# Python bağımlılık kilitleri

- `backend.lock`: Backend, CAN ve TFA50-L UART çalışma bağımlılıkları.
- `dev.lock`: Backend kilidine ek test/coverage araçları.
- `perception-dev.lock`: Pi olmayan geliştirme/CI ve augmentation için NumPy ve headless OpenCV.
- `training-dev.lock`: Python 3.11 üzerinde YOLO araştırma/smoke eğitimi için kilitli Ultralytics/Torch yığını (`training.in` kaynağından üretilir).

Hedef Raspberry Pi’de NumPy, OpenCV ve Picamera2 aynı Raspberry Pi OS Trixie
deposundan `python3-numpy`, `python3-opencv` ve `python3-picamera2` olarak
kurulur. Böylece Picamera2 ile uyumsuz ikinci bir pip OpenCV yığını yaratılmaz.
Kesin apt paketi sürümleri temiz imaj kurulumu sırasında
`deploy/pi/installed-packages.lock` çıktısına kaydedilir; bu çıktı makine kanıtı
olduğu için repoya değil release/telemetri paketine konur.

```bash
# Backend + test
python3 -m pip install -r requirements/dev.lock
python3 -m pip install -e . --no-deps

# Pi olmayan perception geliştirmesi
python3 -m pip install -r requirements/perception-dev.lock
python3 -m pip install -e . --no-deps
```

AI HAT+ 26 TOPS için `dkms`, `hailo-all` ve `rpicam-apps` apt paketleri
`deploy/pi/manifest.toml` içinde kilitlidir. Model ağırlıkları/derlenmiş HEF
artefaktları bu kilitlerin parçası değildir ve repoya eklenmez; kabul edilen
modelin kaynağı, sınıf listesi ve SHA-256 değeri release manifestinde tutulur.
