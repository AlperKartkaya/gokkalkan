# 🚀 Gökkalkan — Arduino Uno & DM542 Çift Motor Test Rehberi

Bu dizin, Gökkalkan taret mekanizmasının **Arduino Uno** ve **DM542** step motor sürücüleri üzerinden test edilmesi için geliştirilmiş firmware ve Python teşhis araçlarını içerir.

---

## 📌 Fiziksel Pin ve Bağlantı Şeması

| Sinyal | Arduino Uno Pini | DM542 Klemensi | Açıklama |
| :--- | :---: | :---: | :--- |
| **1. Motor (PAN) Pals** | **Pin 2** (Üzerinde 2 yazan) | **1. Sürücü PUL+** | Pan ekseni adım sinyali |
| **1. Motor (PAN) Yön** | **Pin 3** (Üzerinde 3 yazan) | **1. Sürücü DIR+** | Pan ekseni yön sinyali (CW/CCW) |
| **2. Motor (TILT) Pals** | **Pin 4** (Üzerinde 4 yazan) | **2. Sürücü PUL+** | Tilt ekseni adım sinyali |
| **2. Motor (TILT) Yön** | **Pin 5** (Üzerinde 5 yazan) | **2. Sürücü DIR+** | Tilt ekseni yön sinyali (CW/CCW) |
| **Ortak Eksi (GND)** | **Arduino GND** | **Tüm PUL- ve DIR-** | Her iki sürücünün eksi uçları |
| **Boşta (Enable)** | — | **ENA+ ve ENA-** | Kesinlikle boş bırakılmalıdır |

> [!IMPORTANT]
> **DM542 DIP Switch Ayarı:** Sürücüler üzerindeki mikroadım anahtarlarını (SW5-SW8) **`1600 Pulse/Rev`** (1 tur = 1600 adım) konumuna getirin. Akım ayarı (SW1-SW3) için motorunuza uygun olarak **`2.5A - 3.5A`** aralığını seçin.

---

## 🛠️ ADIM 1: Kodu Arduino Uno'ya Yükleme

1. Arduino Uno'yu bilgisayarınıza bağlayın.
2. Arduino IDE ile [`realtimetesting/arduino_uno/arduino_uno.ino`](./arduino_uno/arduino_uno.ino) dosyasını açın.
3. **Araçlar (Tools) -> Kart -> Arduino Uno** ve ilgili **COM portunu** seçin.
4. **Yükle (Upload - Sol üstteki sağ ok)** butonuna basarak kodu karta atın.
5. Yükleme tamamlandıktan sonra Arduino'yu test bilgisayarınıza veya **Raspberry Pi 5'in USB portuna** takın.

---

## 💻 ADIM 2: Gerekli Paketlerin Kurulumu

### Raspberry Pi 5 (Debian Bookworm) için:
```bash
sudo apt update
sudo apt install -y python3-serial
sudo usermod -a -G dialout $USER
```

### Windows veya Sanal Ortam (venv) için:
```bash
pip install pyserial
```

---

## 🎮 ADIM 3: Test Konsolunu Çalıştırma

### 1. İnteraktif Menülü Kontrol Paneli (Önerilen)
Motorları tek tek veya birlikte seçip canlı geri sayımla test etmek için:

```bash
python realtimetesting/interactive_motor_control.py
```
*(Raspberry Pi'de `python3 realtimetesting/interactive_motor_control.py`)*

**Menü Seçenekleri:**
* `[1]` -> 1. Motoru (PAN - Pin 2/3) 15 sn çalıştır (Saat yönü - CW)
* `[2]` -> 2. Motoru (TILT - Pin 4/5) 15 sn çalıştır (Saat yönü - CW)
* `[3]` -> Her iki motoru birlikte 15 sn çalıştır
* `[4]` -> 1. Motoru ters yönde çalıştır (CCW)
* `[5]` -> 2. Motoru ters yönde çalıştır (CCW)
* `[6]` -> Özel parametreyle çalıştır (Süre ve motor seçmeli)
* `[8]` veya `[Ctrl + C]` -> **ACİL DURDUR (STOP)**

---

### 2. Tek Satırlık Hızlı Test Scripti
Belirli bir motoru parametrelerle doğrudan başlatmak için:

```bash
# 1. Motoru (PAN - Pin 2/3) 15 saniye test et:
python realtimetesting/test_motor_15s.py --motor pan --duration 15

# 2. Motoru (TILT - Pin 4/5) ters yönde 10 saniye test et:
python realtimetesting/test_motor_15s.py --motor tilt --duration 10 --direction CCW

# Her iki motoru birlikte test et:
python realtimetesting/test_motor_15s.py --motor both --duration 15
```

---

## 📁 Dizin Yapısı

```text
realtimetesting/
├── README.md                          # Test ve kablolama rehberi
├── arduino_uno/
│   └── arduino_uno.ino                # Arduino Uno firmware kaynak kodu
├── interactive_motor_control.py       # İnteraktif Python terminal kontrol paneli
└── test_motor_15s.py                  # CLI parametreli 15 sn test aracı
```
