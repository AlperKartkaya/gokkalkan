# Gökkalkan Canlı Kamera, Taret Kontrolü ve LiDAR Entegrasyonu

## 🎯 Tamamlanan Geliştirmeler

### 1. 🧹 Sahte / Simülasyon Verilerinin Temizlenmesi
- Arayüzde yer alan sentetik CAD yer tutucuları ve demo hedef verileri temizlendi.
- Hedef tespit listesi ve yapay zeka paneli, doğrudan kamera ve algı motorundan (`gokkalkan-perception`) gelen canlı verilere bağlandı.
- Görüş açısında hedef olmadığında ekran sade ve temiz bir şekilde optik tarama durumunu göstermektedir.

### 2. 🎮 WASD & D-Pad Taret Kontrolü
- **Klavyeden Doğrudan Kontrol:** Hem Operatör Panelinde hem de Canlı Yapay Zeka / Kamera Panelinde `W`, `A`, `S`, `D` ve yön okları (`▲`, `▼`, `◀`, `▶`) ile pan/tilt taretini anında hareket ettirme yeteneği eklendi.
- **Acil Durdurma:** `Space` tuşuna basıldığında motorlar anında acil durdurma (E-Stop) durumuna geçer.
- **Ekran Üzeri D-Pad:** Açı adımı seçimi (`0.25°`, `0.5°`, `1.0°`, `2.0°`, `5.0°`) ve canlı pan/tilt açı göstergesi ile dokunmatik/fare kontrollü yönlendirme arayüzü entegre edildi.

### 3. 📡 1D LiDAR UART Donanım Bağlantısı (Raspberry Pi 5 GPIO)
- **Pin Konfigürasyonu:**
  - **Pin 8 (GPIO 14 / TXD0):** LiDAR RX hattı
  - **Pin 10 (GPIO 15 / RXD0):** LiDAR TX hattı
  - **Pin 9:** Ground (GND)
- **Kalıcı Aygıt:** `/boot/firmware/config.txt` dosyasına `dtoverlay=uart0-pi5` eklenerek `/dev/ttyAMA0` seri portu kalıcı hale getirildi.
- **Arayüz HUD:** Kamera görüntüsü üzerinde canlı LiDAR menzil okuması (metre cinsinden) ve bağlantı durumu HUD olarak eklendi.

---

## 🚀 Canlı Sisteme Bağlanma ve Test Rehberi

Raspberry Pi üzerinde servisler arkaplanda sürekli çalışmaktadır. Tarayıcınızdan arayüze ve canlı kamera akışına bağlanmak için:

### 1. SSH Tünelini Başlatın (Windows Terminal / PowerShell):
```powershell
ssh -N -L 4173:127.0.0.1:4173 -L 8088:127.0.0.1:8088 -L 8090:127.0.0.1:8090 gokkalkan@gokkalkan
```

### 2. Tarayıcınızda Açın:
- **Operatör & Görev Paneli:** [http://127.0.0.1:4173](http://127.0.0.1:4173)
- **Canlı Optik, LiDAR ve Taret Paneli:** [http://127.0.0.1:4173/?surface=ai](http://127.0.0.1:4173/?surface=ai)
- **Doğrudan Ham Kamera Yayını:** [http://127.0.0.1:8090/camera/live.mjpg](http://127.0.0.1:8090/camera/live.mjpg)

### 3. Kontrol Testi:
1. Sayfayı açtıktan sonra klavyeden **W**, **A**, **S**, **D** tuşlarına basarak tareti yönlendirebilirsiniz.
2. LiDAR sensörünüz pin 8, 9 ve 10'a bağlı olduğunda sağ üstteki LiDAR HUD'ında anlık mesafe belirecektir.
