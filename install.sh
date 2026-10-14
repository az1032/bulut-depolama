#!/usr/bin/env bash
# ==============================================================================
# Bulut Depolama Sunucusu - Otomatik Kurulum ve Servis Betiği
# Desteklenen Sistemler: Ubuntu, Debian, Oracle Linux (VPS & Cloud)
# ==============================================================================

set -e

# Renkler
KIRMIZI='\033[0;31m'
YESIL='\033[0;32m'
SARI='\033[1;33m'
MAVI='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}======================================================${NC}"
echo -e "${CYAN}   Bulut Depolama Sunucusu Kurulum Sihirbazı          ${NC}"
echo -e "${CYAN}======================================================${NC}"

# 1. Root / Sudo Yetkisi Kontrolü
if [ "$EUID" -ne 0 ]; then
    echo -e "${KIRMIZI}[HATA] Bu betiği 'sudo' yetkisiyle çalıştırmalısınız!${NC}"
    echo -e "Kullanım: sudo bash install.sh"
    exit 1
fi

MEVCUT_DIZIN=$(pwd)
KULLANICI=${SUDO_USER:-$USER}

echo -e "\n${MAVI}[1/6] Paket yöneticisi güncelleniyor ve bağımlılıklar kuruluyor...${NC}"
apt-get update -y
apt-get install -y python3 python3-pip python3-venv curl ufw iptables-persistent

# 2. Oracle Cloud ve Linux Güvenlik Duvarı (Firewall) Ayarı
VARSAYILAN_PORT=8000
echo -e "\n${MAVI}[2/6] Güvenlik Duvarı (Firewall & Port) Yapılandırılıyor...${NC}"

# Oracle Cloud Ubuntu Iptables Kuralı (Oracle'ın varsayılan DROP kuralını deler)
if command -v iptables &> /dev/null; then
    echo -e "${SARI}• Oracle Cloud / iptables kuralı ekleniyor (Port: ${VARSAYILAN_PORT})...${NC}"
    iptables -I INPUT 6 -m state --state NEW -p tcp --dport ${VARSAYILAN_PORT} -j ACCEPT 2>/dev/null || \
    iptables -I INPUT -p tcp --dport ${VARSAYILAN_PORT} -j ACCEPT 2>/dev/null || true
    
    # Kuralları kalıcı yap
    netfilter-persistent save 2>/dev/null || true
fi

# UFW Kuralı
if command -v ufw &> /dev/null; then
    echo -e "${SARI}• UFW portu açılıyor (${VARSAYILAN_PORT}/tcp)...${NC}"
    ufw allow ${VARSAYILAN_PORT}/tcp >/dev/null 2>&1 || true
fi
echo -e "${YESIL}✓ Port ${VARSAYILAN_PORT} başarıyla açıldı.${NC}"

# 3. Sunucu Şifresi Belirleme
echo -e "\n${MAVI}[3/6] Sunucu Güvenlik Şifresi...${NC}"
read -p "Sunucu için bir şifre belirleyin (Boş bırakırsanız 'esatesat16.' kullanılır): " GIRILEN_SIFRE
SIFRE=${GIRILEN_SIFRE:-esatesat16.}

# 4. Python Sanal Ortamı (Virtual Environment)
echo -e "\n${MAVI}[4/6] Python sanal ortamı hazırlanıyor ve paketler yükleniyor...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

./venv/bin/pip install --upgrade pip >/dev/null
./venv/bin/pip install -r requirements.txt >/dev/null
echo -e "${YESIL}✓ Python paketleri başarıyla yüklendi.${NC}"

# Depolama klasörü izinleri
mkdir -p BulutDepolama
chown -R ${KULLANICI}:${KULLANICI} "${MEVCUT_DIZIN}"

# 5. Systemd Kalıcı Arka Plan Servisi Oluşturma
echo -e "\n${MAVI}[5/6] Kalıcı Arka Plan Servisi (systemd) kuruluyor...${NC}"
SERVICE_YOLU="/etc/systemd/system/bulut-depo.service"

cat <<EOF > ${SERVICE_YOLU}
[Unit]
Description=Bulut Depolama ve Yedekleme Sunucusu
After=network.target

[Service]
Type=simple
User=${KULLANICI}
WorkingDirectory=${MEVCUT_DIZIN}
Environment="BULUT_SIFRE=${SIFRE}"
Environment="BULUT_HOST=0.0.0.0"
Environment="BULUT_PORT=${VARSAYILAN_PORT}"
ExecStart=${MEVCUT_DIZIN}/venv/bin/python ${MEVCUT_DIZIN}/server.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bulut-depo.service
systemctl restart bulut-depo.service

echo -e "${YESIL}✓ 'bulut-depo' servisi kuruldu ve başlatıldı.${NC}"

# 6. Genel IP Adresini Öğren ve Özeti Yazdır
echo -e "\n${MAVI}[6/6] Sunucu genel IP adresi tespit ediliyor...${NC}"
GENEL_IP=$(curl -s -4 https://ifconfig.me || curl -s -4 https://api.ipify.org || echo "SUNUCU_IP_ADRESINIZ")

echo -e "\n${YESIL}======================================================${NC}"
echo -e "${YESIL}   TEBRİKLER! KURULUM BAŞARIYLA TAMAMLANDI           ${NC}"
echo -e "${YESIL}======================================================${NC}"
echo -e "Sunucunuz arka planda 7/24 kesintisiz çalışmaya başladı."
echo -e ""
echo -e "${CYAN}İSTEMCİ (CLIENT) AYARLARINIZ:${NC}"
echo -e "  • Sunucu Adresi : ${SARI}http://${GENEL_IP}:${VARSAYILAN_PORT}${NC}"
echo -e "  • Sunucu Şifresi: ${SARI}${SIFRE}${NC}"
echo -e ""
echo -e "${CYAN}YARARLI YÖNETİM KOMUTLARI:${NC}"
echo -e "  • Servis Durumu : sudo systemctl status bulut-depo"
echo -e "  • Canlı Loglar  : sudo journalctl -u bulut-depo -f"
echo -e "  • Yeniden Başlat: sudo systemctl restart bulut-depo"
echo -e "  • Servisi Durdur: sudo systemctl stop bulut-depo"
echo -e ""
echo -e "${SARI}[ÖNEMLİ NOT - ORACLE CLOUD & AWS KULLANICILARI]:${NC}"
echo -e "Eğer bağlantı kurulamazsa, bulut servisinizin web panelinden (Oracle Console -> Virtual Cloud Networks -> Security Lists -> Ingress Rules) kısmına girip:"
echo -e "  - Source CIDR: 0.0.0.0/0"
echo -e "  - Destination Port: ${VARSAYILAN_PORT}"
echo -e "kuralını eklediğinizden emin olun."
echo -e "${YESIL}======================================================${NC}"
