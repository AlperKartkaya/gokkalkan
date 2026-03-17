# 🚀 Gökkalkan Tech Stack & Pipeline

Bu doküman, Gökkalkan Hava Savunma Sistemi'nin yazılım mimarisini, kullanılan teknolojileri ve veri akış boru hattını (pipeline) tanımlar. Yazılım ekibinin araştırmaları için temel başvuru kaynağıdır.

## 1. Sistem Mimari Özeti (High-Level Architecture)
Gökkalkan yazılım mimarisi; manuel/otonom görev yönetimi, hedef tespit-takip-sınıflandırma, hareket kontrol, güvenlik denetimi, operatör arayüzü ve telemetri/log katmanlarından oluşan modüler bir yapıdır. Sistem ana bilgisayar olarak Raspberry Pi 5 üzerinde koşar ve alt donanımlarla iletişim kurar.

---

## 2. Kullanılan Teknolojiler ve Dokümantasyonlar (Tech Stack)

### 2.1. Donanım ve İşletim Sistemi (Hardware & OS)
* **Ana Hesaplama Birimi:** Raspberry Pi 5 (8GB). Görüntü işleme ve görev yönetimi için ana bilgisayar olarak kullanılır.
* **AI Hızlandırıcı:** Hailo AI HAT+ (26 TOPS, Hailo-8)
* **Kamera Modülü:** Camera Module 3 veya Global Shutter özellikli kamera. Düşük gecikmeli görüntü ve hareketli hedef takibi için kullanılır.
* **Dokümantasyon Kaynakları:**
    * [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/)
    * [Hailo Developer Zone](https://hailo.ai/developer-zone/)

### 2.2. Algı ve Görüntü İşleme Katmanı (Perception & AI)
* **Kamera Sürücüsü:** Picamera2 0.3.x. Kamera sürüşü, düşük gecikmeli kare akışı ve senkron veri üretimi sağlar.
* **Ön İşleme:** OpenCV 4.10.
* **Yapay Zeka Çıkarım (Inference):** HailoRT 4.x. AI HAT+ üzerinde gerçek zamanlı tespit ve çıkarım yapar.
* **Nesne Tespiti ve Takip Algoritmaları:** Sistem tasarımı YOLOX , ByteTrack ve SORT/DeepSORT mimarilerini referans almaktadır.
* **Dokümantasyon Kaynakları:**
    * [Picamera2 Manual](https://picamera.readthedocs.io/)
    * [OpenCV 4.x Documentation](https://docs.opencv.org/4.x/)
    * [HailoRT GitHub Repository](https://github.com/hailo-ai/hailort)

### 2.3. Haberleşme ve Görev Çekirdeği (Middleware & Comm)
* **Ara Katman (Middleware):** ROS / ROS2 (Robot Operating System) mimarisi.
* **Donanım Haberleşmesi:** pySerial 3.5 ve python-can 4.x. Raspberry Pi ile MCU (Motor Kontrolcüsü) arasında komut/geri bildirim iletişimi sağlar.
* **Dokümantasyon Kaynakları:**
    * [ROS 2 Documentation](https://docs.ros.org/en/humble/index.html)
    * [pySerial Documentation](https://pyserial.readthedocs.io/en/latest/)
    * [python-can Documentation](https://python-can.readthedocs.io/en/stable/)

### 2.4. Operatör Arayüzü (Frontend / GUI)
* **Arayüz Framework:** PySide6 6.7.x.
* **Görevi:** Mod seçimi, canlı görüntü, hedef bilgisi, uyarılar ve operatör komutları bu katmanda yönetilir.
* **Dokümantasyon Kaynakları:**
    * [Qt for Python (PySide6) Documentation](https://doc.qt.io/qtforpython-6/)

### 2.5. Test ve Telemetri (QA & Logging)
* **Test Altyapısı:** pytest 8.x.
* **Görevi:** Zaman damgalı log/replay, senaryo testleri, regresyon ve entegrasyon doğrulaması gerçekleştirir.
* **Dokümantasyon Kaynakları:**
    * [pytest Documentation](https://docs.pytest.org/en/latest/)

---

## 3. Yazılım Boru Hattı (Data Pipeline)
Verinin kameradan girip motor hareketine dönüşene kadar izlediği yol (Şekil 2 Yazılım Arayüz Şeması baz alınarak):

1.  **Algı (Perception):** Picamera2 üzerinden alınan ham görüntü, OpenCV ile ön işlemeye sokulur ve doğrudan Hailo-8 (AI HAT+) birimine aktarılarak yapay zeka çıkarımı (bounding box/sınıflandırma) elde edilir.
2.  **Karar ve Takip (Logic):** Çıkarım sonuçları Görev Çekirdeğine (Raspberry Pi) gelir. Hedef Takip / Sınıflandırma modülü bu verileri işler ve Atış Kontrol + Güvenlik katmanına iletir.
3.  **Aksiyon (Hardware Action):** Güvenlik denetiminden geçen komutlar, donanım katmanındaki Pan/Tilt Sürücü MCU'suna ve Atış Mekanizmasına iletilir. Eş zamanlı olarak Sensörler ve Emniyet Girişleri donanımı denetler.
4.  **Kullanıcı ve Telemetri (UI & Logging):** Tüm bu süreç boyunca Canlı Görüntü ve uyarılar Operatör Arayüzüne (PySide6) basılır. Görev yöneticisindeki tüm durum değişiklikleri Telemetri, Log, Replay modülü tarafından zaman damgalı olarak kaydedilir.