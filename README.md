# Bulut OS - Kişisel Bulut Depolama ve Yedekleme Sistemi

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python" alt="Python Version" />
  <img src="https://img.shields.io/badge/FastAPI-2.0-009688?style=for-the-badge&logo=fastapi" alt="FastAPI" />
  <img src="https://img.shields.io/badge/PyQt6-GUI-41CD52?style=for-the-badge&logo=qt" alt="PyQt6" />
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-orange?style=for-the-badge" alt="Platform" />
  <img src="https://img.shields.io/badge/License-MIT-lightgrey?style=for-the-badge" alt="License" />
</p>

**Bulut OS**, büyük kurumsal bulut sağlayıcılarına bağımlı kalmadan kendi sunucunuzu (Oracle Cloud, AWS, Hetzner, DigitalOcean veya evdeki bir Raspberry Pi / Linux makinesi) saniyeler içinde özel bir bulut depolama ve otomatik yedekleme merkezine dönüştüren modern bir açık kaynak yazılımdır.

---

## Öne Çıkan Özellikler

###  1. Parçalı ve Kesintisiz Yükleme (Chunked & Resumable)
- Büyük dosyalar 1 MB'lık dinamik parçalara bölünerek sunucuya aktarılır.
- İnternet bağlantısı kesilirse, bilgisayar kapanırsa veya yükleme durdurulursa işlem baştan **başlamaz**. Kaldığı son bayttan devam eder.
- Dosya boyutu 0 bayt olan boş dosyalar da dahil olmak üzere tam dosya bütünlüğü korunur.

###  2. Entegre Sunucu Dosya Yöneticisi
- Sunucunun deposundaki (`BulutDepolama`) tüm dizinleri tıpkı yerel bir dosya yöneticisi gibi gezebilirsiniz.
- Canlı arama çubuğu ile isim ve dosya uzantısına (`.txt`, `.py`, `.png` vb.) göre anlık filtreleme yapılabilir.
- **Anında Önizleme:** Metin/kod dosyaları ve görseller çift tıklanarak doğrudan pencere içinde görüntülenebilir.
- **Sıfır Disk Kirliliği (Auto-Cleanup):** Görüntülenen geçici dosyalar pencere kapatıldığı anda diskten otomatik olarak silinir.
- **Büyük Dosya Güvenlik Bariyeri:** 30 MB'tan büyük dosyalar önizlenmek istendiğinde kullanıcıdan onay talep ederek arayüzün ve ağın kilitlenmesini engeller.
- **Flaş Diske / Yerel Diske İndirme:** Dosyalar akış (stream) yöntemiyle harici bir USB belleğe veya bilgisayarınızdaki herhangi bir dizine kaydedilebilir.

###  3. Otomatik ve Zamanlanmış Yedekleme
- Belirlediğiniz klasörler, arka planda çalışan **APScheduler** zamanlayıcısı ile istediğiniz gün ve saatte otomatik olarak sunucuya aktarılır.
- **Modern Zaman Seçici:** Tek tıkla hızlı erteleme (+1 saat, +3 saat, bu gece 22:00, yarın sabah 09:00) ve canlı geri sayım önizlemesi sunar.

###  4. Siber Güvenlik ve Bot Kalkanı
- **Brute-Force (Kaba Kuvvet) Engeli:** Üst üste 5 kez hatalı şifre gönderen IP adresleri sunucu tarafından 15 dakika boyunca engellenir (`HTTP 429 Too Many Requests`).
- **Path Traversal Savunması:** Dizin atlama saldırılarını (`../../etc/passwd`) engelleyen güvenli hedef yol doğrulama mekanizması.
- **Zamanlama Saldırısı Koruması (Timing Attack):** `secrets.compare_digest` ile sabit zamanlı şifre doğrulaması.
- **Eşzamanlı Veri Kilidi (`threading.Lock`):** Aynı anda gelen çoklu isteklerde veritabanı dosyalarının (`hafiza.json`, `gorevler.json`) bozulması engellenir.

### 5. Modern ve Emojisiz Arayüz Tasarımı
- Koyu Catppuccin renk paleti (`#1e1e2e`, `#181825`, `#313244`, `#89b4fa`).
- Kesinlikle emoji içermez; sade, beyaz ve şık Unicode simgelerle donatılmıştır.
- İlk kez açıldığında kullanıcıyı karşılayan **"İlk Kurulum Sihirbazı"** sayesinde IP ve şifre tek tıkla yapılandırılır.

---

##  Kurulum Rehberi

Proje iki ana bileşenden oluşur:
1. **Sunucu (Server):** Dosyaları barındıran FastAPI arka ucu.
2. **İstemci (Client):** Masaüstünde çalışan PyQt6 grafik arayüzü.

---

### Bölüm 1: Sunucu Kurulumu

#### Seçenek A: Linux VPS / Oracle Cloud / Ubuntu (Önerilen - Tek Komutla)
Sunucunuza SSH ile bağlandıktan sonra proje klasöründe şu komutu çalıştırmanız yeterlidir:

```bash
sudo bash install.sh
```

**`install.sh` Betiğinin Yaptığı İşlemler:**
1. Sistem paketlerini ve Python sanal ortamını (`venv`) hazırlar.
2. `requirements.txt` bağımlılıklarını kurar.
3. **Oracle Cloud ve Linux Güvenlik Duvarını (`iptables` ve `ufw`) otomatik olarak 8000 portuna açar.**
4. Sunucu yeniden başlasa bile 7/24 çalışmasını sağlayan `systemd` servisini (`bulut-depo.service`) kurup başlatır.
5. Kurulum sonunda sunucunuzun Genel IP adresini ve bağlantı bilgilerinizi ekrana yazdırır.

> **[ÖNEMLİ] Oracle Cloud / AWS Kullanıcıları İçin:**
> Web yönetim panelinizden (Oracle Console -> Virtual Cloud Networks -> Security Lists -> Ingress Rules):
> - **Source CIDR:** `0.0.0.0/0`
> - **Destination Port:** `8000` (TCP)
> kuralını eklemeyi unutmayınız.

**Yararlı Yönetim Komutları:**
```bash
sudo systemctl status bulut-depo     # Sunucunun çalışma durumunu kontrol et
sudo journalctl -u bulut-depo -f      # Canlı sunucu loglarını izle
sudo systemctl restart bulut-depo    # Sunucu servisini yeniden başlat
sudo systemctl stop bulut-depo       # Sunucuyu durdur
```

---

#### Seçenek B: Docker & Docker Compose ile Kurulum
Sunucunuzda Docker kuruluysa:

```bash
docker compose up -d
```
Sunucunuz `http://0.0.0.0:8000` adresinde izole bir konteyner olarak çalışmaya başlar.

---

#### Seçenek C: Manuel Python ile Çalıştırma
```bash
pip install -r requirements.txt
python server.py
```

---

### Bölüm 2: İstemci (Masaüstü Uygulaması) Kurulumu

#### Seçenek A: Bağımsız `.exe` Olarak Çalıştırma (Son Kullanıcı İçin)
Bilgisayarınızda Python yüklü olmasına gerek yoktur:
1. GitHub Releases sayfasından **`BulutOS.exe`** dosyasını indirin.
2. Çift tıklayarak başlatın.
3. Açılan ilk kurulum sihirbazına sunucunuzun adresini (Örn: `http://140.238.x.x:8000`) ve şifrenizi girin.
4. "Bağlan ve Başla" butonuna basarak doğrudan kullanmaya başlayın.

#### Seçenek B: Python Kaynak Kodundan Çalıştırma
```bash
# Bağımlılıkları yükleyin
pip install -r requirements-client.txt

# Uygulamayı başlatın
python client.py
```

---

##  Proje Dizin Yapısı

```text
├── client.py                 # PyQt6 Masaüstü İstemci Kaynak Kodu
├── server.py                 # FastAPI Sunucu Kaynak Kodu
├── install.sh                # Linux & Oracle Cloud Tek Tıkla Kurulum Betiği
├── Dockerfile                # Sunucu Docker İmaj Tanımı
├── docker-compose.yml        # Docker Konteyner Yapılandırması
├── requirements.txt          # Sunucu Python Bağımlılıkları
├── requirements-client.txt   # İstemci Python Bağımlılıkları
├── .gitignore                # Git Hariç Tutma Listesi
└── README.md                 # Proje Tanıtım ve Kurulum Kılavuzu
```

---

##  Sık Karşılaşılan Sorunlar ve Çözümleri

| Hata Kodu / Belirti | Olası Neden | Çözüm |
| :--- | :--- | :--- |
| **Zaman Aşımı (Timeout)** | Bulut sağlayıcınız port 8000'i engelliyor. | Oracle Cloud / AWS web panelinden `Ingress Rules` bölümüne TCP 8000 izni ekleyin ve `sudo ufw allow 8000/tcp` yapın. |
| **Bağlantı Hatası (Connection Error)** | Uvicorn servisi kapalı veya `127.0.0.1` dinliyor. | `sudo systemctl status bulut-depo` ile servisi kontrol edin. Sunucunun `0.0.0.0` üzerinde çalıştığından emin olun. |
| **HTTP 401 (Yetkisiz Erişim)** | Sunucu şifresi hatalı girildi. | İstemcideki **Sunucu Ayarları** menüsünden şifrenizi kontrol edin ve güncelleyin. |
| **HTTP 429 (Güvenlik Engeli)** | Üst üste 5 kez hatalı şifre girildi. | Brute-force koruması devreye girdi. IP engeliniz 15 dakika sonra otomatik açılacaktır. |

---

##  Geliştirici & İletişim

- **Geliştirici:** az1032
- **GitHub:** [@az1032](https://github.com/az1032)
- **E-posta:** [az1032110@gmail.com](mailto:az1032110@gmail.com)

---

## Lisans

Bu proje **MIT Lisansı** altında lisanslanmıştır. Dilediğiniz gibi geliştirebilir, dağıtabilir veya kendi sunucularınızda kullanabilirsiniz.
