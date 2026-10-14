import os
import shutil
import json
import secrets
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Form, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Bulut Depolama Sunucusu", version="2.0")

# --- AYARLAR VE DİZİNLER ---
SUNUCU_SIFRESI = os.getenv("BULUT_SIFRE", "esatesat16.")
HAFIZA_DOSYASI = "hafiza.json"
GOREV_DOSYASI = "gorevler.json"
ANA_DEPO_KLASORU = Path(os.getenv("BULUT_DEPO_YOLU", "BulutDepolama")).resolve()

# Depolama dizini yoksa oluştur
ANA_DEPO_KLASORU.mkdir(parents=True, exist_ok=True)

# Eşzamanlı isteklerde dosya bozulmasını engelleyen kilit
dosya_kilidi = threading.Lock()

# --- GÜVENLİK, RATE LIMIT & BRUTE-FORCE KORUMASI ---
MAX_HATALI_DENEME = 5          # 5 hatalı şifre denemesinde IP engellenir
ENGEL_SURESI = 15 * 60         # 15 dakika boyunca engellenir (saniye)

engelli_ipler = {}             # {ip: engel_bitis_zamani}
hatali_denemeler = defaultdict(list) # {ip: [zaman1, zaman2, ...]}
guvenlik_kilidi = threading.Lock()

@app.middleware("http")
async def brute_force_ve_guvenlik_middleware(request: Request, call_next):
    # İstemci IP adresini tespit et (Ters vekil arkasındaysa X-Forwarded-For veya request.client.host)
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        istemci_ip = x_forwarded_for.split(",")[0].strip()
    elif request.client and request.client.host:
        istemci_ip = request.client.host
    else:
        istemci_ip = "127.0.0.1"

    simdi = time.time()

    # 1. IP Engelli mi kontrol et
    with guvenlik_kilidi:
        if istemci_ip in engelli_ipler:
            bitis = engelli_ipler[istemci_ip]
            if simdi < bitis:
                kalan_dk = int((bitis - simdi) / 60) + 1
                return JSONResponse(
                    status_code=429,
                    content={
                        "detail": f"Çok fazla hatalı şifre denemesi yapıldı! Güvenlik nedeniyle IP adresiniz ({istemci_ip}) {kalan_dk} dakika boyunca engellendi."
                    }
                )
            else:
                # Engel süresi dolmuş, temizle
                del engelli_ipler[istemci_ip]
                hatali_denemeler.pop(istemci_ip, None)

    # 2. İsteği işlet
    response = await call_next(request)

    # 3. Şifre hatalıysa (HTTP 401) sayacı artır
    if response.status_code == 401:
        with guvenlik_kilidi:
            # Son 10 dakika içindeki denemeleri tut
            hatali_denemeler[istemci_ip] = [t for t in hatali_denemeler[istemci_ip] if simdi - t < 600]
            hatali_denemeler[istemci_ip].append(simdi)
            deneme_sayisi = len(hatali_denemeler[istemci_ip])
            
            if deneme_sayisi >= MAX_HATALI_DENEME:
                engelli_ipler[istemci_ip] = simdi + ENGEL_SURESI
                hatali_denemeler.pop(istemci_ip, None)
                print(f"[GÜVENLİK UYARISI] Brute-force saldırı şüphesi: {istemci_ip} adresi {ENGEL_SURESI // 60} dakika engellendi!")
    elif response.status_code == 200:
        # Başarılı istek geldiğinde hatalı deneme sayısını sıfırla
        with guvenlik_kilidi:
            if istemci_ip in hatali_denemeler:
                hatali_denemeler.pop(istemci_ip, None)

    return response

# --- YARDIMCI FONKSİYONLAR ---
def json_oku(dosya_yolu: str) -> dict:
    if not os.path.exists(dosya_yolu):
        return {}
    try:
        with open(dosya_yolu, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def json_yaz(dosya_yolu: str, veri: dict):
    # Güvenli yazım: Önce geçici dosyaya yazıp sonra atomik olarak değiştir
    gecici_yol = f"{dosya_yolu}.tmp"
    with open(gecici_yol, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=4)
    if os.path.exists(dosya_yolu):
        os.remove(dosya_yolu)
    os.rename(gecici_yol, dosya_yolu)

def sifre_kontrol(gelen_sifre: Optional[str]):
    # Sabit zamanlı karşılaştırma (Timing attack koruması)
    if not gelen_sifre or not secrets.compare_digest(gelen_sifre, SUNUCU_SIFRESI):
        raise HTTPException(status_code=401, detail="Yetkisiz erişim! Şifre hatalı veya eksik.")

def guvenli_hedef_yol(dosya_adi: str) -> Path:
    """Path Traversal (Dizin Atlama) saldırılarını engeller."""
    # Başındaki / veya \ karakterlerini temizle
    temiz_ad = dosya_adi.strip().lstrip("/\\")
    hedef = (ANA_DEPO_KLASORU / temiz_ad).resolve()
    
    # Hedef yol kesinlikle ANA_DEPO_KLASORU altında olmalı
    if not str(hedef).startswith(str(ANA_DEPO_KLASORU)):
        raise HTTPException(status_code=400, detail="Güvenlik ihlali: Geçersiz dosya yolu!")
    return hedef

# --- TEMEL ENDPOINTLER ---
@app.get("/")
def disk_durumu(gelen_sifre: Optional[str] = Header(None)):
    sifre_kontrol(gelen_sifre)
    try:
        # ANA_DEPO_KLASORU'nun bulunduğu diskin kullanımını ölç
        toplam, _, bos = shutil.disk_usage(str(ANA_DEPO_KLASORU))
        return {"toplam": toplam, "bos_alan": bos}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Disk bilgisi alınamadı: {str(e)}")

@app.get("/yedek-sorgula")
def yedek_sorgula(dosya_id: str, dosya_adi: Optional[str] = None, gelen_sifre: Optional[str] = Header(None)):
    sifre_kontrol(gelen_sifre)
    with dosya_kilidi:
        hafiza = json_oku(HAFIZA_DOSYASI)
        yuklenen = hafiza.get(dosya_id, 0)

        # Eğer dosya adı verilmişse ve sunucudaki gerçek dosya boyutu ile hafıza uyuşmuyorsa,
        # diskteki gerçek dosya boyutunu baz alarak hafızayı senkronize et
        if dosya_adi:
            try:
                hedef = guvenli_hedef_yol(dosya_adi)
                if hedef.is_file():
                    disk_boyutu = hedef.stat().st_size
                    if disk_boyutu != yuklenen:
                        yuklenen = disk_boyutu
                        hafiza[dosya_id] = yuklenen
                        json_yaz(HAFIZA_DOSYASI, hafiza)
                elif not hedef.exists() and yuklenen > 0:
                    # Dosya diskte silinmişse sıfırla
                    yuklenen = 0
                    hafiza[dosya_id] = 0
                    json_yaz(HAFIZA_DOSYASI, hafiza)
            except Exception:
                pass

        return {"yuklenen_boyut": yuklenen}

@app.post("/yedek-parca-yukle")
def parca_yukle(
    dosya_id: str = Form(...),
    dosya_adi: str = Form(...), 
    bastan_basla: bool = Form(False),
    gelen_dosya: UploadFile = File(...), 
    gelen_sifre: Optional[str] = Header(None)
):
    sifre_kontrol(gelen_sifre)
    hedef_dosya_yolu = guvenli_hedef_yol(dosya_adi)
    
    # Üst klasörler yoksa güvenle oluştur
    hedef_dosya_yolu.parent.mkdir(parents=True, exist_ok=True)
    
    veri = gelen_dosya.file.read()
    eklenen_boyut = len(veri)

    # Dosyayı yaz: bastan_basla ise 'wb' (üzerine yaz), devam ediyorsa 'ab' (ekle)
    mod = "wb" if bastan_basla else "ab"
    with open(hedef_dosya_yolu, mod) as f:
        if eklenen_boyut > 0:
            f.write(veri)
        else:
            # 0 baytlık dosya oluşturma desteği
            pass
            
    with dosya_kilidi:
        hafiza = json_oku(HAFIZA_DOSYASI)
        if bastan_basla:
            hafiza[dosya_id] = eklenen_boyut
        else:
            hafiza[dosya_id] = hafiza.get(dosya_id, 0) + eklenen_boyut
        json_yaz(HAFIZA_DOSYASI, hafiza)
        
    return {"mesaj": "Parça eklendi", "mevcut_boyut": hafiza[dosya_id]}

# --- GÖREV YÖNETİMİ ---
class GorevModel(BaseModel):
    id: str
    klasorler: List[str]
    zaman: str
    durum: str

@app.get("/gorevler")
def gorevleri_getir(gelen_sifre: Optional[str] = Header(None)):
    sifre_kontrol(gelen_sifre)
    with dosya_kilidi:
        return json_oku(GOREV_DOSYASI)

@app.post("/gorev-ekle")
def gorev_ekle(gorev: GorevModel, gelen_sifre: Optional[str] = Header(None)):
    sifre_kontrol(gelen_sifre)
    with dosya_kilidi:
        gorevler = json_oku(GOREV_DOSYASI)
        # Pydantic v1 / v2 uyumluluğu
        gorev_veri = getattr(gorev, "model_dump", getattr(gorev, "dict", None))()
        gorevler[gorev.id] = gorev_veri
        json_yaz(GOREV_DOSYASI, gorevler)
    return {"mesaj": "Görev başarıyla eklendi"}

@app.post("/gorev-guncelle")
def gorev_guncelle(
    gorev_id: str = Form(...), 
    durum: Optional[str] = Form(None), 
    zaman: Optional[str] = Form(None), 
    gelen_sifre: Optional[str] = Header(None)
):
    sifre_kontrol(gelen_sifre)
    with dosya_kilidi:
        gorevler = json_oku(GOREV_DOSYASI)
        if gorev_id not in gorevler:
            raise HTTPException(status_code=404, detail="Görev bulunamadı")
        
        if durum:
            gorevler[gorev_id]["durum"] = durum
        if zaman:
            gorevler[gorev_id]["zaman"] = zaman
            
        json_yaz(GOREV_DOSYASI, gorevler)
    return {"mesaj": "Görev güncellendi"}

@app.delete("/gorev-sil/{gorev_id}")
def gorev_sil(gorev_id: str, gelen_sifre: Optional[str] = Header(None)):
    sifre_kontrol(gelen_sifre)
    with dosya_kilidi:
        gorevler = json_oku(GOREV_DOSYASI)
        if gorev_id not in gorevler:
            raise HTTPException(status_code=404, detail="Görev bulunamadı")
            
        del gorevler[gorev_id]
        json_yaz(GOREV_DOSYASI, gorevler)
    return {"mesaj": "Görev silindi"}

# --- DOSYA YÖNETİCİSİ ENDPOINTLERİ ---
from fastapi.responses import FileResponse
from datetime import datetime

def format_boyut(bayt: int) -> str:
    for birim in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bayt < 1024.0:
            return f"{bayt:.1f} {birim}"
        bayt /= 1024.0
    return f"{bayt:.1f} PB"

@app.get("/dosyalar-listele")
def dosyalar_listele(alt_dizin: Optional[str] = "", gelen_sifre: Optional[str] = Header(None)):
    sifre_kontrol(gelen_sifre)
    hedef_dizin = guvenli_hedef_yol(alt_dizin)
    
    if not hedef_dizin.exists() or not hedef_dizin.is_dir():
        return {"mevcut_dizin": alt_dizin, "ogeler": []}
        
    ogeler = []
    try:
        with os.scandir(hedef_dizin) as entries:
            for entry in entries:
                try:
                    stat = entry.stat()
                    mtime_str = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                    if entry.is_dir():
                        ogeler.append({
                            "ad": entry.name,
                            "tip": "klasor",
                            "uzanti": "",
                            "boyut": 0,
                            "boyut_str": "-",
                            "mtime": mtime_str
                        })
                    else:
                        uzanti = os.path.splitext(entry.name)[1].lower()
                        ogeler.append({
                            "ad": entry.name,
                            "tip": "dosya",
                            "uzanti": uzanti,
                            "boyut": stat.st_size,
                            "boyut_str": format_boyut(stat.st_size),
                            "mtime": mtime_str
                        })
                except (OSError, PermissionError):
                    continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dizin okunamadı: {str(e)}")
        
    # Klasörleri önce, sonra dosyaları alfabetik sırala
    ogeler.sort(key=lambda x: (0 if x["tip"] == "klasor" else 1, x["ad"].lower()))
    
    # Göreceli mevcut dizin yolunu hesapla
    rel_dizin = os.path.relpath(hedef_dizin, ANA_DEPO_KLASORU).replace("\\", "/")
    if rel_dizin == ".":
        rel_dizin = ""
        
    return {"mevcut_dizin": rel_dizin, "ogeler": ogeler}

@app.get("/dosya-indir")
def dosya_indir(dosya_yolu: str, gelen_sifre: Optional[str] = Header(None)):
    sifre_kontrol(gelen_sifre)
    hedef_dosya = guvenli_hedef_yol(dosya_yolu)
    
    if not hedef_dosya.exists() or not hedef_dosya.is_file():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı.")
        
    return FileResponse(
        path=str(hedef_dosya), 
        filename=hedef_dosya.name,
        media_type="application/octet-stream"
    )

@app.delete("/depo-dosya-sil")
def depo_dosya_sil(dosya_yolu: str, gelen_sifre: Optional[str] = Header(None)):
    sifre_kontrol(gelen_sifre)
    hedef = guvenli_hedef_yol(dosya_yolu)
    
    if not hedef.exists():
        raise HTTPException(status_code=404, detail="Öğe bulunamadı.")
        
    try:
        if hedef.is_dir():
            shutil.rmtree(hedef)
        else:
            hedef.unlink()
        return {"mesaj": "Öğe başarıyla silindi"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Silme hatası: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("BULUT_HOST", "0.0.0.0")
    port = int(os.getenv("BULUT_PORT", "8000"))
    print("=" * 50)
    print(" Bulut Depolama Sunucusu Aktif Ediliyor")
    print(f" Dinlenen Adres : http://{host}:{port}")
    print(f" Depolama Alanı : {ANA_DEPO_KLASORU}")
    print("=" * 50)
    uvicorn.run("server:app", host=host, port=port, reload=False)

