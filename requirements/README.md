# Python bağımlılık kilitleri

- `backend.lock`: Backend, CAN ve TFA50-L UART çalışma bağımlılıkları.
- `dev.lock`: Backend kilidine ek test/coverage araçları.
- `perception-dev.lock`: Pi olmayan geliştirme/CI ve augmentation için NumPy ve headless OpenCV.
- `training-dev.lock`: Python 3.11 üzerinde YOLO araştırma/smoke eğitimi ve
  offline SAHI sliced-inference parity/ablation çalışmaları için kilitli
  Ultralytics/Torch/SAHI yığını (`training.in` kaynağından üretilir).
- `synthetic-render.lock`: Python 3.11 geliştirme makinesinde 3MF inceleme,
  şema doğrulama, contact sheet ve BlenderProc render araçları
  (`synthetic-render.in` kaynağından üretilir). Pi/LIVE imajına kurulmaz.

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

# Pi olmayan CAD/sentetik render geliştirmesi
uv venv .venv-synthetic --python 3.11
uv pip install --python .venv-synthetic/bin/python \
  -r requirements/synthetic-render.lock
```

AI HAT+ 26 TOPS için `dkms`, `hailo-all` ve `rpicam-apps` apt paketleri
`deploy/pi/manifest.toml` içinde kilitlidir. Model ağırlıkları/derlenmiş HEF
artefaktları bu kilitlerin parçası değildir ve repoya eklenmez; kabul edilen
modelin kaynağı, sınıf listesi ve SHA-256 değeri release manifestinde tutulur.

SAHI Pi runtime'ına pip OpenCV ile birlikte kurulmaz. Canlı süreç
`perception/src/sahi_geometry.py` içindeki SAHI-parity tile/merge sözleşmesini ve
`HailoSahiAdapter` batch sınırını kullanır; resmî SAHI paketi eğitim/offline
referans ortamında tutulur.
