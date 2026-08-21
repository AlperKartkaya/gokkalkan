# 🚀 Gökkalkan — Arduino Uno Motor & 1D LiDAR Gerçek Zamanlı Test Rehberi

Bu dizin, Gökkalkan taret mekanizmasının **Arduino Uno + DM542 step motor sürücüleri** ve **1D LiDAR (TFA50-L / TF-Luna / TFmini)** sensörü ile test edilmesi için geliştirilmiş firmware ve Python teşhis araçlarını içerir.

---

## 📌 1. Fiziksel Pin ve Bağlantı Şemaları

### A. Arduino Uno -> DM542 Step Sürücü Bağlantıları

| Sinyal | Arduino Uno Pini | DM542 Klemensi | Açıklama |
| :--- | :---: | :---: | :--- |
| **1. Motor (PAN) Pals** | **Pin 2** | **1. Sürücü PUL+** | Pan ekseni adım sinyali |
| **1. Motor (PAN) Yön** | **Pin 3** | **1. Sürücü DIR+** | Pan ekseni yön sinyali (CW/CCW) |
| **2. Motor (TILT) Pals** | **Pin 4** | **2. Sürücü PUL+** | Tilt ekseni adım sinyali |
| **2. Motor (TILT) Yön** | **Pin 5** | **2. Sürücü DIR+** | Tilt ekseni yön sinyali (CW/CCW) |
| **Ortak Eksi (GND)** | **Arduino GND** | **Tüm PUL- ve DIR-** | Her iki sürücünün eksi uçları (Ortak Katot) |
| **Boşta (Enable)** | — | **ENA+ ve ENA-** | Kesinlikle boş bırakılmalıdır |

> [!IMPORTANT]
> **DM542 DIP Switch Ayarları:**
> - Mikroadım (SW5-SW8): **`1600 Pulse/Rev`** (1 tur = 1600 adım = ~4.444 adım/derece)
> - Akım ayarı (SW1-SW3): Motorunuza uygun olarak **`2.5A - 3.5A`** aralığı.

---

### B. 1D LiDAR (TFA50-L / TF-Luna / TFmini) USB-UART Bağlantısı

| LiDAR Kablosu | Renk | USB-UART Dönüştürücü | Açıklama |
| :--- | :---: | :---: | :--- |
| **VCC (Besleme)** | Kırmızı | **5V** (veya harici 5V 1A) | Kararlı 5V DC güç |
| **GND (Toprak)** | Siyah | **GND** | Ortak toprak |
| **TXD (Verici)** | Beyaz / Yeşil | **RXD** | LiDAR Veri Çıkışı -> USB Girişi |
| **RXD (Alıcı)** | Yeşil / Beyaz | **TXD** | LiDAR Komut Girişi <- USB Çıkışı |

---

## 🛠️ ADIM 1: Firmware'i Arduino Uno'ya Yükleme

1. Arduino Uno'yu bilgisayara USB kablosuyla bağlayın.
2. Arduino IDE ile [`realtimetesting/arduino_uno/arduino_uno.ino`](./arduino_uno/arduino_uno.ino) dosyasını açın.
3. **Araçlar (Tools) -> Kart -> Arduino Uno** ve ilgili **COM portunu** seçin.
4. **Yükle (Upload)** butonuna basarak kodu karta yazın.

---

## 💻 ADIM 2: Gerekli Paketlerin Kurulumu

```bash
pip install pyserial
```
*(Raspberry Pi / Linux için: `sudo apt install -y python3-serial && sudo usermod -a -G dialout $USER`)*

---

## 🎮 ADIM 3: Test Araçlarını Çalıştırma

### 1. 🕹️ Gerçek Zamanlı WASD Klavye Motor Kontrolcüsü (ÖNERİLEN)
Klavyeden anlık tuşlara basarak motorları adım adım veya kesintisiz sürmek için:

```bash
python realtimetesting/wasd_motor_control.py
```

**Klavye Tuş Haritası:**
* `[ W ]` veya `[ ↑ ]` : **TILT Yukarı** (Saat yönü - CW)
* `[ S ]` veya `[ ↓ ]` : **TILT Aşağı** (Ters yön - CCW)
* `[ A ]` veya `[ ← ]` : **PAN Sola** (Ters yön - CCW)
* `[ D ]` veya `[ → ]` : **PAN Sağa** (Saat yönü - CW)
* `[ SPACE ]` veya `[ X ]` : **ACİL DURDUR (STOP)**
* `[ + ]` / `[ - ]` : **Adım Açısını Ayarla** (`0.25°`, `0.5°`, `1.0°`, `2.0°`, `5.0°`, `10.0°`)
* `[ 1 ]` / `[ 2 ]` / `[ 3 ]` : **Hız Kademesi** (1: Yavaş, 2: Normal, 3: Hızlı)
* `[ C ]` : **Mod Geçişi** (Adım/Pulse Modu ⟷ Kesintisiz Jog Modu)
* `[ R ]` : **Konum Sayacını Sıfırla** (Home/Reset)
* `[ Q ]` veya `[ ESC ]` : **Güvenli Çıkış**

---

### 2. 📡 1D LiDAR Canlı Teşhis ve Test Monitörü
LiDAR sensöründen gelen canlı mesafeyi (m/cm), sinyal gücünü, frekansı (Hz) ve ham hex baytları izlemek için:

```bash
python realtimetesting/test_lidar.py
```
*(Baud rate ve port otomatik tespit edilir. İstenirse: `python realtimetesting/test_lidar.py --port COM4 --baud 460800`)*

**Özellikler:**
* TFA50-L (4-Bayt @ 460800 baud) ve TF-Luna/TFmini (9-Bayt @ 115200 baud) protokollerini otomatik tanır.
* Canlı renkli mesafe çubuğu ve örnekleme hızı (FPS/Hz) gösterir.
* Sinyal kopukluğu veya hatalı bağlantıda otomatik teşhis önerileri sunar.

---

### 3. 📋 Menülü Motor Test Paneli
Süreli (15 saniye) testler ve menü üzerinden motor doğrulama için:

```bash
python realtimetesting/interactive_motor_control.py
```

---

### 4. ⚡ Tek Satırlık Parametreli Hızlı Test Scripti

```bash
# Pan motorunu 15 saniye saat yönünde döndür:
python realtimetesting/test_motor_15s.py --motor pan --duration 15

# Tilt motorunu 10 saniye ters yönde döndür:
python realtimetesting/test_motor_15s.py --motor tilt --duration 10 --direction CCW

# Her iki motoru birlikte test et:
python realtimetesting/test_motor_15s.py --motor both --duration 15
```

---

## 📁 Dizin Yapısı

```text
realtimetesting/
├── README.md                          # Test, pin ve kablolama rehberi
├── arduino_uno/
│   └── arduino_uno.ino                # Arduino Uno firmware kaynak kodu (v2.0 - Step/Jog/WASD destekli)
├── wasd_motor_control.py              # Gerçek zamanlı WASD klavye motor kontrolcüsü
├── test_lidar.py                      # Canlı 1D LiDAR teşhis ve test monitörü
├── interactive_motor_control.py       # İnteraktif numaralı menü test paneli
└── test_motor_15s.py                  # CLI parametreli 15 sn test aracı
```
