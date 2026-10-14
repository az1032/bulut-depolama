import sys
import os
import requests
import json
import uuid
import hashlib
import tempfile
import shutil
import atexit
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QPushButton, QLabel, QStackedWidget, 
                             QFrame, QFileDialog, QGraphicsOpacityEffect, 
                             QTimeEdit, QDialog, QDialogButtonBox, QCalendarWidget, 
                             QListWidget, QProgressBar, QScrollArea, QMessageBox,
                             QLineEdit, QCheckBox, QTableWidget, QTableWidgetItem,
                             QHeaderView, QAbstractItemView, QTextEdit, QSpinBox)
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, Qt, QTimer, QRectF, QThread, pyqtSignal, pyqtProperty, QUrl, QDate
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QColor, QFont, QDesktopServices, QPixmap

# Geçici Önizleme Klasörü (Kapatıldığında otomatik temizlenir)
TEMP_ONIZLEME_DIZINI = Path(tempfile.gettempdir()) / "bulut_depo_onizleme"
TEMP_ONIZLEME_DIZINI.mkdir(parents=True, exist_ok=True)

def temp_onizleme_temizle():
    """Geçici indirilen tüm önizleme dosyalarını temizler."""
    try:
        if TEMP_ONIZLEME_DIZINI.exists():
            shutil.rmtree(TEMP_ONIZLEME_DIZINI, ignore_errors=True)
    except Exception:
        pass

atexit.register(temp_onizleme_temizle)

# --- AYAR DOSYASI YÖNETİMİ ---
AYAR_DOSYASI = "istemci_ayar.json"

def ayar_yukle():
    varsayilan = {
        "sunucu_url": os.getenv("BULUT_SUNUCU_URL", ""),
        "sifre": os.getenv("BULUT_SIFRE", "")
    }
    if os.path.exists(AYAR_DOSYASI):
        try:
            with open(AYAR_DOSYASI, "r", encoding="utf-8") as f:
                kayitli = json.load(f)
                if isinstance(kayitli, dict):
                    varsayilan.update(kayitli)
        except Exception:
            pass
    return varsayilan

def ayar_kaydet(sunucu_url: str, sifre: str):
    try:
        with open(AYAR_DOSYASI, "w", encoding="utf-8") as f:
            json.dump({"sunucu_url": sunucu_url.strip(), "sifre": sifre.strip()}, f, ensure_ascii=False, indent=4)
        return True
    except Exception:
        return False

# İlk ayarları yükle
ILK_AYARLAR = ayar_yukle()
TIMEOUT = 10

# --- CSS TASARIMI (EMOJİSİZ, SADE VE ŞIK) ---
STYLE_SHEET = """
QMainWindow { background-color: #1e1e2e; }
QFrame#Sidebar { background-color: #181825; border-left: 2px solid #313244; }
QFrame#TopBar { background-color: #181825; border-bottom: 2px solid #313244; }
QFrame#BottomBar { background-color: #181825; border-top: 1px solid #313244; min-height: 32px; max-height: 32px; }

QPushButton#SidebarBtn { background-color: transparent; color: #cdd6f4; text-align: left; padding-left: 20px; border-radius: 0px; font-weight: bold; font-size: 14px; padding-top: 10px; padding-bottom: 10px; }
QPushButton#SidebarBtn:hover { background-color: #313244; border-left: 4px solid #89b4fa; }
QPushButton#MenuBtn { background-color: transparent; color: #cdd6f4; font-size: 20px; }
QPushButton#MenuBtn:hover { background-color: #313244; }

QPushButton#NavBtn { background-color: #313244; color: #cdd6f4; border-radius: 6px; padding: 6px 15px; font-weight: bold; font-size: 15px; margin: 5px; }
QPushButton#NavBtn:hover { background-color: #45475a; }

QPushButton#ActionBtn { background-color: #585b70; color: #cdd6f4; border-radius: 8px; font-weight: bold; font-size: 14px; padding: 10px;}
QPushButton#ActionBtn:hover { background-color: #6c7086; }

QPushButton#CancelBtn { background-color: #e78284; color: #181825; border-radius: 8px; font-weight: bold; font-size: 14px; padding: 10px;}
QPushButton#CancelBtn:hover { background-color: #ea999c; }

QPushButton#ErteleBtn { background-color: #313244; color: #cdd6f4; border: 1px solid #45475a; border-radius: 6px; padding: 4px 10px; font-size: 12px; font-weight: bold; }
QPushButton#ErteleBtn:hover { background-color: #45475a; border-color: #89b4fa; }

QPushButton#KucukBtn { background-color: #313244; color: #cdd6f4; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: bold; }
QPushButton#KucukBtn:hover { background-color: #45475a; color: #ffffff; }

QFrame[class="SettingsRow"] { background-color: #181825; border-radius: 10px; }
QLabel[class="SettingsLabel"] { font-size: 15px; font-weight: bold; color: #cdd6f4; }
QLabel[class="SettingsValue"] { font-size: 13px; color: #a6adc8; padding-right: 15px; }
QPushButton[class="SettingsBtn"] { background-color: #313244; color: #cdd6f4; border-radius: 6px; padding: 6px 15px; font-weight: bold; }
QPushButton[class="SettingsBtn"]:hover { background-color: #45475a; }

QLineEdit { background-color: #11111b; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; padding: 8px 12px; font-size: 13px; }
QLineEdit:focus { border: 1px solid #89b4fa; }

QListWidget { background-color: #11111b; color: #cdd6f4; border: 1px solid #313244; border-radius: 5px; padding: 5px; }
QScrollArea { border: none; background-color: transparent; }
QWidget#ScrollContent { background-color: transparent; }

/* Progress Bar Stilleri */
QProgressBar { border: 1px solid #313244; border-radius: 4px; text-align: center; color: #cdd6f4; background-color: #11111b; font-size: 11px; font-weight: bold; height: 16px; }
QProgressBar::chunk { background-color: #89b4fa; border-radius: 3px; }
QProgressBar#GenelBar::chunk { background-color: #a6e3a1; }

QTableWidget { background-color: #11111b; color: #cdd6f4; border: 1px solid #313244; border-radius: 6px; gridline-color: #1e1e2e; }
QTableWidget::item { padding: 6px; }
QTableWidget::item:selected { background-color: #313244; color: #89b4fa; }
QHeaderView::section { background-color: #181825; color: #cdd6f4; font-weight: bold; border: 1px solid #313244; padding: 6px; font-size: 12px; }

QLabel { color: #cdd6f4; font-size: 14px; }
QLabel#Baslik { font-size: 24px; font-weight: bold; }
QLabel#KucukBaslik { font-size: 18px; font-weight: bold; color: #89b4fa; }
QLabel#HataMetni { color: #f38ba8; font-weight: bold; }
QLabel#BasariMetni { color: #89b4fa; font-weight: bold; } 
"""

# --- MODERN VE GELİŞMİŞ TAKVİM & SAAT SEÇİCİ ---
class ModernZamanSecici(QDialog):
    def __init__(self, parent=None, varsayilan_dt=None):
        super().__init__(parent)
        self.setWindowTitle("Zaman ve Saat Belirle")
        self.resize(500, 560)
        self.setStyleSheet(STYLE_SHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        baslik = QLabel("Yedekleme Zamanı Planlama")
        baslik.setObjectName("KucukBaslik")
        layout.addWidget(baslik)

        # Hızlı Hazır Seçimler (Presets)
        preset_kutu = QFrame()
        preset_kutu.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 8px; padding: 4px;")
        p_lay = QHBoxLayout(preset_kutu)
        p_lay.setContentsMargins(6, 6, 6, 6)
        p_lay.setSpacing(6)

        btn_p1 = QPushButton("+1 Saat")
        btn_p1.setObjectName("KucukBtn")
        btn_p1.clicked.connect(lambda: self.hizli_ayar(saat_farki=1))
        
        btn_p2 = QPushButton("+3 Saat")
        btn_p2.setObjectName("KucukBtn")
        btn_p2.clicked.connect(lambda: self.hizli_ayar(saat_farki=3))

        btn_p3 = QPushButton("Bu Akşam (22:00)")
        btn_p3.setObjectName("KucukBtn")
        btn_p3.clicked.connect(lambda: self.hizli_ayar(saat=22, dakika=0))

        btn_p4 = QPushButton("Yarın Sabah (09:00)")
        btn_p4.setObjectName("KucukBtn")
        btn_p4.clicked.connect(lambda: self.hizli_ayar(gun_farki=1, saat=9, dakika=0))

        btn_p5 = QPushButton("Yarın (Aynı Saat)")
        btn_p5.setObjectName("KucukBtn")
        btn_p5.clicked.connect(lambda: self.hizli_ayar(gun_farki=1))

        for b in [btn_p1, btn_p2, btn_p3, btn_p4, btn_p5]:
            p_lay.addWidget(b)
        layout.addWidget(preset_kutu)

        # Takvim
        self.takvim = QCalendarWidget(self)
        self.takvim.setGridVisible(True)
        self.takvim.setVerticalHeaderFormat(QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader)
        self.takvim.setStyleSheet("""
            QCalendarWidget {
                background-color: #181825;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 8px;
            }
            QCalendarWidget QWidget#qt_calendar_navigationbar {
                background-color: #11111b;
                border-bottom: 1px solid #313244;
                padding: 4px;
            }
            QCalendarWidget QToolButton {
                color: #cdd6f4;
                font-weight: bold;
                border-radius: 4px;
                padding: 4px;
            }
            QCalendarWidget QToolButton:hover {
                background-color: #313244;
            }
            QCalendarWidget QMenu {
                background-color: #181825;
                color: #cdd6f4;
            }
            QCalendarWidget QSpinBox {
                background-color: #11111b;
                color: #cdd6f4;
            }
            QCalendarWidget QAbstractItemView:enabled {
                background-color: #181825;
                color: #cdd6f4;
                selection-background-color: #89b4fa;
                selection-color: #181825;
            }
        """)
        self.takvim.selectionChanged.connect(self.onizleme_guncelle)
        layout.addWidget(self.takvim)

        # Saat & Dakika Seçim Alanı
        saat_kutu = QFrame()
        saat_kutu.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 8px; padding: 6px;")
        saat_lay = QHBoxLayout(saat_kutu)
        saat_lay.setContentsMargins(15, 6, 15, 6)
        
        lbl_saat_baslik = QLabel("Saat ve Dakika:")
        lbl_saat_baslik.setStyleSheet("color: #cdd6f4; font-weight: bold; font-size: 13px;")
        saat_lay.addWidget(lbl_saat_baslik)
        saat_lay.addStretch()

        self.spin_saat = QSpinBox()
        self.spin_saat.setRange(0, 23)
        self.spin_saat.setFixedWidth(65)
        self.spin_saat.setFixedHeight(34)
        self.spin_saat.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_saat.setStyleSheet("background-color: #11111b; color: #89b4fa; font-size: 16px; font-weight: bold; border: 1px solid #313244; border-radius: 6px;")
        self.spin_saat.valueChanged.connect(self.onizleme_guncelle)
        saat_lay.addWidget(self.spin_saat)

        lbl_nokta = QLabel(":")
        lbl_nokta.setStyleSheet("color: #cdd6f4; font-size: 18px; font-weight: bold;")
        saat_lay.addWidget(lbl_nokta)

        self.spin_dakika = QSpinBox()
        self.spin_dakika.setRange(0, 59)
        self.spin_dakika.setFixedWidth(65)
        self.spin_dakika.setFixedHeight(34)
        self.spin_dakika.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_dakika.setStyleSheet("background-color: #11111b; color: #89b4fa; font-size: 16px; font-weight: bold; border: 1px solid #313244; border-radius: 6px;")
        self.spin_dakika.valueChanged.connect(self.onizleme_guncelle)
        saat_lay.addWidget(self.spin_dakika)

        layout.addWidget(saat_kutu)

        # Önizleme Göstergesi
        self.lbl_onizleme = QLabel("")
        self.lbl_onizleme.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 12px;")
        self.lbl_onizleme.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_onizleme)

        # Butonlar
        btn_box = QHBoxLayout()
        btn_iptal = QPushButton("İptal")
        btn_iptal.setObjectName("CancelBtn")
        btn_iptal.clicked.connect(self.reject)

        btn_onay = QPushButton("Tarihi Seç ve Onayla")
        btn_onay.setObjectName("ActionBtn")
        btn_onay.clicked.connect(self.accept)

        btn_box.addWidget(btn_iptal)
        btn_box.addWidget(btn_onay)
        layout.addLayout(btn_box)

        # Varsayılan zaman
        baslangic = varsayilan_dt or (datetime.now() + timedelta(hours=1))
        self.takvim.setSelectedDate(QDate(baslangic.year, baslangic.month, baslangic.day))
        self.spin_saat.setValue(baslangic.hour)
        self.spin_dakika.setValue(baslangic.minute)
        self.onizleme_guncelle()

    def hizli_ayar(self, saat_farki=0, gun_farki=0, saat=None, dakika=None):
        simdi = datetime.now()
        hedef = simdi + timedelta(days=gun_farki, hours=saat_farki)
        if saat is not None:
            hedef = hedef.replace(hour=saat)
        if dakika is not None:
            hedef = hedef.replace(minute=dakika)
            
        self.takvim.setSelectedDate(QDate(hedef.year, hedef.month, hedef.day))
        self.spin_saat.setValue(hedef.hour)
        self.spin_dakika.setValue(hedef.minute)
        self.onizleme_guncelle()

    def onizleme_guncelle(self):
        dt = self.get_datetime()
        simdi = datetime.now()
        fark = dt - simdi
        
        tarih_str = dt.strftime("%Y-%m-%d %H:%M")
        if fark.total_seconds() > 0:
            toplam_dk = int(fark.total_seconds() // 60)
            gun = toplam_dk // (24 * 60)
            kalan_saat = (toplam_dk % (24 * 60)) // 60
            kalan_dk = toplam_dk % 60
            
            sure_str = ""
            if gun > 0: sure_str += f"{gun} gün "
            if kalan_saat > 0 or gun > 0: sure_str += f"{kalan_saat} saat "
            sure_str += f"{kalan_dk} dakika sonra"
            self.lbl_onizleme.setText(f"Planlanan Zaman: {tarih_str} ({sure_str})")
            self.lbl_onizleme.setStyleSheet("color: #a6e3a1; font-weight: bold; font-size: 12px;")
        else:
            self.lbl_onizleme.setText(f"Planlanan Zaman: {tarih_str} (Zamanı geçmiş - Anında başlayacak)")
            self.lbl_onizleme.setStyleSheet("color: #f9e2af; font-weight: bold; font-size: 12px;")

    def get_datetime(self):
        tarih = self.takvim.selectedDate()
        saat = self.spin_saat.value()
        dakika = self.spin_dakika.value()
        return datetime(tarih.year(), tarih.month(), tarih.day(), saat, dakika)

TarihSaatSecici = ModernZamanSecici

# --- İLK KURULUM SİHİRBAZI DİYALOĞU ---
class IlkKurulumDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulut OS - Sunucu Bağlantı Kurulumu")
        self.setFixedSize(500, 370)
        self.setStyleSheet(STYLE_SHEET)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 25, 30, 25)
        layout.setSpacing(14)

        lbl_baslik = QLabel("Bulut OS'a Hoş Geldiniz")
        lbl_baslik.setObjectName("Baslik")
        layout.addWidget(lbl_baslik)

        lbl_aciklama = QLabel(
            "Uygulamayı kullanabilmek için lütfen bağlanmak istediğiniz sunucunun "
            "adresini ve şifresini giriniz."
        )
        lbl_aciklama.setStyleSheet("color: #a6adc8; font-size: 13px;")
        lbl_aciklama.setWordWrap(True)
        layout.addWidget(lbl_aciklama)

        # Sunucu URL
        layout.addWidget(QLabel("Sunucu Adresi (Örn: http://1.2.3.4:8000):"))
        self.txt_url = QLineEdit()
        self.txt_url.setPlaceholderText("http://sunucu-ip-adresiniz:8000")
        layout.addWidget(self.txt_url)

        # Şifre
        layout.addWidget(QLabel("Sunucu Şifresi:"))
        sifre_lay = QHBoxLayout()
        self.txt_sifre = QLineEdit()
        self.txt_sifre.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_sifre.setPlaceholderText("Sunucu şifrenizi girin...")
        sifre_lay.addWidget(self.txt_sifre)

        chk_goster = QCheckBox("Göster")
        chk_goster.setStyleSheet("color: #a6adc8; font-size: 12px;")
        chk_goster.toggled.connect(lambda g: self.txt_sifre.setEchoMode(QLineEdit.EchoMode.Normal if g else QLineEdit.EchoMode.Password))
        sifre_lay.addWidget(chk_goster)
        layout.addLayout(sifre_lay)

        self.lbl_durum = QLabel("")
        self.lbl_durum.setWordWrap(True)
        self.lbl_durum.setStyleSheet("font-size: 12px; font-weight: bold;")
        layout.addWidget(self.lbl_durum)

        # Butonlar
        btn_lay = QHBoxLayout()
        btn_cikis = QPushButton("Vazgeç")
        btn_cikis.setObjectName("CancelBtn")
        btn_cikis.clicked.connect(self.reject)
        
        btn_baglan = QPushButton("Bağlan ve Başla")
        btn_baglan.setObjectName("ActionBtn")
        btn_baglan.clicked.connect(self.baglantiyi_dene)

        btn_lay.addWidget(btn_cikis)
        btn_lay.addWidget(btn_baglan)
        layout.addLayout(btn_lay)

    def baglantiyi_dene(self):
        url = self.txt_url.text().strip().rstrip("/")
        sifre = self.txt_sifre.text().strip()

        if not url:
            self.lbl_durum.setText("Lütfen bir sunucu adresi girin!")
            self.lbl_durum.setStyleSheet("color: #f38ba8;")
            return

        if not (url.startswith("http://") or url.startswith("https://")):
            url = "http://" + url
            self.txt_url.setText(url)

        self.lbl_durum.setText("Sunucuya bağlanılıyor, lütfen bekleyin...")
        self.lbl_durum.setStyleSheet("color: #89b4fa;")
        QApplication.processEvents()

        try:
            resp = requests.get(f"{url}/", headers={"gelen-sifre": sifre}, timeout=6)
            if resp.status_code == 200:
                self.lbl_durum.setText("Bağlantı başarılı!")
                self.lbl_durum.setStyleSheet("color: #a6e3a1;")
                ayar_kaydet(url, sifre)
                self.accept()
            elif resp.status_code == 401:
                self.lbl_durum.setText("Sunucu şifresi hatalı! (HTTP 401)")
                self.lbl_durum.setStyleSheet("color: #f38ba8;")
            elif resp.status_code == 429:
                self.lbl_durum.setText("Çok fazla hatalı deneme! IP engellendi. (HTTP 429)")
                self.lbl_durum.setStyleSheet("color: #f38ba8;")
            else:
                self.lbl_durum.setText(f"Sunucu beklenmeyen yanıt verdi: HTTP {resp.status_code}")
                self.lbl_durum.setStyleSheet("color: #f38ba8;")
        except requests.exceptions.ConnectTimeout:
            self.lbl_durum.setText("Zaman Aşımı: Sunucuya ulaşılamadı. Port ve güvenlik duvarını kontrol edin.")
            self.lbl_durum.setStyleSheet("color: #f38ba8;")
        except requests.exceptions.ConnectionError:
            self.lbl_durum.setText("Bağlantı Hatası: Sunucu kapalı veya IP adresi hatalı.")
            self.lbl_durum.setStyleSheet("color: #f38ba8;")
        except Exception as e:
            self.lbl_durum.setText(f"Hata: {str(e)[:50]}")
            self.lbl_durum.setStyleSheet("color: #f38ba8;")

# --- AŞAĞIYA KAYAN KATLANABİLİR MENÜ KUTUSU ---
class KatlanabilirKutu(QWidget):
    def __init__(self, baslik, parent=None):
        super().__init__(parent)
        self.baslik_metin = baslik
        self.ana_layout = QVBoxLayout(self)
        self.ana_layout.setContentsMargins(0, 4, 0, 4)
        self.ana_layout.setSpacing(0)

        # Başlık Butonu (Minimalist ve Şık Tasarım)
        self.btn_baslik = QPushButton(f"{baslik}   ›")
        self.btn_baslik.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_baslik.setStyleSheet("""
            QPushButton {
                background-color: #181825;
                color: #cdd6f4;
                text-align: left;
                padding: 13px 18px;
                font-size: 14px;
                font-weight: bold;
                border: 1px solid #313244;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #242438;
                border-color: #89b4fa;
                color: #ffffff;
            }
        """)
        self.btn_baslik.clicked.connect(self.toggle)
        self.ana_layout.addWidget(self.btn_baslik)

        # Aşağıya Kayan İçerik Alanı
        self.icerik_frame = QFrame()
        self.icerik_frame.setStyleSheet("""
            QFrame {
                background-color: #11111b;
                border: 1px solid #313244;
                border-top: none;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
            }
        """)
        self.icerik_layout = QVBoxLayout(self.icerik_frame)
        self.icerik_layout.setContentsMargins(20, 16, 20, 16)
        self.icerik_layout.setSpacing(12)
        
        self.icerik_frame.setMaximumHeight(0)
        self.icerik_frame.setVisible(False)
        self.ana_layout.addWidget(self.icerik_frame)

        # Animasyon
        self.anim = QPropertyAnimation(self.icerik_frame, b"maximumHeight")
        self.anim.setDuration(220)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutQuart)
        self.anim.finished.connect(self.animasyon_bitti)
        self.acik = False

    def icerik_ekle(self, widget):
        self.icerik_layout.addWidget(widget)

    def toggle(self):
        self.acik = not self.acik
        self.anim.stop()
        
        ok = "⌄" if self.acik else "›"
        self.btn_baslik.setText(f"{self.baslik_metin}   {ok}")

        if self.acik:
            self.btn_baslik.setStyleSheet("""
                QPushButton {
                    background-color: #242438;
                    color: #89b4fa;
                    text-align: left;
                    padding: 13px 18px;
                    font-size: 14px;
                    font-weight: bold;
                    border: 1px solid #313244;
                    border-top-left-radius: 8px;
                    border-top-right-radius: 8px;
                    border-bottom-left-radius: 0px;
                    border-bottom-right-radius: 0px;
                }
                QPushButton:hover {
                    background-color: #2b2b42;
                }
            """)
            self.icerik_frame.setVisible(True)
            self.icerik_frame.setMaximumHeight(0)
            hedef_yukseklik = self.icerik_layout.sizeHint().height() + 35
            self.anim.setStartValue(0)
            self.anim.setEndValue(hedef_yukseklik)
        else:
            self.btn_baslik.setStyleSheet("""
                QPushButton {
                    background-color: #181825;
                    color: #cdd6f4;
                    text-align: left;
                    padding: 13px 18px;
                    font-size: 14px;
                    font-weight: bold;
                    border: 1px solid #313244;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #242438;
                    border-color: #89b4fa;
                    color: #ffffff;
                }
            """)
            self.anim.setStartValue(self.icerik_frame.height())
            self.anim.setEndValue(0)

        self.anim.start()

    def animasyon_bitti(self):
        if self.acik:
            self.icerik_frame.setMaximumHeight(16777215)
        else:
            self.icerik_frame.setVisible(False)

# --- GEÇİCİ DOSYA ÖNİZLEME PENCERESİ (KAPATILINCA OTOMATİK SİLİNİR) ---
class DosyaOnizlemeDialog(QDialog):
    def __init__(self, dosya_yolu: Path, dosya_bilgi: dict, parent=None):
        super().__init__(parent)
        self.dosya_yolu = Path(dosya_yolu)
        self.dosya_bilgi = dosya_bilgi
        self.setWindowTitle(f"Dosya Önizleme - {dosya_bilgi.get('ad', 'Dosya')}")
        self.resize(760, 560)
        self.setStyleSheet(STYLE_SHEET)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Üst Bilgi Barı
        ust_bar = QFrame()
        ust_bar.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 8px; padding: 6px;")
        ub_lay = QHBoxLayout(ust_bar)
        ub_lay.setContentsMargins(12, 6, 12, 6)
        
        lbl_ad = QLabel(f"<b>{dosya_bilgi.get('ad', '')}</b>")
        lbl_ad.setStyleSheet("font-size: 14px; color: #89b4fa;")
        ub_lay.addWidget(lbl_ad)
        
        lbl_boyut = QLabel(f"Boyut: {dosya_bilgi.get('boyut_str', '')}")
        lbl_boyut.setStyleSheet("font-size: 12px; color: #a6adc8;")
        ub_lay.addWidget(lbl_boyut)
        
        ub_lay.addStretch()
        
        btn_sistemle_ac = QPushButton("Sistemle Aç")
        btn_sistemle_ac.setObjectName("KucukBtn")
        btn_sistemle_ac.clicked.connect(self.sistemle_ac)
        ub_lay.addWidget(btn_sistemle_ac)
        
        layout.addWidget(ust_bar)

        # İçerik Alanı
        uzanti = dosya_bilgi.get("uzanti", "").lower()
        metin_uzantilari = [
            ".txt", ".py", ".json", ".csv", ".log", ".md", ".html", 
            ".xml", ".ini", ".yaml", ".yml", ".sh", ".bat", ".css", 
            ".js", ".c", ".cpp", ".h", ".sql"
        ]
        resim_uzantilari = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".svg"]

        if uzanti in resim_uzantilari:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("background-color: #11111b; border: 1px solid #313244; border-radius: 8px;")
            lbl_resim = QLabel()
            lbl_resim.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pix = QPixmap(str(self.dosya_yolu))
            if not pix.isNull():
                if pix.width() > 700 or pix.height() > 460:
                    pix = pix.scaled(700, 460, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                lbl_resim.setPixmap(pix)
            else:
                lbl_resim.setText("Resim yüklenemedi veya bozuk format.")
                lbl_resim.setStyleSheet("color: #f38ba8;")
            scroll.setWidget(lbl_resim)
            layout.addWidget(scroll, 1)

        elif uzanti in metin_uzantilari:
            self.txt_icerik = QTextEdit()
            self.txt_icerik.setReadOnly(True)
            self.txt_icerik.setStyleSheet("""
                QTextEdit {
                    background-color: #11111b;
                    color: #cdd6f4;
                    border: 1px solid #313244;
                    border-radius: 8px;
                    font-family: 'Consolas', 'Courier New', monospace;
                    font-size: 13px;
                    padding: 10px;
                }
            """)
            try:
                with open(self.dosya_yolu, "r", encoding="utf-8", errors="replace") as f:
                    metin = f.read(500000)
                    if len(metin) >= 500000:
                        metin += "\n\n--- [DOSYA ÇOK UZUN, İLK 500 KB GÖSTERİLİYOR] ---"
                    self.txt_icerik.setPlainText(metin)
            except Exception as e:
                self.txt_icerik.setPlainText(f"Metin okunamadı: {str(e)}")
            layout.addWidget(self.txt_icerik, 1)

        else:
            kutu_bilgi = QFrame()
            kutu_bilgi.setStyleSheet("background-color: #11111b; border: 1px solid #313244; border-radius: 8px;")
            kb_lay = QVBoxLayout(kutu_bilgi)
            kb_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            lbl_uyari = QLabel(f"Bu dosya türü ({uzanti or 'Bilinmiyor'}) doğrudan metin/resim olarak görüntülenemez.")
            lbl_uyari.setStyleSheet("color: #a6adc8; font-size: 14px; margin-bottom: 10px;")
            kb_lay.addWidget(lbl_uyari)
            
            btn_ac = QPushButton("Varsayılan Sistem Uygulamasıyla Aç")
            btn_ac.setObjectName("ActionBtn")
            btn_ac.setFixedWidth(280)
            btn_ac.clicked.connect(self.sistemle_ac)
            kb_lay.addWidget(btn_ac)
            
            layout.addWidget(kutu_bilgi, 1)

        # Alt Butonlar
        alt_lay = QHBoxLayout()
        lbl_bilgi_not = QLabel("Not: Bu pencere kapandığında geçici indirilen dosya diskten otomatik olarak silinir.")
        lbl_bilgi_not.setStyleSheet("color: #6c7086; font-size: 11px;")
        alt_lay.addWidget(lbl_bilgi_not)
        alt_lay.addStretch()

        btn_kapat = QPushButton("Kapat ve Temizle")
        btn_kapat.setObjectName("ActionBtn")
        btn_kapat.clicked.connect(self.close)
        alt_lay.addWidget(btn_kapat)
        layout.addLayout(alt_lay)

    def sistemle_ac(self):
        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.dosya_yolu)))
        except Exception as e:
            QMessageBox.warning(self, "Hata", f"Dosya açılamadı: {str(e)}")

    def closeEvent(self, event):
        # Kapatılınca geçici dosyayı anında sil (Kullanıcının isteği: gereksiz yer kaplamasın)
        try:
            if self.dosya_yolu.exists():
                self.dosya_yolu.unlink()
        except Exception:
            pass
        event.accept()

# --- ÇOKLU KLASÖR YÜKLEME MOTORU ---
class CokluKlasorYuklemeIslemi(QThread):
    durum_guncelle = pyqtSignal(str)
    genel_ilerleme = pyqtSignal(int)
    dosya_ilerleme = pyqtSignal(int, str)
    tamamlandi = pyqtSignal(bool, str)

    def __init__(self, klasorler, sunucu_url, bilet):
        super().__init__()
        self.klasorler = klasorler
        self.sunucu_url = sunucu_url
        self.bilet = bilet
        self._calisiyor = True

    def durdur(self):
        """Yükleme işlemini güvenli şekilde durdurur."""
        self._calisiyor = False

    def run(self):
        try:
            toplam_boyut = 0
            tum_dosyalar = []
            
            # Klasörleri tara ve toplam boyutu hesapla
            for klsr in self.klasorler:
                if not os.path.exists(klsr):
                    continue
                ana_klasor_adi = os.path.basename(os.path.normpath(klsr))
                klasor_hash = hashlib.md5(os.path.abspath(klsr).encode("utf-8")).hexdigest()[:6]
                
                for kok, _, dosyalar in os.walk(klsr):
                    for d in dosyalar:
                        tam_dosya_yolu = os.path.join(kok, d)
                        try:
                            boyut = os.path.getsize(tam_dosya_yolu)
                        except (OSError, PermissionError):
                            boyut = 0
                        toplam_boyut += boyut
                        goreceli_yol = os.path.relpath(tam_dosya_yolu, klsr)
                        sunucu_dosya_adi = os.path.join(ana_klasor_adi, goreceli_yol).replace("\\", "/")
                        
                        dosya_id = f"klasor_{klasor_hash}_{ana_klasor_adi}_{goreceli_yol}".replace("\\", "_").replace("/", "_")
                        tum_dosyalar.append({
                            "tam_yol": tam_dosya_yolu,
                            "boyut": boyut,
                            "sunucu_adi": sunucu_dosya_adi,
                            "dosya_id": dosya_id,
                            "dosya_kisa_ad": d
                        })

            if not tum_dosyalar:
                self.durum_guncelle.emit("Yüklenecek dosya bulunamadı veya klasör boş.")
                self.genel_ilerleme.emit(100)
                self.dosya_ilerleme.emit(100, "Tamamlandı")
                self.tamamlandi.emit(True, "Klasör boş, işlem tamamlandı.")
                return

            yuklenen_toplam = 0

            for d_bilgi in tum_dosyalar:
                if not self._calisiyor:
                    self.durum_guncelle.emit("Yükleme işlemi kullanıcı tarafından iptal edildi.")
                    self.tamamlandi.emit(False, "İşlem iptal edildi.")
                    return

                tam_dosya_yolu = d_bilgi["tam_yol"]
                dosya_boyutu = d_bilgi["boyut"]
                sunucu_dosya_adi = d_bilgi["sunucu_adi"]
                dosya_id = d_bilgi["dosya_id"]
                dosya_kisa_ad = d_bilgi["dosya_kisa_ad"]

                # Sunucuda dosya durumunu sorgula
                try:
                    resp = requests.get(
                        f"{self.sunucu_url}/yedek-sorgula", 
                        headers=self.bilet, 
                        params={"dosya_id": dosya_id, "dosya_adi": sunucu_dosya_adi},
                        timeout=TIMEOUT
                    )
                    kaldigi_yer = resp.json().get("yuklenen_boyut", 0) if resp.status_code == 200 else 0
                except requests.RequestException:
                    kaldigi_yer = 0

                # 0 Baytlık dosya desteği
                if dosya_boyutu == 0:
                    try:
                        data = {"dosya_id": dosya_id, "dosya_adi": sunucu_dosya_adi, "bastan_basla": "true"}
                        files = {"gelen_dosya": (dosya_kisa_ad, b"")}
                        requests.post(f"{self.sunucu_url}/yedek-parca-yukle", headers=self.bilet, data=data, files=files, timeout=TIMEOUT)
                    except Exception as e:
                        self.tamamlandi.emit(False, f"0 Bayt dosya yüklenemedi: {str(e)}")
                    continue

                # Zaten tam yüklüyse atla
                if kaldigi_yer >= dosya_boyutu:
                    yuklenen_toplam += dosya_boyutu
                    yuzde = int((yuklenen_toplam / toplam_boyut) * 100) if toplam_boyut > 0 else 100
                    self.genel_ilerleme.emit(yuzde)
                    continue

                bastan_basla = False
                if kaldigi_yer > dosya_boyutu:
                    kaldigi_yer = 0
                    bastan_basla = True

                yuklenen_toplam += kaldigi_yer

                try:
                    with open(tam_dosya_yolu, "rb") as f:
                        f.seek(kaldigi_yer)
                        chunk_size = 1024 * 1024  # 1 MB
                        dosya_ici_yuklenen = kaldigi_yer

                        while self._calisiyor:
                            parca = f.read(chunk_size)
                            if not parca:
                                break

                            data = {
                                "dosya_id": dosya_id, 
                                "dosya_adi": sunucu_dosya_adi, 
                                "bastan_basla": "true" if bastan_basla else "false"
                            }
                            bastan_basla = False

                            files = {"gelen_dosya": (dosya_kisa_ad, parca)}
                            
                            try:
                                post_resp = requests.post(
                                    f"{self.sunucu_url}/yedek-parca-yukle", 
                                    headers=self.bilet, 
                                    data=data, 
                                    files=files, 
                                    timeout=TIMEOUT + 10
                                )
                            except requests.RequestException as e:
                                self.durum_guncelle.emit("Bağlantı kesildi! Sunucuya ulaşılamıyor.")
                                self.tamamlandi.emit(False, f"Ağ bağlantısı koptu ({str(e)})")
                                return

                            if post_resp.status_code == 200:
                                parca_boyutu = len(parca)
                                dosya_ici_yuklenen += parca_boyutu
                                yuklenen_toplam += parca_boyutu

                                d_yuzde = int((dosya_ici_yuklenen / dosya_boyutu) * 100) if dosya_boyutu > 0 else 100
                                g_yuzde = int((yuklenen_toplam / toplam_boyut) * 100) if toplam_boyut > 0 else 100

                                self.dosya_ilerleme.emit(d_yuzde, dosya_kisa_ad[:25] + "...")
                                self.genel_ilerleme.emit(g_yuzde)
                            else:
                                hata_metni = f"Sunucu parça yüklemeyi reddetti (HTTP {post_resp.status_code})"
                                self.durum_guncelle.emit(hata_metni)
                                self.tamamlandi.emit(False, hata_metni)
                                return
                except (PermissionError, OSError) as e:
                    self.durum_guncelle.emit(f"Dosya okunamadı: {dosya_kisa_ad}")
                    continue

            if self._calisiyor:
                self.durum_guncelle.emit("Tüm işlemler başarıyla tamamlandı!")
                self.genel_ilerleme.emit(100)
                self.dosya_ilerleme.emit(100, "Bitti")
                self.tamamlandi.emit(True, "Yükleme tamamlandı.")
            else:
                self.durum_guncelle.emit("Yükleme işlemi durduruldu.")
                self.tamamlandi.emit(False, "İşlem kullanıcı tarafından durduruldu.")

        except Exception as e:
            self.durum_guncelle.emit(f"Sistem Hatası: {str(e)}")
            self.tamamlandi.emit(False, f"Beklenmeyen Hata: {str(e)}")

# --- GRAFİKLER ---
class DaireselDiskGrafigi(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120) 
        self._current_yuzde = 0.0 
        self.merkez_metin = "Bekle"
        self.anim = QPropertyAnimation(self, b"drawProgress")
        self.anim.setDuration(1200)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def drawProgress(self): 
        return self._current_yuzde

    @drawProgress.setter
    def drawProgress(self, value):
        self._current_yuzde = value
        self.update()

    def guncelle_grafik(self, bos_gb, toplam_gb):
        if toplam_gb > 0:
            hedef = (toplam_gb - bos_gb) / toplam_gb
            self.merkez_metin = f"{bos_gb:.1f} GB\nBoş"
        else:
            hedef = 0.0
            self.merkez_metin = "Bağlantı\nYok"
        self.anim.stop()
        self.anim.setStartValue(self._current_yuzde)
        self.anim.setEndValue(hedef)
        self.anim.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c, r, pen_w = 60, 48, 12
        rect = QRectF(c - r, c - r, 2*r, 2*r)
        
        painter.setPen(QPen(QColor("#2a2b3d"), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 0, 360 * 16)
        
        painter.setPen(QPen(QColor("#89b4fa"), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 90 * 16, int(-self._current_yuzde * 360 * 16))
        
        painter.setPen(QColor("#ffffff"))
        painter.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.merkez_metin)

class YilanLogoWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(200, 200) 
        self.yilan_offset = 0.0
        self.nokta_mesafe = 0.0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.anim)
        self.timer.start(16) 

    def anim(self):
        self.yilan_offset -= 0.15  
        self.nokta_mesafe += 0.8   
        self.update() 

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing) 
        path = QPainterPath()
        path.addRoundedRect(QRectF(20, 20, 160, 160), 45, 45)
        path_len = path.length()
        pen_w = 15

        p.setPen(QPen(QColor("#2a2b3d"), 1))
        p.drawPath(path)

        def ciz(renk, uz, off):
            pen = QPen(QColor(renk), pen_w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap) 
            pen.setDashPattern([uz, (path_len/pen_w) - uz])
            pen.setDashOffset(self.yilan_offset + off)
            p.setPen(pen)
            p.drawPath(path)

        ciz("#112f52", 18, 0)      
        ciz("#1f538d", 12, -6)     
        ciz("#89b4fa", 5, -13)     

# --- ANA UYGULAMA ---
class BulutSistemiApp(QMainWindow):
    zamanlayici_tetiklendi = pyqtSignal(str, list)
    ornek = None

    def __init__(self):
        super().__init__()
        BulutSistemiApp.ornek = self
        self.setWindowTitle("Bulut OS - Depolama & Yedekleme") 
        self.resize(960, 650)
        
        # Dinamik Sunucu Ayarları
        self.sunucu_url = ILK_AYARLAR["sunucu_url"]
        self.sunucu_sifre = ILK_AYARLAR["sifre"]
        self.bilet = {"gelen-sifre": self.sunucu_sifre}

        self.secilen_klasorler = []
        self.manuel_klasor_yolu = ""
        self.aktif_motor = None
        self.manuel_motor = None
        self.sayfa_gecmisi = [] 
        self.aktif_gorev_id = None
        self.bekleyen_pano_gorev_id = None
        
        # Dosya Yöneticisi Gezgini Durumu
        self.mevcut_dizin_yolu = ""
        self.mevcut_dizin_ogeleri = []
        
        # Hata Kayıtları Geçmişi
        self.hata_kayitlari = []
        self.son_baglanti_bilgisi = {
            "basarili": False,
            "hata_kodu": "Bilinmiyor",
            "hata_aciklamasi": "Henüz bağlantı testi yapılmadı."
        }
        
        # Sinyal bağlantısı (Thread-Safe GUI Güncellemesi)
        self.zamanlayici_tetiklendi.connect(self.gorev_tetikle)

        self.scheduler = BackgroundScheduler()
        self.scheduler.start()

        self.ana_pencere_stack = QStackedWidget()
        self.setCentralWidget(self.ana_pencere_stack)

        # Splash Sayfası
        self.splash_sayfa = QWidget()
        splash_layout = QVBoxLayout(self.splash_sayfa)
        self.splash_logo = YilanLogoWidget()
        splash_layout.addWidget(self.splash_logo, alignment=Qt.AlignmentFlag.AlignCenter)
        self.ana_pencere_stack.addWidget(self.splash_sayfa)

        # Ana Uygulama Gövdesi
        self.main_app_widget = QWidget()
        self.ana_layout = QVBoxLayout(self.main_app_widget)
        self.ana_layout.setContentsMargins(0, 0, 0, 0)
        self.ana_layout.setSpacing(0)
        self.ana_pencere_stack.addWidget(self.main_app_widget)

        # Top Bar
        self.top_bar = QFrame()
        self.top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(self.top_bar)
        
        self.btn_geri = QPushButton("◀ Geri")
        self.btn_geri.setObjectName("NavBtn")
        self.btn_geri.clicked.connect(self.sayfa_geri)
        self.btn_geri.setToolTip("Geri Dön")
        
        self.btn_ana_menu = QPushButton("Ana Menü")
        self.btn_ana_menu.setObjectName("NavBtn")
        self.btn_ana_menu.clicked.connect(lambda: self.sayfa_degistir(0, kaydet=False))
        self.btn_ana_menu.setToolTip("Ana Menüye Git")
        
        self.btn_menu = QPushButton("☰")
        self.btn_menu.setObjectName("MenuBtn")
        self.btn_menu.setFixedSize(40, 40)
        self.btn_menu.clicked.connect(self.menu_tetikle)
        
        top_layout.addWidget(self.btn_geri)
        top_layout.addWidget(self.btn_ana_menu)
        top_layout.addStretch()
        top_layout.addWidget(self.btn_menu)
        
        self.ana_layout.addWidget(self.top_bar)

        # İçerik Alanı
        icerik_widget = QWidget()
        icerik_layout = QHBoxLayout(icerik_widget)
        icerik_layout.setContentsMargins(0,0,0,0)
        icerik_layout.setSpacing(0)
        self.ana_layout.addWidget(icerik_widget)

        self.sayfalar = QStackedWidget()
        icerik_layout.addWidget(self.sayfalar)
        
        # Sayfalar
        self.sayfalar.addWidget(self.ana_sayfa_olustur())               # 0: Genel Bakış
        self.sayfalar.addWidget(self.dosya_yoneticisi_sayfasi_olustur())# 1: Dosya Yöneticisi
        self.sayfalar.addWidget(self.oto_yedekleme_sayfasi_olustur())   # 2: Otomatik Yedekleme
        self.sayfalar.addWidget(self.manuel_yukleme_sayfasi_olustur())  # 3: Manuel Yükleme
        self.sayfalar.addWidget(self.gorevler_sayfasi_olustur())        # 4: İşlemler ve Görevler
        self.sayfalar.addWidget(self.sunucu_ayarlari_sayfasi_olustur()) # 5: Sunucu Ayarları
        self.sayfalar.addWidget(self.hakkinda_sayfasi_olustur())        # 6: Hakkında

        # Sidebar (Emojisiz, sade ve beyaz/açık renk metinli)
        self.sidebar = QFrame()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setMaximumWidth(0) 
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 20, 0, 0)
        self.sidebar_layout.setSpacing(5)
        
        btn1 = QPushButton("Genel Bakış")
        btn1.setObjectName("SidebarBtn")
        btn1.clicked.connect(lambda: self.sayfa_degistir(0))

        btn_depo = QPushButton("Dosya Yöneticisi")
        btn_depo.setObjectName("SidebarBtn")
        btn_depo.clicked.connect(lambda: self.sayfa_degistir(1))
        
        btn2 = QPushButton("Otomatik Yedekleme")
        btn2.setObjectName("SidebarBtn")
        btn2.clicked.connect(lambda: self.sayfa_degistir(2))
        
        btn3 = QPushButton("Manuel Yükleme")
        btn3.setObjectName("SidebarBtn")
        btn3.clicked.connect(lambda: self.sayfa_degistir(3))
        
        btn4 = QPushButton("İşlemler ve Görevler")
        btn4.setObjectName("SidebarBtn")
        btn4.clicked.connect(lambda: self.sayfa_degistir(4))

        btn5 = QPushButton("Sunucu Ayarları")
        btn5.setObjectName("SidebarBtn")
        btn5.clicked.connect(lambda: self.sayfa_degistir(5))

        btn6 = QPushButton("Hakkında")
        btn6.setObjectName("SidebarBtn")
        btn6.clicked.connect(lambda: self.sayfa_degistir(6))
        
        self.sidebar_layout.addWidget(btn1)
        self.sidebar_layout.addWidget(btn_depo)
        self.sidebar_layout.addWidget(btn2)
        self.sidebar_layout.addWidget(btn3)
        self.sidebar_layout.addWidget(btn4)
        self.sidebar_layout.addWidget(btn5)
        self.sidebar_layout.addWidget(btn6)
        self.sidebar_layout.addStretch() 
        icerik_layout.addWidget(self.sidebar)

        # Alt Sabit Durum Çubuğu (Her sayfada en altta görünen sunucu durumu)
        self.bottom_bar = QFrame()
        self.bottom_bar.setObjectName("BottomBar")
        bottom_layout = QHBoxLayout(self.bottom_bar)
        bottom_layout.setContentsMargins(15, 2, 15, 2)
        bottom_layout.setSpacing(10)

        self.lbl_global_ip = QLabel("Sunucu Adresi: -")
        self.lbl_global_ip.setStyleSheet("font-size: 11px; color: #cdd6f4; font-weight: bold;")
        bottom_layout.addWidget(self.lbl_global_ip)

        lbl_ayirici = QLabel("•")
        lbl_ayirici.setStyleSheet("color: #45475a; font-size: 11px;")
        bottom_layout.addWidget(lbl_ayirici)

        self.lbl_global_durum = QLabel("Durum: Kontrol ediliyor...")
        self.lbl_global_durum.setStyleSheet("font-size: 11px; color: #a6adc8;")
        bottom_layout.addWidget(self.lbl_global_durum)

        self.btn_global_hata = QPushButton("Hata Detayı")
        self.btn_global_hata.setObjectName("KucukBtn")
        self.btn_global_hata.setVisible(False)
        self.btn_global_hata.clicked.connect(self.hata_detay_goster)
        bottom_layout.addWidget(self.btn_global_hata)

        bottom_layout.addStretch()
        self.ana_layout.addWidget(self.bottom_bar)

        self.opacity_effect = QGraphicsOpacityEffect(self.splash_sayfa)
        self.splash_sayfa.setGraphicsEffect(self.opacity_effect)
        QTimer.singleShot(1800, self.splash_erime) 

    def splash_erime(self):
        self.fade_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_anim.setDuration(600) 
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.finished.connect(self.baslat)
        self.fade_anim.start()

    def baslat(self):
        self.ana_pencere_stack.setCurrentIndex(1)
        self.splash_logo.timer.stop() 

        # İlk Kurulum Kontrolü (Ayar dosyası yoksa veya sunucu adresi henüz girilmemişse)
        if not os.path.exists(AYAR_DOSYASI) or not self.sunucu_url:
            dialog = IlkKurulumDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                guncel_ayar = ayar_yukle()
                self.sunucu_url = guncel_ayar.get("sunucu_url", "")
                self.sunucu_sifre = guncel_ayar.get("sifre", "")
                self.bilet = {"gelen-sifre": self.sunucu_sifre}
                if hasattr(self, 'txt_sunucu_url'):
                    self.txt_sunucu_url.setText(self.sunucu_url)
                if hasattr(self, 'txt_sunucu_sifre'):
                    self.txt_sunucu_sifre.setText(self.sunucu_sifre)
            else:
                # Kullanıcı vazgeçtiyse doğrudan Sunucu Ayarları sayfasına yönlendir
                self.sayfa_degistir(5, kaydet=False)

        if self.sunucu_url:
            self.sunucu_senkronizasyonu()
        else:
            self.sunucu_durum_kartini_guncelle()

    def sunucu_senkronizasyonu(self):
        """Sunucu disk durumunu ve görev listesini güvenli çeker, bağlantı durumunu günceller."""
        baglanti_basarili = False
        hata_kodu = ""
        hata_aciklamasi = ""

        try:
            cevap = requests.get(f"{self.sunucu_url}/", headers={"gelen-sifre": self.sunucu_sifre}, timeout=TIMEOUT)
            if cevap.status_code == 200:
                v = cevap.json()
                self.disk_grafik.guncelle_grafik(v.get("bos_alan", 0) / (1024**3), v.get("toplam", 0) / (1024**3))
                baglanti_basarili = True
            elif cevap.status_code == 401:
                hata_kodu = "HTTP 401 (Yetkisiz Erişim)"
                hata_aciklamasi = "Sunucu şifresi hatalı! 'Sunucu Ayarları' bölümünden doğru şifreyi giriniz."
                self.disk_grafik.guncelle_grafik(0, 0)
            elif cevap.status_code == 429:
                hata_kodu = "HTTP 429 (Güvenlik Engeli)"
                detay = "Çok fazla hatalı şifre girildiği için sunucu bu IP adresini geçici olarak (15 dk) engelledi."
                try:
                    detay = cevap.json().get("detail", detay)
                except Exception:
                    pass
                hata_aciklamasi = detay
                self.disk_grafik.guncelle_grafik(0, 0)
            else:
                hata_kodu = f"HTTP {cevap.status_code}"
                hata_aciklamasi = f"Sunucu beklenmeyen durum kodu döndürdü ({cevap.status_code})."
                self.disk_grafik.guncelle_grafik(0, 0)
        except requests.exceptions.ConnectTimeout:
            hata_kodu = "Zaman Aşımı (Timeout)"
            hata_aciklamasi = (
                "Sunucuya 10 saniye içinde ulaşılamadı. Port engellenmiş olabilir!\n"
                "• Oracle Cloud / AWS: Web panelinde 'Security Lists -> Ingress Rules' bölümünden TCP 8000 portunu (0.0.0.0/0) açtığınızdan emin olun.\n"
                "• Linux Güvenlik Duvarı: Sunucuda 'sudo ufw allow 8000/tcp' komutunun çalıştırıldığını kontrol edin."
            )
            self.disk_grafik.guncelle_grafik(0, 0)
        except requests.exceptions.ConnectionError:
            hata_kodu = "Bağlantı Hatası (Connection Error)"
            hata_aciklamasi = (
                "Sunucu adresine veya porta bağlanılamadı.\n"
                "• Sunucu servisinin açık olduğunu doğrulayın ('systemctl status bulut-depo' veya 'python server.py').\n"
                "• Sunucu 0.0.0.0 üzerinde mi dinliyor? (127.0.0.1 dışarıdan erişilemez).\n"
                "• Sunucu IP adresini ve portunu doğru yazdığınızdan emin olun."
            )
            self.disk_grafik.guncelle_grafik(0, 0)
        except Exception as e:
            hata_kodu = "Bilinmeyen Ağ Hatası"
            hata_aciklamasi = str(e)
            self.disk_grafik.guncelle_grafik(0, 0)

        self.son_baglanti_bilgisi = {
            "basarili": baglanti_basarili,
            "hata_kodu": hata_kodu,
            "hata_aciklamasi": hata_aciklamasi
        }
        self.sunucu_durum_kartini_guncelle()

        if baglanti_basarili:
            self.gorevleri_getir_ve_kur()
        else:
            if not (self.aktif_motor and self.aktif_motor.isRunning()):
                self.lbl_pano_durum.setText("Sunucuya bağlanılamadı. Otomatik işlemler kontrol edilemiyor.")
                self.btn_ertele.setVisible(False)
            self.hata_kaydi_ekle("Sunucu Bağlantısı", f"{hata_kodu} - {hata_aciklamasi[:50]}")

    def sunucu_durum_kartini_guncelle(self):
        """Sunucu durum bilgisini hem ana sayfadaki karta hem de her sayfada görünen alt çubuğa yansıtır."""
        temiz_url = self.sunucu_url.replace("http://", "").replace("https://", "").rstrip("/")
        
        # Ana Sayfa Sol Kart
        if hasattr(self, 'lbl_kart_ip'):
            self.lbl_kart_ip.setText(f"Adres: {temiz_url}")
        
        # Her Menüde Görünen Alt Çubuk
        if hasattr(self, 'lbl_global_ip'):
            self.lbl_global_ip.setText(f"Sunucu Adresi: {temiz_url}")
        
        if self.son_baglanti_bilgisi["basarili"]:
            durum_metni = "Durum: Bağlandı"
            stil = "color: #a6e3a1; font-weight: bold; font-size: 11px;"
            if hasattr(self, 'lbl_kart_durum'):
                self.lbl_kart_durum.setText(durum_metni)
                self.lbl_kart_durum.setStyleSheet(stil)
                self.btn_kart_hata.setVisible(False)
            if hasattr(self, 'lbl_global_durum'):
                self.lbl_global_durum.setText(durum_metni)
                self.lbl_global_durum.setStyleSheet(stil)
                self.btn_global_hata.setVisible(False)
        else:
            durum_metni = "Durum: Bağlanılamadı"
            stil = "color: #f38ba8; font-weight: bold; font-size: 11px;"
            if hasattr(self, 'lbl_kart_durum'):
                self.lbl_kart_durum.setText(durum_metni)
                self.lbl_kart_durum.setStyleSheet(stil)
                self.btn_kart_hata.setVisible(True)
            if hasattr(self, 'lbl_global_durum'):
                self.lbl_global_durum.setText(durum_metni)
                self.lbl_global_durum.setStyleSheet(stil)
                self.btn_global_hata.setVisible(True)

    def hata_detay_goster(self):
        info = self.son_baglanti_bilgisi
        QMessageBox.warning(
            self,
            "Sunucu Bağlantı Teşhisi",
            f"Sunucuya bağlanılamadı!\n\n"
            f"Hedef Adres: {self.sunucu_url}\n"
            f"Hata Kodu: {info['hata_kodu']}\n\n"
            f"Teşhis & Açıklama:\n{info['hata_aciklamasi']}\n\n"
            f"Bulut / VPS Sunucu Çözüm Adımları:\n"
            f"1. Oracle Cloud / AWS kullanıyorsanız web panelinden 8000 portuna Ingress izni verin.\n"
            f"2. Sunucu terminalinde 'sudo ufw allow 8000/tcp' komutunun çalıştırıldığını kontrol edin.\n"
            f"3. Sunucu servisinin çalıştığından ('systemctl status bulut-depo') emin olun.\n"
            f"4. 'Sunucu Ayarları' menüsünden IP adresi ve şifrenizi doğrulayın."
        )

    def hata_kaydi_ekle(self, islem, neden):
        """Hata geçmişine yeni kayıt ekler."""
        saat = datetime.now().strftime("%H:%M:%S")
        kayit = f"[{saat}] {islem}: {neden}"
        self.hata_kayitlari.insert(0, kayit)
        if len(self.hata_kayitlari) > 20:
            self.hata_kayitlari.pop()
        self.hata_listesini_guncelle()

    def hata_listesini_guncelle(self):
        self.liste_hatalar.clear()
        if not self.hata_kayitlari:
            self.liste_hatalar.addItem("(Kayıtlı işlem hatası yok)")
        else:
            for k in self.hata_kayitlari:
                self.liste_hatalar.addItem(k)

    def hata_kayitlarini_temizle(self):
        self.hata_kayitlari.clear()
        self.hata_listesini_guncelle()

    # --- NAVİGASYON ---
    def sayfa_degistir(self, index, kaydet=True):
        if kaydet and self.sayfalar.currentIndex() != index:
            self.sayfa_gecmisi.append(self.sayfalar.currentIndex())
        self.sayfalar.setCurrentIndex(index)
        if index == 1:
            self.depo_dizinini_yukle()
        elif index == 4: 
            self.gorevleri_arayuze_ciz()
        if self.sidebar.width() > 0: 
            self.menu_tetikle()
        
    def sayfa_geri(self):
        if self.sayfa_gecmisi:
            eski = self.sayfa_gecmisi.pop()
            self.sayfalar.setCurrentIndex(eski)

    def menu_tetikle(self):
        genislik = self.sidebar.width()
        hedef = 240 if genislik == 0 else 0
        self.animasyon = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.animasyon.setDuration(250) 
        self.animasyon.setStartValue(genislik)
        self.animasyon.setEndValue(hedef)
        self.animasyon.setEasingCurve(QEasingCurve.Type.InOutQuart) 
        self.animasyon.start()

    # --- SAYFALAR ---
    def ana_sayfa_olustur(self):
        sayfa = QWidget()
        layout = QHBoxLayout(sayfa)
        layout.setContentsMargins(35, 30, 35, 30)
        
        # Sol Taraf: Disk Grafiği ve Altında Kompakt Sunucu Durumu
        sol_layout = QVBoxLayout()
        sol_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        
        self.disk_grafik = DaireselDiskGrafigi()
        sol_layout.addWidget(self.disk_grafik)
        
        btn_yenile = QPushButton("Durumu Yenile")
        btn_yenile.setFixedWidth(130)
        btn_yenile.clicked.connect(self.sunucu_senkronizasyonu)
        sol_layout.addWidget(btn_yenile)
        
        sol_layout.addSpacing(16)

        # Dairesel Grafik ile Sunucu Durum Kartını Ayıran Çizgi
        cizgi_sol_grafik = QFrame()
        cizgi_sol_grafik.setFrameShape(QFrame.Shape.HLine)
        cizgi_sol_grafik.setStyleSheet("color: #313244; max-height: 1px;")
        cizgi_sol_grafik.setFixedWidth(160)
        sol_layout.addWidget(cizgi_sol_grafik)

        sol_layout.addSpacing(16)

        # Kompakt Sunucu Durum Kartı (Gözü yormayan boyutlandırma)
        kart_frame = QFrame()
        kart_frame.setStyleSheet("""
            QFrame {
                background-color: #181825;
                border: 1px solid #313244;
                border-radius: 8px;
            }
        """)
        kart_frame.setFixedWidth(170)
        kart_lay = QVBoxLayout(kart_frame)
        kart_lay.setContentsMargins(10, 10, 10, 10)
        kart_lay.setSpacing(5)

        lbl_kart_baslik = QLabel("Sunucu Bağlantısı")
        lbl_kart_baslik.setStyleSheet("font-size: 11px; font-weight: bold; color: #89b4fa;")
        kart_lay.addWidget(lbl_kart_baslik)

        self.lbl_kart_ip = QLabel("Adres: -")
        self.lbl_kart_ip.setStyleSheet("font-size: 10px; color: #a6adc8;")
        self.lbl_kart_ip.setWordWrap(True)
        kart_lay.addWidget(self.lbl_kart_ip)

        durum_satir = QHBoxLayout()
        self.lbl_kart_durum = QLabel("Kontrol ediliyor...")
        self.lbl_kart_durum.setStyleSheet("font-size: 11px; color: #a6adc8;")
        durum_satir.addWidget(self.lbl_kart_durum)

        self.btn_kart_hata = QPushButton("Hata Detayı")
        self.btn_kart_hata.setObjectName("KucukBtn")
        self.btn_kart_hata.setVisible(False)
        self.btn_kart_hata.clicked.connect(self.hata_detay_goster)
        durum_satir.addWidget(self.btn_kart_hata)

        kart_lay.addLayout(durum_satir)
        sol_layout.addWidget(kart_frame)
        sol_layout.addStretch()
        
        # Ortadaki Dikey Ayırıcı Çizgi
        cizgi = QFrame()
        cizgi.setFrameShape(QFrame.Shape.VLine)
        cizgi.setStyleSheet("color: #313244;")
        
        # Sağ Taraf: İşlem Panosu ve Altında Hatalı İşlemler
        sag_layout = QVBoxLayout()
        sag_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        lbl_pano = QLabel("İşlem Panosu")
        lbl_pano.setObjectName("KucukBaslik")
        sag_layout.addWidget(lbl_pano)
        
        # Durum Metni ve Yanındaki Erteleme Butonu
        durum_satir_pano = QHBoxLayout()
        self.lbl_pano_durum = QLabel("Sistem Hazır. Bekleyen otomatik işlem yok.")
        self.lbl_pano_durum.setWordWrap(True)
        durum_satir_pano.addWidget(self.lbl_pano_durum, 1)

        self.btn_ertele = QPushButton("◷ Ertele")
        self.btn_ertele.setObjectName("ErteleBtn")
        self.btn_ertele.setVisible(False)
        self.btn_ertele.setToolTip("Bekleyen işlemin tarih ve saatini değiştir")
        self.btn_ertele.clicked.connect(self.pano_gorev_ertele)
        durum_satir_pano.addWidget(self.btn_ertele)

        sag_layout.addLayout(durum_satir_pano)
        
        sag_layout.addSpacing(12)
        sag_layout.addWidget(QLabel("Aktif Dosya İlerlemesi:"))
        self.bar_dosya = QProgressBar()
        self.bar_dosya.setValue(0)
        sag_layout.addWidget(self.bar_dosya)
        
        sag_layout.addSpacing(8)
        sag_layout.addWidget(QLabel("Genel Yedekleme İlerlemesi:"))
        self.bar_genel = QProgressBar()
        self.bar_genel.setObjectName("GenelBar")
        self.bar_genel.setValue(0)
        sag_layout.addWidget(self.bar_genel)

        sag_layout.addSpacing(10)
        self.btn_oto_durdur = QPushButton("İşlemi İptal Et")
        self.btn_oto_durdur.setObjectName("CancelBtn")
        self.btn_oto_durdur.setVisible(False)
        self.btn_oto_durdur.clicked.connect(self.aktif_islemi_iptal_et)
        sag_layout.addWidget(self.btn_oto_durdur)
        
        sag_layout.addSpacing(15)

        # Yatay Ayırıcı Çizgi
        cizgi_hata = QFrame()
        cizgi_hata.setFrameShape(QFrame.Shape.HLine)
        cizgi_hata.setStyleSheet("color: #313244; max-height: 1px;")
        sag_layout.addWidget(cizgi_hata)

        sag_layout.addSpacing(10)

        # Hata Alan İşlemler Bölümü
        hata_ust_satir = QHBoxLayout()
        lbl_hata_baslik = QLabel("Son İşlem Hataları:")
        lbl_hata_baslik.setStyleSheet("color: #f38ba8; font-weight: bold; font-size: 13px;")
        hata_ust_satir.addWidget(lbl_hata_baslik)
        hata_ust_satir.addStretch()

        btn_hata_temizle = QPushButton("Listeyi Temizle")
        btn_hata_temizle.setObjectName("KucukBtn")
        btn_hata_temizle.clicked.connect(self.hata_kayitlarini_temizle)
        hata_ust_satir.addWidget(btn_hata_temizle)
        sag_layout.addLayout(hata_ust_satir)

        self.liste_hatalar = QListWidget()
        self.liste_hatalar.setFixedHeight(95)
        self.liste_hatalar.setStyleSheet("background-color: #11111b; color: #f38ba8; border: 1px solid #313244; border-radius: 5px; font-size: 11px;")
        self.liste_hatalar.addItem("(Kayıtlı işlem hatası yok)")
        sag_layout.addWidget(self.liste_hatalar)

        sag_layout.addStretch()

        layout.addLayout(sol_layout, 1)
        layout.addWidget(cizgi)
        layout.addLayout(sag_layout, 3)
        return sayfa

    # --- DOSYA YÖNETİCİSİ SAYFASI & METOTLARI ---
    def dosya_yoneticisi_sayfasi_olustur(self):
        sayfa = QWidget()
        layout = QVBoxLayout(sayfa)
        layout.setContentsMargins(35, 30, 35, 30)
        layout.setSpacing(14)

        # Üst Başlık
        baslik = QLabel("Sunucu Dosya Yöneticisi")
        baslik.setObjectName("Baslik")
        layout.addWidget(baslik)

        aciklama = QLabel("Sunucu deposundaki (BulutDepolama) dosyaları görüntüleyin, önizleyin veya diskinize indirin.")
        aciklama.setStyleSheet("color: #a6adc8; font-size: 13px;")
        layout.addWidget(aciklama)

        # Gezinme ve Dizin Çubuğu
        nav_bar = QFrame()
        nav_bar.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 8px; padding: 4px;")
        nav_lay = QHBoxLayout(nav_bar)
        nav_lay.setContentsMargins(10, 4, 10, 4)
        nav_lay.setSpacing(8)

        self.btn_depo_yukari = QPushButton("▲ Üst Dizin")
        self.btn_depo_yukari.setObjectName("NavBtn")
        self.btn_depo_yukari.setEnabled(False)
        self.btn_depo_yukari.clicked.connect(self.depo_ust_dizine_cik)
        nav_lay.addWidget(self.btn_depo_yukari)

        self.btn_depo_yenile = QPushButton("Yenile")
        self.btn_depo_yenile.setObjectName("NavBtn")
        self.btn_depo_yenile.clicked.connect(lambda: self.depo_dizinini_yukle())
        nav_lay.addWidget(self.btn_depo_yenile)

        self.lbl_depo_yol = QLabel("Dizin: / (Kök Dizin)")
        self.lbl_depo_yol.setStyleSheet("color: #89b4fa; font-weight: bold; font-family: monospace; font-size: 13px; padding-left: 8px;")
        nav_lay.addWidget(self.lbl_depo_yol, 1)

        self.txt_depo_ara = QLineEdit()
        self.txt_depo_ara.setPlaceholderText("Dosya veya uzantı ara...")
        self.txt_depo_ara.setFixedWidth(210)
        self.txt_depo_ara.textChanged.connect(self.depo_filtrele)
        nav_lay.addWidget(self.txt_depo_ara)

        layout.addWidget(nav_bar)

        # Tablo Görünümü
        self.tablo_depo = QTableWidget()
        self.tablo_depo.setColumnCount(5)
        self.tablo_depo.setHorizontalHeaderLabels(["Öğe Adı", "Tür", "Uzantı", "Boyut", "Son Değiştirilme"])
        self.tablo_depo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo_depo.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tablo_depo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo_depo.setShowGrid(False)
        self.tablo_depo.verticalHeader().setVisible(False)
        
        header = self.tablo_depo.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.tablo_depo.setColumnWidth(1, 90)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.tablo_depo.setColumnWidth(2, 80)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.tablo_depo.setColumnWidth(3, 110)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        self.tablo_depo.setColumnWidth(4, 150)

        self.tablo_depo.cellDoubleClicked.connect(self.depo_oge_cift_tiklandi)
        layout.addWidget(self.tablo_depo, 1)

        # Alt İşlem ve Bilgi Barı
        alt_bar = QHBoxLayout()
        self.lbl_depo_durum = QLabel("Sunucu içeriği bekleniyor...")
        self.lbl_depo_durum.setStyleSheet("color: #a6adc8; font-size: 12px;")
        alt_bar.addWidget(self.lbl_depo_durum)

        alt_bar.addStretch()

        self.btn_depo_goruntule = QPushButton("Görüntüle / Önizle")
        self.btn_depo_goruntule.setObjectName("ActionBtn")
        self.btn_depo_goruntule.setToolTip("Seçili dosyayı geçici belleğe indirip önizler (Kapatılınca otomatik silinir)")
        self.btn_depo_goruntule.clicked.connect(self.depo_dosya_goruntule)
        alt_bar.addWidget(self.btn_depo_goruntule)

        self.btn_depo_indir = QPushButton("Farklı Kaydet (İndir)")
        self.btn_depo_indir.setObjectName("ActionBtn")
        self.btn_depo_indir.setToolTip("Dosyayı yerel diskinize veya USB belleğinize kaydeder")
        self.btn_depo_indir.clicked.connect(self.depo_dosya_indir)
        alt_bar.addWidget(self.btn_depo_indir)

        self.btn_depo_sil = QPushButton("Sil")
        self.btn_depo_sil.setObjectName("CancelBtn")
        self.btn_depo_sil.setToolTip("Seçili öğeyi sunucudan kalıcı olarak siler")
        self.btn_depo_sil.clicked.connect(self.depo_dosya_sil)
        alt_bar.addWidget(self.btn_depo_sil)

        layout.addLayout(alt_bar)
        return sayfa

    def depo_dizinini_yukle(self, hedef_dizin=None):
        """Sunucudaki hedef dizini sorgular ve dosya tablosunu doldurur."""
        if hedef_dizin is None:
            hedef_dizin = self.mevcut_dizin_yolu
            
        self.lbl_depo_durum.setText("Sunucudan dosyalar listeleniyor...")
        QApplication.processEvents()

        try:
            cevap = requests.get(
                f"{self.sunucu_url}/dosyalar-listele",
                headers=self.bilet,
                params={"alt_dizin": hedef_dizin},
                timeout=TIMEOUT
            )
            if cevap.status_code == 200:
                veri = cevap.json()
                self.mevcut_dizin_yolu = veri.get("mevcut_dizin", "")
                self.mevcut_dizin_ogeleri = veri.get("ogeler", [])
                
                yol_gorunum = "/" + self.mevcut_dizin_yolu if self.mevcut_dizin_yolu else "/ (Kök Dizin)"
                self.lbl_depo_yol.setText(f"Dizin: {yol_gorunum}")
                self.btn_depo_yukari.setEnabled(bool(self.mevcut_dizin_yolu))
                
                arama = self.txt_depo_ara.text().strip()
                if arama:
                    self.depo_filtrele(arama)
                else:
                    self.depo_tabloyu_doldur(self.mevcut_dizin_ogeleri)
            elif cevap.status_code == 401:
                self.lbl_depo_durum.setText("Yetkisiz erişim! 'Sunucu Ayarları'ndan şifreyi kontrol edin.")
                self.tablo_depo.setRowCount(0)
            else:
                self.lbl_depo_durum.setText(f"Sunucu hatası: HTTP {cevap.status_code}")
                self.tablo_depo.setRowCount(0)
        except requests.RequestException as e:
            self.lbl_depo_durum.setText(f"Bağlantı hatası: Sunucuya erişilemedi.")
            self.hata_kaydi_ekle("Dosya Gezgini", f"Bağlantı hatası: {str(e)[:50]}")
            self.tablo_depo.setRowCount(0)
        except Exception as e:
            self.lbl_depo_durum.setText(f"Hata: {str(e)[:50]}")
            self.tablo_depo.setRowCount(0)

    def depo_tabloyu_doldur(self, ogeler):
        """Öğe listesini tabloya ekler."""
        self.tablo_depo.setRowCount(0)
        for oge in ogeler:
            row = self.tablo_depo.rowCount()
            self.tablo_depo.insertRow(row)

            is_klasor = (oge.get("tip") == "klasor")
            gorunen_ad = f"[Klasör] {oge['ad']}" if is_klasor else oge['ad']

            item_ad = QTableWidgetItem(gorunen_ad)
            item_ad.setData(Qt.ItemDataRole.UserRole, oge)
            if is_klasor:
                item_ad.setForeground(QColor("#89b4fa"))
            else:
                item_ad.setForeground(QColor("#cdd6f4"))

            item_tip = QTableWidgetItem("Klasör" if is_klasor else "Dosya")
            item_tip.setForeground(QColor("#a6adc8"))

            item_uzanti = QTableWidgetItem("-" if is_klasor else oge.get("uzanti", ""))
            item_uzanti.setForeground(QColor("#a6adc8"))

            item_boyut = QTableWidgetItem("-" if is_klasor else oge.get("boyut_str", "-"))
            item_boyut.setForeground(QColor("#a6adc8"))

            item_tarih = QTableWidgetItem(oge.get("mtime", "-"))
            item_tarih.setForeground(QColor("#a6adc8"))

            self.tablo_depo.setItem(row, 0, item_ad)
            self.tablo_depo.setItem(row, 1, item_tip)
            self.tablo_depo.setItem(row, 2, item_uzanti)
            self.tablo_depo.setItem(row, 3, item_boyut)
            self.tablo_depo.setItem(row, 4, item_tarih)

        klasor_sayisi = sum(1 for o in ogeler if o.get("tip") == "klasor")
        dosya_sayisi = len(ogeler) - klasor_sayisi
        self.lbl_depo_durum.setText(f"Toplam {len(ogeler)} öğe ({klasor_sayisi} klasör, {dosya_sayisi} dosya)")

    def depo_filtrele(self, metin):
        """Dosya listesini arama metnine göre filtreler."""
        metin = metin.strip().lower()
        if not metin:
            self.depo_tabloyu_doldur(self.mevcut_dizin_ogeleri)
            return
        filtrelenmis = [
            o for o in self.mevcut_dizin_ogeleri
            if metin in o.get("ad", "").lower() or metin in o.get("uzanti", "").lower()
        ]
        self.depo_tabloyu_doldur(filtrelenmis)

    def depo_secili_oge(self):
        """Tabloda seçili olan öğenin veri sözlüğünü döndürür."""
        secili_satirlar = self.tablo_depo.selectedItems()
        if not secili_satirlar:
            return None
        row = secili_satirlar[0].row()
        item = self.tablo_depo.item(row, 0)
        if item:
            return item.data(Qt.ItemDataRole.UserRole)
        return None

    def depo_oge_cift_tiklandi(self, row, col):
        """Tablodaki öğeye çift tıklandığında klasörse içine girer, dosyaysa önizler."""
        item = self.tablo_depo.item(row, 0)
        if not item:
            return
        oge = item.data(Qt.ItemDataRole.UserRole)
        if not oge:
            return
        if oge.get("tip") == "klasor":
            self.depo_dizine_gir(oge["ad"])
        else:
            self.depo_dosya_goruntule()

    def depo_dizine_gir(self, klasor_adi):
        """Alt dizine giriş yapar."""
        yeni_yol = f"{self.mevcut_dizin_yolu}/{klasor_adi}".strip("/") if self.mevcut_dizin_yolu else klasor_adi
        self.txt_depo_ara.clear()
        self.depo_dizinini_yukle(yeni_yol)

    def depo_ust_dizine_cik(self):
        """Bir üst dizine çıkar."""
        if not self.mevcut_dizin_yolu:
            return
        parcalar = self.mevcut_dizin_yolu.replace("\\", "/").rstrip("/").split("/")
        ust_yol = "/".join(parcalar[:-1]) if len(parcalar) > 1 else ""
        self.txt_depo_ara.clear()
        self.depo_dizinini_yukle(ust_yol)

    def depo_dosya_goruntule(self):
        """Seçili dosyayı geçici belleğe indirir ve önizleme penceresinde açar. Kapatılınca silinir."""
        oge = self.depo_secili_oge()
        if not oge:
            QMessageBox.information(self, "Bilgi", "Lütfen görüntülemek istediğiniz dosyayı seçin.")
            return

        if oge.get("tip") == "klasor":
            self.depo_dizine_gir(oge["ad"])
            return

        # Büyük dosya güvenlik kontrolü (>30 MB)
        dosya_boyutu = oge.get("boyut", 0)
        if dosya_boyutu > 30 * 1024 * 1024:
            mb_boyut = dosya_boyutu / (1024 * 1024)
            onay = QMessageBox.question(
                self,
                "Büyük Dosya Uyarısı",
                f"Seçilen dosya çok büyük ({mb_boyut:.1f} MB)!\n\n"
                f"Bu dosyanın önizleme için sunucudan indirilmesi ağ hızınıza bağlı olarak zaman alabilir.\n\n"
                f"Yine de indirip önizlemek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if onay != QMessageBox.StandardButton.Yes:
                return

        sunucu_yol = f"{self.mevcut_dizin_yolu}/{oge['ad']}".strip("/") if self.mevcut_dizin_yolu else oge['ad']
        TEMP_ONIZLEME_DIZINI.mkdir(parents=True, exist_ok=True)
        gecici_hedef = TEMP_ONIZLEME_DIZINI / f"{uuid.uuid4().hex[:8]}_{oge['ad']}"

        self.lbl_depo_durum.setText(f"İndiriliyor: {oge['ad']}...")
        QApplication.processEvents()

        try:
            with requests.get(
                f"{self.sunucu_url}/dosya-indir",
                headers=self.bilet,
                params={"dosya_yolu": sunucu_yol},
                stream=True,
                timeout=60
            ) as resp:
                if resp.status_code == 200:
                    with open(gecici_hedef, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                else:
                    QMessageBox.critical(self, "Hata", f"Dosya sunucudan alınamadı (HTTP {resp.status_code}).")
                    self.lbl_depo_durum.setText("İndirme başarısız.")
                    return
        except requests.RequestException as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Dosya indirilirken ağ hatası oluştu:\n{str(e)}")
            self.hata_kaydi_ekle("Önizleme İndirme", str(e))
            self.lbl_depo_durum.setText("Ağ hatası.")
            return
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Beklenmeyen bir hata oluştu:\n{str(e)}")
            self.hata_kaydi_ekle("Önizleme", str(e))
            self.lbl_depo_durum.setText("Sistem hatası.")
            return

        self.lbl_depo_durum.setText(f"Önizleniyor: {oge['ad']}")
        try:
            dialog = DosyaOnizlemeDialog(gecici_hedef, oge, self)
            dialog.exec()
        finally:
            # Pencere kapandığında dosya diskten garanti temizlenir
            if gecici_hedef.exists():
                try:
                    gecici_hedef.unlink()
                except Exception:
                    pass
            self.lbl_depo_durum.setText("Önizleme kapatıldı, geçici dosya temizlendi.")

    def depo_dosya_indir(self):
        """Seçili dosyayı kullanıcının seçeceği yerel diske/flaş diske kaydeder."""
        oge = self.depo_secili_oge()
        if not oge:
            QMessageBox.information(self, "Bilgi", "Lütfen indirmek için bir dosya seçin.")
            return

        if oge.get("tip") == "klasor":
            QMessageBox.information(self, "Bilgi", "Tek seferde klasör indirme desteklenmemektedir. Lütfen klasör içine girerek bir dosya seçin.")
            return

        kayit_yolu, _ = QFileDialog.getSaveFileName(
            self,
            "Dosyayı Kaydet",
            oge["ad"],
            "Tüm Dosyalar (*.*)"
        )
        if not kayit_yolu:
            return

        sunucu_yol = f"{self.mevcut_dizin_yolu}/{oge['ad']}".strip("/") if self.mevcut_dizin_yolu else oge['ad']

        self.lbl_depo_durum.setText(f"Kaydediliyor: {oge['ad']}...")
        QApplication.processEvents()

        try:
            with requests.get(
                f"{self.sunucu_url}/dosya-indir",
                headers=self.bilet,
                params={"dosya_yolu": sunucu_yol},
                stream=True,
                timeout=120
            ) as resp:
                if resp.status_code == 200:
                    with open(kayit_yolu, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                    QMessageBox.information(self, "Başarılı", f"Dosya başarıyla kaydedildi:\n{kayit_yolu}")
                    self.lbl_depo_durum.setText(f"Dosya kaydedildi: {oge['ad']}")
                else:
                    QMessageBox.critical(self, "Hata", f"Dosya sunucudan alınamadı (HTTP {resp.status_code}).")
                    self.lbl_depo_durum.setText("İndirme başarısız.")
        except requests.RequestException as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Dosya indirilirken ağ hatası oluştu:\n{str(e)}")
            self.hata_kaydi_ekle("Dosya İndirme", str(e))
            self.lbl_depo_durum.setText("Ağ hatası.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Dosya diske kaydedilemedi:\n{str(e)}")
            self.hata_kaydi_ekle("Dosya Kaydetme", str(e))
            self.lbl_depo_durum.setText("Yazma hatası.")

    def depo_dosya_sil(self):
        """Seçili dosya veya klasörü sunucudan kalıcı olarak siler."""
        oge = self.depo_secili_oge()
        if not oge:
            QMessageBox.information(self, "Bilgi", "Lütfen silmek istediğiniz öğeyi seçin.")
            return

        tur_str = "klasörünü ve içindeki tüm dosyaları" if oge.get("tip") == "klasor" else "dosyasını"
        onay = QMessageBox.question(
            self,
            "Silme Onayı",
            f"'{oge['ad']}' {tur_str} sunucudan kalıcı olarak silmek istediğinizden emin misiniz?\n\nBu işlem geri alınamaz!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if onay != QMessageBox.StandardButton.Yes:
            return

        sunucu_yol = f"{self.mevcut_dizin_yolu}/{oge['ad']}".strip("/") if self.mevcut_dizin_yolu else oge['ad']

        try:
            cevap = requests.delete(
                f"{self.sunucu_url}/depo-dosya-sil",
                headers=self.bilet,
                params={"dosya_yolu": sunucu_yol},
                timeout=TIMEOUT
            )
            if cevap.status_code == 200:
                self.depo_dizinini_yukle()
                self.sunucu_senkronizasyonu()
                QMessageBox.information(self, "Başarılı", f"'{oge['ad']}' başarıyla silindi.")
            else:
                QMessageBox.critical(self, "Hata", f"Silme işlemi başarısız oldu (HTTP {cevap.status_code}).")
        except requests.RequestException as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya bağlanılamadı:\n{str(e)}")
            self.hata_kaydi_ekle("Dosya Silme", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Beklenmeyen bir hata oluştu:\n{str(e)}")
            self.hata_kaydi_ekle("Dosya Silme", str(e))

    def oto_yedekleme_sayfasi_olustur(self):
        sayfa = QWidget()
        layout = QVBoxLayout(sayfa)
        layout.setContentsMargins(40, 40, 60, 40)

        baslik = QLabel("Yeni Otomatik Yedekleme Planı")
        baslik.setObjectName("Baslik")
        layout.addWidget(baslik)
        layout.addSpacing(20)

        klsr_frame = QFrame()
        klsr_frame.setProperty("class", "SettingsRow")
        klsr_lay = QVBoxLayout(klsr_frame)
        
        lbl_klasor = QLabel("Yedeklenecek Klasörler:")
        lbl_klasor.setStyleSheet("font-size: 15px; font-weight: bold; color: #cdd6f4;")
        klsr_lay.addWidget(lbl_klasor)
        
        self.liste_klasorler = QListWidget()
        self.liste_klasorler.setFixedHeight(110)
        klsr_lay.addWidget(self.liste_klasorler)
        
        btn_lay = QHBoxLayout()
        btn_ekle = QPushButton("Klasör Ekle")
        btn_ekle.setProperty("class", "SettingsBtn")
        btn_ekle.clicked.connect(self.klasor_ekle)
        
        btn_temizle = QPushButton("Listeyi Temizle")
        btn_temizle.setProperty("class", "SettingsBtn")
        btn_temizle.clicked.connect(self.liste_klasorler.clear)
        
        btn_lay.addWidget(btn_ekle)
        btn_lay.addWidget(btn_temizle)
        btn_lay.addStretch()
        klsr_lay.addLayout(btn_lay)
        layout.addWidget(klsr_frame)

        zaman_frame = QFrame()
        zaman_frame.setProperty("class", "SettingsRow")
        zaman_lay = QHBoxLayout(zaman_frame)
        
        lbl_zaman = QLabel("Takvim ve Saat:")
        lbl_zaman.setStyleSheet("font-size: 15px; font-weight: bold; color: #cdd6f4;")
        zaman_lay.addWidget(lbl_zaman)
        
        self.lbl_secilen_zaman = QLabel("Seçilmedi")
        self.lbl_secilen_zaman.setProperty("class", "SettingsValue")
        self.lbl_secilen_zaman.setStyleSheet("color: #a6adc8;")
        
        btn_zaman = QPushButton("Zaman Seç")
        btn_zaman.setProperty("class", "SettingsBtn")
        btn_zaman.clicked.connect(self.zaman_sec_dialog)
        
        zaman_lay.addStretch()
        zaman_lay.addWidget(self.lbl_secilen_zaman)
        zaman_lay.addWidget(btn_zaman)
        layout.addWidget(zaman_frame)

        btn_kaydet = QPushButton("Görevi Sunucuya Kaydet ve Zamanla")
        btn_kaydet.setObjectName("ActionBtn")
        btn_kaydet.clicked.connect(self.gorev_olustur)
        layout.addWidget(btn_kaydet)

        layout.addStretch()
        return sayfa

    def manuel_yukleme_sayfasi_olustur(self):
        sayfa = QWidget()
        layout = QVBoxLayout(sayfa)
        layout.setContentsMargins(40, 40, 60, 40)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        baslik = QLabel("Manuel Klasör Yükleme")
        baslik.setObjectName("Baslik")
        layout.addWidget(baslik)
        layout.addSpacing(20)

        secim_frame = QFrame()
        secim_frame.setProperty("class", "SettingsRow")
        secim_lay = QHBoxLayout(secim_frame)
        
        self.lbl_secilen_manuel_klasor = QLabel("Seçilen Klasör: Yok")
        self.lbl_secilen_manuel_klasor.setStyleSheet("color: #a6adc8; font-size: 14px;")
        
        btn_sec = QPushButton("Klasör Seç")
        btn_sec.setProperty("class", "SettingsBtn")
        btn_sec.clicked.connect(self.manuel_klasor_sec)
        
        secim_lay.addWidget(self.lbl_secilen_manuel_klasor)
        secim_lay.addStretch()
        secim_lay.addWidget(btn_sec)
        layout.addWidget(secim_frame)
        layout.addSpacing(20)

        self.lbl_manuel_durum = QLabel("İşlem bekleniyor...")
        self.lbl_manuel_durum.setWordWrap(True)
        layout.addWidget(self.lbl_manuel_durum)

        layout.addSpacing(10)
        layout.addWidget(QLabel("Aktif Dosya İlerlemesi:"))
        self.manuel_bar_dosya = QProgressBar()
        self.manuel_bar_dosya.setValue(0)
        layout.addWidget(self.manuel_bar_dosya)
        
        layout.addSpacing(10)
        layout.addWidget(QLabel("Genel Klasör İlerlemesi:"))
        self.manuel_bar_genel = QProgressBar()
        self.manuel_bar_genel.setObjectName("GenelBar")
        self.manuel_bar_genel.setValue(0)
        layout.addWidget(self.manuel_bar_genel)
        
        layout.addSpacing(25)
        buton_lay = QHBoxLayout()
        self.btn_manuel_yukle = QPushButton("Sunucuya Gönder (Hemen Başlat)")
        self.btn_manuel_yukle.setObjectName("ActionBtn")
        self.btn_manuel_yukle.clicked.connect(self.manuel_yuklemeyi_baslat)
        
        self.btn_manuel_durdur = QPushButton("Durdur")
        self.btn_manuel_durdur.setObjectName("CancelBtn")
        self.btn_manuel_durdur.setEnabled(False)
        self.btn_manuel_durdur.clicked.connect(self.manuel_yuklemeyi_durdur)

        buton_lay.addWidget(self.btn_manuel_yukle)
        buton_lay.addWidget(self.btn_manuel_durdur)
        layout.addLayout(buton_lay)
        
        layout.addStretch()
        return sayfa

    def gorevler_sayfasi_olustur(self):
        sayfa = QWidget()
        layout = QVBoxLayout(sayfa)
        layout.setContentsMargins(40, 20, 40, 20)
        
        baslik_satir = QHBoxLayout()
        baslik = QLabel("İşlemler ve Görev Geçmişi")
        baslik.setObjectName("Baslik")
        baslik_satir.addWidget(baslik)
        baslik_satir.addStretch()

        btn_tum_gecmisi_sil = QPushButton("Tüm Geçmişi Temizle")
        btn_tum_gecmisi_sil.setProperty("class", "SettingsBtn")
        btn_tum_gecmisi_sil.clicked.connect(self.tum_gecmisi_sil)
        baslik_satir.addWidget(btn_tum_gecmisi_sil)

        layout.addLayout(baslik_satir)
        
        self.scroll_area = QScrollArea()
        self.scroll_icerik = QWidget()
        self.scroll_icerik.setObjectName("ScrollContent")
        self.scroll_layout = QVBoxLayout(self.scroll_icerik)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.scroll_area.setWidget(self.scroll_icerik)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area)
        
        return sayfa

    def sunucu_ayarlari_sayfasi_olustur(self):
        """Sunucu adresi ve şifresinin yapılandırıldığı sayfa."""
        sayfa = QWidget()
        layout = QVBoxLayout(sayfa)
        layout.setContentsMargins(40, 30, 60, 30)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        baslik = QLabel("Sunucu Bağlantı Ayarları")
        baslik.setObjectName("Baslik")
        layout.addWidget(baslik)
        
        aciklama = QLabel("Depolamanın yapılacağı sunucu adresini ve erişim şifresini buradan belirleyebilirsiniz.\nAyarlar kaydedildiğinde uygulama her açıldığında bu sunucuya otomatik bağlanacaktır.")
        aciklama.setStyleSheet("color: #a6adc8; font-size: 13px; margin-bottom: 15px;")
        layout.addWidget(aciklama)

        # Adres Kartı
        url_frame = QFrame()
        url_frame.setProperty("class", "SettingsRow")
        url_lay = QVBoxLayout(url_frame)
        lbl_url = QLabel("Sunucu Adresi (URL):")
        lbl_url.setStyleSheet("font-size: 14px; font-weight: bold; color: #cdd6f4;")
        url_lay.addWidget(lbl_url)
        
        self.txt_sunucu_url = QLineEdit()
        self.txt_sunucu_url.setPlaceholderText("http://100.76.104.55:8000")
        self.txt_sunucu_url.setText(self.sunucu_url)
        url_lay.addWidget(self.txt_sunucu_url)
        
        lbl_url_ipucu = QLabel("Örnek: http://100.76.104.55:8000 veya http://192.168.1.100:8000")
        lbl_url_ipucu.setStyleSheet("color: #6c7086; font-size: 11px;")
        url_lay.addWidget(lbl_url_ipucu)
        layout.addWidget(url_frame)

        layout.addSpacing(10)

        # Şifre Kartı
        sifre_frame = QFrame()
        sifre_frame.setProperty("class", "SettingsRow")
        sifre_lay = QVBoxLayout(sifre_frame)
        lbl_sifre = QLabel("Sunucu Erişim Şifresi:")
        lbl_sifre.setStyleSheet("font-size: 14px; font-weight: bold; color: #cdd6f4;")
        sifre_lay.addWidget(lbl_sifre)

        sifre_input_lay = QHBoxLayout()
        self.txt_sunucu_sifre = QLineEdit()
        self.txt_sunucu_sifre.setEchoMode(QLineEdit.EchoMode.Password)
        self.txt_sunucu_sifre.setText(self.sunucu_sifre)
        sifre_input_lay.addWidget(self.txt_sunucu_sifre)

        chk_goster = QCheckBox("Göster")
        chk_goster.setStyleSheet("color: #a6adc8; font-size: 12px;")
        chk_goster.toggled.connect(lambda g: self.txt_sunucu_sifre.setEchoMode(QLineEdit.EchoMode.Normal if g else QLineEdit.EchoMode.Password))
        sifre_input_lay.addWidget(chk_goster)
        sifre_lay.addLayout(sifre_input_lay)
        layout.addWidget(sifre_frame)

        layout.addSpacing(15)

        # Sonuç Bildirimi
        self.lbl_config_durum = QLabel("")
        self.lbl_config_durum.setWordWrap(True)
        self.lbl_config_durum.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(self.lbl_config_durum)

        layout.addSpacing(10)

        # Butonlar
        btn_lay = QHBoxLayout()
        btn_test = QPushButton("Bağlantıyı Test Et")
        btn_test.setObjectName("ActionBtn")
        btn_test.clicked.connect(self.config_baglanti_test_et)

        btn_kaydet = QPushButton("Kaydet ve Bağlan")
        btn_kaydet.setObjectName("ActionBtn")
        btn_kaydet.clicked.connect(self.config_kaydet_ve_baglan)

        btn_lay.addWidget(btn_test)
        btn_lay.addWidget(btn_kaydet)
        btn_lay.addStretch()
        layout.addLayout(btn_lay)

        layout.addStretch()
        return sayfa

    def hakkinda_sayfasi_olustur(self):
        """Uygulama özellikleri ve geliştirici iletişim bilgilerini içeren sayfa."""
        ana_sayfa = QWidget()
        ana_layout = QVBoxLayout(ana_sayfa)
        ana_layout.setContentsMargins(35, 25, 35, 25)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background-color: transparent; border: none;")

        icerik_widget = QWidget()
        icerik_widget.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(icerik_widget)
        layout.setContentsMargins(10, 10, 25, 20)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        baslik = QLabel("Hakkında")
        baslik.setObjectName("Baslik")
        layout.addWidget(baslik)
        
        aciklama = QLabel("Bulut OS depolama mimarisi, teknik özellikleri ve geliştirici bilgileri aşağıda yer almaktadır.")
        aciklama.setStyleSheet("color: #a6adc8; font-size: 13px; margin-bottom: 18px;")
        layout.addWidget(aciklama)

        # 1. Menü: Uygulama Özellikleri
        kutu_ozellikler = KatlanabilirKutu("Uygulama Özellikleri ve Çalışma Mantığı")
        
        lbl_ozellikler = QLabel(
            "<b>• Parçalı ve Kesintisiz Yükleme (Chunked & Resumable):</b><br>"
            "Büyük boyutlu dosyalar 1 MB'lık parçalara bölünerek sunucuya aktarılır. "
            "Ağ bağlantısı koparsa veya uygulama kapatılırsa, tekrar açıldığında dosya baştan değil, "
            "sunucudaki son bayttan devam eder.<br><br>"
            "<b>• Otomatik & Zamanlanmış Yedekleme:</b><br>"
            "Belirlediğiniz klasörler arka planda APScheduler motoru ile istenen gün ve saatte "
            "otomatik olarak sunucuya yedeklenir. Yaklaşan görevler panodan izlenebilir ve ertelenebilir.<br><br>"
            "<b>• Manuel Klasör Aktarımı:</b><br>"
            "İstediğiniz klasörü tek tıkla hemen gönderebilir, aktif dosya ve genel ilerleme çubukları ile "
            "aktarımı canlı izleyebilir, gerektiğinde durdurabilirsiniz.<br><br>"
            "<b>• Canlı Disk ve Durum Takibi:</b><br>"
            "Sunucunun boş ve toplam kapasitesi ana ekrandaki dairesel grafik üzerinden takip edilir. "
            "Sol alt köşede sunucu bağlantı durumu tüm pencerelerde anlık görüntülenir.<br><br>"
            "<b>• Güvenli ve Eşzamanlı Mimari:</b><br>"
            "FastAPI arka ucunda dizin atlama (Path Traversal) engeli, sabit zamanlı kimlik doğrulama "
            "ve eşzamanlı veri kilitleri ile verilerin bütünlüğü tam olarak korunur."
        )
        lbl_ozellikler.setWordWrap(True)
        lbl_ozellikler.setStyleSheet("color: #cdd6f4; font-size: 13px; line-height: 1.5;")
        kutu_ozellikler.icerik_ekle(lbl_ozellikler)
        layout.addWidget(kutu_ozellikler)

        layout.addSpacing(14)

        # 2. Menü: Geliştirici & İletişim Bilgileri
        kutu_gelistirici = KatlanabilirKutu("Geliştirici & İletişim Bilgileri")
        
        gelistirici_kutu = QWidget()
        g_lay = QVBoxLayout(gelistirici_kutu)
        g_lay.setContentsMargins(0, 0, 0, 0)
        g_lay.setSpacing(12)

        lbl_gelistirici = QLabel(
            "<b>Geliştirici:</b> az1032<br>"
            "<b>Proje:</b> Bulut OS - Depolama & Yedekleme Sistemi<br><br>"
            "Bu sistem, yerel dosyalarınızı güvenli bir şekilde sunucunuza aktarmak, "
            "otomatik zamanlanmış yedekleme planları oluşturmak ve veri bütünlüğünü sağlamak "
            "amacıyla <b>az1032</b> tarafından modern Python, PyQt6 ve FastAPI teknolojileri "
            "kullanılarak tasarlanmış ve geliştirilmiştir."
        )
        lbl_gelistirici.setWordWrap(True)
        lbl_gelistirici.setStyleSheet("color: #cdd6f4; font-size: 13px; line-height: 1.5;")
        g_lay.addWidget(lbl_gelistirici)

        # Butonlar Satırı
        btn_satir = QHBoxLayout()
        btn_github = QPushButton("GitHub Profilini Aç (az1032)")
        btn_github.setObjectName("ActionBtn")
        btn_github.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/az1032")))

        btn_mail = QPushButton("E-posta Gönder (az1032110@gmail.com)")
        btn_mail.setObjectName("ActionBtn")
        btn_mail.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_mail.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("mailto:az1032110@gmail.com")))

        btn_satir.addWidget(btn_github)
        btn_satir.addWidget(btn_mail)
        btn_satir.addStretch()
        g_lay.addLayout(btn_satir)

        kutu_gelistirici.icerik_ekle(gelistirici_kutu)
        layout.addWidget(kutu_gelistirici)

        layout.addStretch()
        scroll.setWidget(icerik_widget)
        ana_layout.addWidget(scroll)

        return ana_sayfa

    def config_baglanti_test_et(self):
        url = self.txt_sunucu_url.text().strip().rstrip("/")
        sifre = self.txt_sunucu_sifre.text().strip()
        if not url:
            self.lbl_config_durum.setText("Lütfen geçerli bir sunucu adresi girin!")
            self.lbl_config_durum.setStyleSheet("color: #f38ba8;")
            return

        self.lbl_config_durum.setText("Bağlantı test ediliyor, lütfen bekleyin...")
        self.lbl_config_durum.setStyleSheet("color: #89b4fa;")
        QApplication.processEvents()

        try:
            resp = requests.get(f"{url}/", headers={"gelen-sifre": sifre}, timeout=6)
            if resp.status_code == 200:
                v = resp.json()
                bos_gb = v.get("bos_alan", 0) / (1024**3)
                toplam_gb = v.get("toplam", 0) / (1024**3)
                self.lbl_config_durum.setText(f"Bağlantı başarılı! (Sunucu Boş Alan: {bos_gb:.1f} GB / Toplam: {toplam_gb:.1f} GB)")
                self.lbl_config_durum.setStyleSheet("color: #a6e3a1;")
            elif resp.status_code == 401:
                self.lbl_config_durum.setText("Bağlantı Başarısız: Sunucu şifresi hatalı! (HTTP 401)")
                self.lbl_config_durum.setStyleSheet("color: #f38ba8;")
            elif resp.status_code == 429:
                self.lbl_config_durum.setText("Bağlantı Başarısız: Çok fazla hatalı deneme! IP adresiniz geçici olarak engellendi. (HTTP 429)")
                self.lbl_config_durum.setStyleSheet("color: #f38ba8;")
            else:
                self.lbl_config_durum.setText(f"Bağlantı Başarısız: Sunucu yanıt kodu HTTP {resp.status_code}")
                self.lbl_config_durum.setStyleSheet("color: #f38ba8;")
        except requests.exceptions.ConnectTimeout:
            self.lbl_config_durum.setText("Zaman Aşımı: Sunucuya ulaşılamadı! Bulut panelinden (Oracle/AWS) 8000 portuna Ingress izni verildiğinden ve 'ufw allow 8000/tcp' yapıldığından emin olun.")
            self.lbl_config_durum.setStyleSheet("color: #f38ba8;")
        except requests.exceptions.ConnectionError:
            self.lbl_config_durum.setText("Bağlantı Başarısız: Sunucu veya port kapalı. Sunucunun 0.0.0.0 üzerinde çalıştığından emin olun.")
            self.lbl_config_durum.setStyleSheet("color: #f38ba8;")
        except Exception as e:
            self.lbl_config_durum.setText(f"Hata: {str(e)}")
            self.lbl_config_durum.setStyleSheet("color: #f38ba8;")

    def config_kaydet_ve_baglan(self):
        url = self.txt_sunucu_url.text().strip().rstrip("/")
        sifre = self.txt_sunucu_sifre.text().strip()
        if not url:
            QMessageBox.warning(self, "Eksik Bilgi", "Sunucu adresi boş bırakılamaz!")
            return

        basarili = ayar_kaydet(url, sifre)
        if basarili:
            self.sunucu_url = url
            self.sunucu_sifre = sifre
            self.bilet = {"gelen-sifre": sifre}
            self.lbl_config_durum.setText("Ayarlar başarıyla kaydedildi! Sunucuya bağlanılıyor...")
            self.lbl_config_durum.setStyleSheet("color: #a6e3a1;")
            self.sunucu_senkronizasyonu()
        else:
            self.lbl_config_durum.setText("Ayarlar dosyaya kaydedilemedi!")
            self.lbl_config_durum.setStyleSheet("color: #f38ba8;")

    # --- OTO YEDEKLEME İŞLEMLERİ ---
    def klasor_ekle(self):
        klasor = QFileDialog.getExistingDirectory(self, "Yedeklenecek Klasörü Seç")
        if klasor:
            items = [self.liste_klasorler.item(i).text() for i in range(self.liste_klasorler.count())]
            if klasor not in items:
                self.liste_klasorler.addItem(klasor)

    def zaman_sec_dialog(self):
        dialog = TarihSaatSecici(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.secilen_tarih_saat = dialog.get_datetime()
            self.lbl_secilen_zaman.setText(self.secilen_tarih_saat.strftime("%Y-%m-%d %H:%M"))

    def gorev_olustur(self):
        klasorler = [self.liste_klasorler.item(i).text() for i in range(self.liste_klasorler.count())]
        if not klasorler:
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen en az bir klasör seçin!")
            return
        if not hasattr(self, 'secilen_tarih_saat'):
            QMessageBox.warning(self, "Eksik Bilgi", "Lütfen bir zaman seçin!")
            return
            
        gorev_id = f"gorev_{uuid.uuid4().hex[:8]}"
        zaman_str = self.secilen_tarih_saat.strftime("%Y-%m-%d %H:%M")
        veri = {
            "id": gorev_id,
            "klasorler": klasorler,
            "zaman": zaman_str,
            "durum": "Bekleniyor"
        }
        
        try:
            resp = requests.post(f"{self.sunucu_url}/gorev-ekle", json=veri, headers=self.bilet, timeout=TIMEOUT)
            if resp.status_code == 200:
                self.liste_klasorler.clear()
                self.lbl_secilen_zaman.setText("Görev başarıyla kuruldu!")
                self.sunucu_senkronizasyonu()
            else:
                QMessageBox.critical(self, "Hata", f"Sunucu hatası: {resp.text}")
        except requests.RequestException as e:
            QMessageBox.critical(self, "Bağlantı Hatası", f"Sunucuya ulaşılamadı: {str(e)}")

    # --- MANUEL YÜKLEME İŞLEMLERİ ---
    def manuel_klasor_sec(self):
        klasor = QFileDialog.getExistingDirectory(self, "Sunucuya Gönderilecek Klasörü Seç")
        if klasor:
            self.manuel_klasor_yolu = klasor
            klasor_adi = os.path.basename(os.path.normpath(klasor))
            self.lbl_secilen_manuel_klasor.setText(f"Seçilen: {klasor_adi}")
            self.lbl_manuel_durum.setText("Klasör hazır, başlat butonuna basabilirsiniz.")
            self.manuel_bar_genel.setValue(0)
            self.manuel_bar_dosya.setValue(0)

    def manuel_yuklemeyi_baslat(self):
        if not self.manuel_klasor_yolu:
            self.lbl_manuel_durum.setText("Lütfen önce bir klasör seçin!")
            return
            
        self.btn_manuel_yukle.setEnabled(False)
        self.btn_manuel_durdur.setEnabled(True)
        self.lbl_manuel_durum.setText("Yükleme başlatıldı...")
        self.manuel_bar_genel.setValue(0)
        self.manuel_bar_dosya.setValue(0)
        
        self.manuel_motor = CokluKlasorYuklemeIslemi([self.manuel_klasor_yolu], self.sunucu_url, self.bilet)
        self.manuel_motor.dosya_ilerleme.connect(self.manuel_pano_dosya_guncelle)
        self.manuel_motor.genel_ilerleme.connect(self.manuel_bar_genel.setValue)
        self.manuel_motor.durum_guncelle.connect(self.lbl_manuel_durum.setText)
        self.manuel_motor.tamamlandi.connect(self.manuel_yukleme_bitti)
        self.manuel_motor.start()

    def manuel_yuklemeyi_durdur(self):
        if self.manuel_motor and self.manuel_motor.isRunning():
            self.manuel_motor.durdur()
            self.lbl_manuel_durum.setText("Durduruluyor...")
            self.btn_manuel_durdur.setEnabled(False)

    def manuel_pano_dosya_guncelle(self, yuzde, dosya_adi):
        self.manuel_bar_dosya.setValue(yuzde)
        self.lbl_manuel_durum.setText(f"Yükleniyor: {dosya_adi}")

    def manuel_yukleme_bitti(self, basarili, mesaj):
        self.btn_manuel_yukle.setEnabled(True)
        self.btn_manuel_durdur.setEnabled(False)
        self.lbl_manuel_durum.setText(mesaj)
        if basarili:
            self.manuel_klasor_yolu = ""
            self.lbl_secilen_manuel_klasor.setText("Seçilen: Yok")
            self.sunucu_senkronizasyonu()
        else:
            self.hata_kaydi_ekle("Manuel Yükleme", mesaj)

    # --- OTO GÖREV ÇEK / KUR ---
    def gorevleri_getir_ve_kur(self):
        try:
            cevap = requests.get(f"{self.sunucu_url}/gorevler", headers=self.bilet, timeout=TIMEOUT)
            if cevap.status_code == 200:
                gorevler = cevap.json()
                self.scheduler.remove_all_jobs()
                simdi = datetime.now()

                bekleyenler = []

                for g_id, g_veri in gorevler.items():
                    if g_veri.get("durum") == "Bekleniyor":
                        try:
                            zaman_obj = datetime.strptime(g_veri["zaman"], "%Y-%m-%d %H:%M")
                            bekleyenler.append((zaman_obj, g_id, g_veri))
                            
                            # Zamanı geçmişse ve henüz işlemde değilse tek sefer çalıştır
                            if zaman_obj < simdi:
                                requests.post(
                                    f"{self.sunucu_url}/gorev-guncelle", 
                                    data={"gorev_id": g_id, "durum": "Sıraya Alındı"}, 
                                    headers=self.bilet, 
                                    timeout=TIMEOUT
                                )
                                self.zamanlayici_tetiklendi.emit(g_id, g_veri["klasorler"])
                            else:
                                self.scheduler.add_job(
                                    lambda gid=g_id, kls=g_veri["klasorler"]: self.zamanlayici_tetiklendi.emit(gid, kls),
                                    'date', 
                                    run_date=zaman_obj, 
                                    id=g_id
                                )
                        except Exception:
                            pass
                
                self.sunucu_gorevleri = gorevler

                # Panodaki Bekleme Durumunu Güncelle (Bug Çözümü)
                if not (self.aktif_motor and self.aktif_motor.isRunning()):
                    bekleyenler.sort(key=lambda x: x[0])
                    if bekleyenler:
                        en_yakin_zaman, en_yakin_id, en_yakin_veri = bekleyenler[0]
                        self.bekleyen_pano_gorev_id = en_yakin_id
                        klsr_ozet = ", ".join([os.path.basename(k) for k in en_yakin_veri.get("klasorler", [])])[:25]
                        self.lbl_pano_durum.setText(f"İşlem için saat bekleniyor: {en_yakin_veri['zaman']} ({klsr_ozet})")
                        self.btn_ertele.setVisible(True)
                    else:
                        self.bekleyen_pano_gorev_id = None
                        self.lbl_pano_durum.setText("Sistem Hazır. Bekleyen otomatik işlem yok.")
                        self.btn_ertele.setVisible(False)

        except requests.RequestException as e:
            self.hata_kaydi_ekle("Görev Sorgulama", str(e))

    def pano_gorev_ertele(self):
        """İşlem panosundaki erteleme butonu tıklandığında saati günceller."""
        if not hasattr(self, 'bekleyen_pano_gorev_id') or not self.bekleyen_pano_gorev_id:
            return
            
        dialog = TarihSaatSecici(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            yeni_zaman = dialog.get_datetime().strftime("%Y-%m-%d %H:%M")
            try:
                requests.post(
                    f"{self.sunucu_url}/gorev-guncelle", 
                    data={"gorev_id": self.bekleyen_pano_gorev_id, "zaman": yeni_zaman, "durum": "Bekleniyor"}, 
                    headers=self.bilet, 
                    timeout=TIMEOUT
                )
                QMessageBox.information(self, "İşlem Başarılı", f"Görev saati {yeni_zaman} olarak ertelendi.")
            except requests.RequestException as e:
                QMessageBox.warning(self, "Hata", f"Görev ertelenemedi: {str(e)}")
            self.sunucu_senkronizasyonu()

    def gorevleri_arayuze_ciz(self):
        for i in reversed(range(self.scroll_layout.count())): 
            w = self.scroll_layout.itemAt(i).widget()
            if w: 
                w.deleteLater()
            
        if not hasattr(self, 'sunucu_gorevleri') or not self.sunucu_gorevleri:
            lbl = QLabel("Kayıtlı hiçbir işlem veya görev bulunamadı.")
            self.scroll_layout.addWidget(lbl)
            return

        for g_id, g_veri in self.sunucu_gorevleri.items():
            kutu = QFrame()
            kutu.setProperty("class", "SettingsRow")
            k_lay = QHBoxLayout(kutu)
            
            klsr_isim = ", ".join([os.path.basename(k) for k in g_veri.get("klasorler", [])])
            bilgi = QLabel(f"<b>{klsr_isim[:35]}</b><br>Zaman: {g_veri.get('zaman', '')} | Durum: <i>{g_veri.get('durum', '')}</i>")
            k_lay.addWidget(bilgi)
            k_lay.addStretch()
            
            if g_veri.get("durum") in ["Bekleniyor", "Sıraya Alındı"]:
                btn_edit = QPushButton("Düzenle")
                btn_edit.setProperty("class", "SettingsBtn")
                btn_sil = QPushButton("Sil")
                btn_sil.setProperty("class", "SettingsBtn")
                btn_sil.clicked.connect(lambda ch, gid=g_id: self.gorev_sil(gid))
                btn_edit.clicked.connect(lambda ch, gid=g_id: self.gorev_duzenle(gid))
                k_lay.addWidget(btn_edit)
                k_lay.addWidget(btn_sil)
            else:
                btn_gecmis_sil = QPushButton("Geçmişten Sil")
                btn_gecmis_sil.setProperty("class", "SettingsBtn")
                btn_gecmis_sil.clicked.connect(lambda ch, gid=g_id: self.gorev_sil(gid))
                k_lay.addWidget(btn_gecmis_sil)
                
            self.scroll_layout.addWidget(kutu)

    def tum_gecmisi_sil(self):
        """Geçmişte tamamlanmış veya hata almış tüm görevleri sunucudan siler."""
        if not hasattr(self, 'sunucu_gorevleri') or not self.sunucu_gorevleri:
            QMessageBox.information(self, "Bilgi", "Kayıtlı herhangi bir işlem bulunamadı.")
            return

        silinecekler = [gid for gid, g_veri in self.sunucu_gorevleri.items() if g_veri.get("durum") not in ["Bekleniyor", "Sıraya Alındı", "İşlem yapılıyor"]]
        if not silinecekler:
            QMessageBox.information(self, "Bilgi", "Geçmişte silinecek tamamlanmış bir işlem bulunamadı.")
            return

        onay = QMessageBox.question(
            self, 
            "Geçmişi Temizle", 
            f"Tamamlanmış {len(silinecekler)} adet geçmiş işlem kaydı sunucudan silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if onay == QMessageBox.StandardButton.Yes:
            for gid in silinecekler:
                try:
                    requests.delete(f"{self.sunucu_url}/gorev-sil/{gid}", headers=self.bilet, timeout=TIMEOUT)
                except requests.RequestException:
                    pass
            self.sunucu_senkronizasyonu()
            self.gorevleri_arayuze_ciz()

    def gorev_sil(self, gorev_id):
        try:
            requests.delete(f"{self.sunucu_url}/gorev-sil/{gorev_id}", headers=self.bilet, timeout=TIMEOUT)
        except requests.RequestException:
            pass
        self.sunucu_senkronizasyonu()
        self.gorevleri_arayuze_ciz()

    def gorev_duzenle(self, gorev_id):
        dialog = TarihSaatSecici(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            yeni_zaman = dialog.get_datetime().strftime("%Y-%m-%d %H:%M")
            try:
                requests.post(
                    f"{self.sunucu_url}/gorev-guncelle", 
                    data={"gorev_id": gorev_id, "zaman": yeni_zaman, "durum": "Bekleniyor"}, 
                    headers=self.bilet, 
                    timeout=TIMEOUT
                )
            except requests.RequestException:
                pass
            self.sunucu_senkronizasyonu()
            self.gorevleri_arayuze_ciz()

    # Thread-Safe Slot (Sadece GUI Ana Thread'inde Çalışır)
    def gorev_tetikle(self, gorev_id, klasorler):
        if self.aktif_motor and self.aktif_motor.isRunning():
            self.lbl_pano_durum.setText(f"Görev bekletildi (Başka bir yedekleme sürüyor).")
            return

        self.aktif_gorev_id = gorev_id
        try:
            requests.post(
                f"{self.sunucu_url}/gorev-guncelle", 
                data={"gorev_id": gorev_id, "durum": "İşlem yapılıyor"}, 
                headers=self.bilet, 
                timeout=TIMEOUT
            )
        except requests.RequestException:
            pass
        
        self.lbl_pano_durum.setText(f"Otomatik görev başlatıldı: {len(klasorler)} klasör yedekleniyor...")
        self.bar_dosya.setValue(0)
        self.bar_genel.setValue(0)
        self.btn_ertele.setVisible(False)
        self.btn_oto_durdur.setVisible(True)
        
        self.aktif_motor = CokluKlasorYuklemeIslemi(klasorler, self.sunucu_url, self.bilet)
        self.aktif_motor.dosya_ilerleme.connect(self.pano_dosya_guncelle)
        self.aktif_motor.genel_ilerleme.connect(self.bar_genel.setValue)
        self.aktif_motor.durum_guncelle.connect(self.lbl_pano_durum.setText)
        self.aktif_motor.tamamlandi.connect(self.oto_gorev_tamamlandi)
        self.aktif_motor.start()

    def aktif_islemi_iptal_et(self):
        if self.aktif_motor and self.aktif_motor.isRunning():
            self.aktif_motor.durdur()
            self.lbl_pano_durum.setText("Görev iptal ediliyor...")

    def oto_gorev_tamamlandi(self, basarili, mesaj):
        self.btn_oto_durdur.setVisible(False)
        self.lbl_pano_durum.setText(mesaj)
        yeni_durum = "Tamamlandı" if basarili else "Hata/İptal"
        
        if not basarili:
            self.hata_kaydi_ekle("Otomatik Yedekleme", mesaj)

        if self.aktif_gorev_id:
            try:
                requests.post(
                    f"{self.sunucu_url}/gorev-guncelle", 
                    data={"gorev_id": self.aktif_gorev_id, "durum": yeni_durum}, 
                    headers=self.bilet, 
                    timeout=TIMEOUT
                )
            except requests.RequestException:
                pass
            self.aktif_gorev_id = None
            
        self.sunucu_senkronizasyonu()

    def pano_dosya_guncelle(self, yuzde, dosya_adi):
        self.bar_dosya.setValue(yuzde)
        self.lbl_pano_durum.setText(f"Yükleniyor: {dosya_adi}")

    def closeEvent(self, event):
        """Uygulama kapatılırken thread ve zamanlayıcıları temizle, geçici dosyaları sil."""
        try:
            temp_onizleme_temizle()
        except Exception:
            pass

        if hasattr(self, 'scheduler') and self.scheduler.running:
            try:
                self.scheduler.shutdown(wait=False)
            except Exception:
                pass
            
        if self.aktif_motor and self.aktif_motor.isRunning():
            try:
                self.aktif_motor.durdur()
                self.aktif_motor.wait(1000)
            except Exception:
                pass
            
        if self.manuel_motor and self.manuel_motor.isRunning():
            try:
                self.manuel_motor.durdur()
                self.manuel_motor.wait(1000)
            except Exception:
                pass
            
        event.accept()

# --- GLOBAL CRASH & HATA YAKALAYICI ---
def global_hata_yakalayici(exctype, value, tb):
    """Beklenmeyen istisnaların uygulamayı çökertmesini engeller."""
    hata_metni = "".join(traceback.format_exception(exctype, value, tb))
    print(f"Kritik Hata Yakalandı:\n{hata_metni}", file=sys.stderr)
    try:
        if hasattr(BulutSistemiApp, 'ornek') and BulutSistemiApp.ornek:
            BulutSistemiApp.ornek.hata_kaydi_ekle("Kritik Sistem Hatası", str(value)[:80])
    except Exception:
        pass

sys.excepthook = global_hata_yakalayici

if __name__ == "__main__":
    uygulama = QApplication(sys.argv)
    uygulama.setStyleSheet(STYLE_SHEET) 
    pencere = BulutSistemiApp()
    pencere.show()
    sys.exit(uygulama.exec())
