# Gökkalkan

Gökkalkan, TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması için geliştirilen yazılım, simülasyon ve KTR/rapor hazırlık çalışma alanıdır. Nihai gereksinim kaynağı `docs/sartname_v5.pdf` ve aranabilir metin karşılığı `docs/sartname_v5.txt` dosyalarıdır.

## Güncel Durum

- `frontend/` — React + Vite + TypeScript tabanlı **yarışma eğitim simülatörü**. Aşama 1/2/3 senaryolarını görselleştirir.
- `backend/` — **Çalışan Operatör API**. Dry-run (geliştirme) ve **gerçek CAN donanım** modlarını destekler. JSONL telemetri, Safety Gate ve tüm yarışma endpoint'leri aktif.
- `backend/hardware_mock/` — **Pico MCU simülatörü** (`mcu_simulator.py`). Gerçek Pico olmadan tam CAN protokol testi.
- `perception/` — **Kamera nodu + HSV renk takipçisi + perception bridge**. RPi Camera Module 3 (Picamera2) veya USB kamera (OpenCV) otomatik seçimi.
- Gerçek donanım bağlamak için kalan tek eksik: **Pico RP2040 firmware** (CAN alıcı, STEP/DIR üretici, enkoder okuma).

## Komut Zinciri

```
Operatör Paneli (UI)
      ↓  HTTP POST /manual-aim  /fire-intent
Backend API (OperatorService + Safety Gate)
      ↓  HardwareAdapterBase.execute()
CanMcuAdapter — python-can / socketcan
      ↓  CAN bus 500kbps (SN65HVD230 transceiver)
Pico RP2040 (MCU)
      ↓  STEP/DIR darbeleri
DM542 → NEMA23 pan ekseni / NEMA17 tilt ekseni
```

**E-Stop yolu (çift güvence):**
```
Schneider Mantar Buton → Pico GPIO → CAN 0x201 → CanMcuAdapter → set_estop() → Safety Gate
                                                                       ↑
RPi5 GPIO header (GpioEStopMonitor, ikincil) ─────────────────────────┘
```

## Hızlı Başlangıç

### Geliştirme — Sanal CAN (donanım olmadan)

**Linux / RPi5:**
```bash
bash scripts/setup_virtual_can.sh          # vcan0 kur

# Terminal 1: Pico MCU simülatörü
python3 backend/hardware_mock/mcu_simulator.py --channel vcan0 --bustype socketcan

# Terminal 2: Backend
PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server

# Terminal 3: Operatör paneli
npm run desktop
```

**macOS (python-can virtual, OS kurulum gerektirmez):**
```bash
python3 backend/hardware_mock/mcu_simulator.py --channel test --bustype virtual
PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server
npm run desktop
```

### Gerçek Donanım (RPi5 + Pico + can0)

```bash
sudo ip link set can0 up type can bitrate 500000

GOKKALKAN_CAN_CHANNEL=can0 GOKKALKAN_CAN_BUSTYPE=socketcan \
  PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server

python3 perception/src/perception_bridge.py --stage 2 --url http://127.0.0.1:8088

npm run desktop
```

### Simülatör

```bash
cd frontend && npm install && npm run dev
```

## Backend API Endpoint'leri

| Endpoint | Yöntem | Açıklama |
|----------|--------|----------|
| `/state` | GET | Tüm sistem durumu |
| `/health` | GET | Backend sağlık |
| `/hardware/health` | **GET** | CAN bağlantısı ve Pico MCU durumu |
| `/mode` | POST | Mod değiştir |
| `/stage` | POST | Aşama/tur değiştir |
| `/manual-aim` | POST | Manuel pan/tilt komutu niyeti |
| `/fire-intent` | POST | Ateş niyeti |
| `/tracks/update` | **POST** | Perception bridge track besleme |
| `/estop` | **POST** | E-Stop tetikle / temizle |
| `/telemetry/export` | GET | JSONL telemetri dışa aktarma |
| `/replay` | GET | Komut/olay tekrar oynatma |
| `/readiness` | GET | Final fazı hazırlık raporu |
| `/sensor-frames` | GET | Radar/LiDAR biçimli replay verisi |

## Testler

```bash
# Tüm testler
PYTHONPATH=backend/src python3 -m pytest tests/ -v

# Kapsama raporu (pytest-cov gerekli)
PYTHONPATH=backend/src python3 -m pytest tests/ --cov=gokkalkan_backend --cov-report=term-missing

# Hızlı doğrulama
PYTHONPATH=backend/src python3 -m pytest tests/ -q

# Frontend tip kontrolü
cd frontend && npm run typecheck && npm run build
```

## Önemli Dokümanlar

- `docs/sartname_v5.txt` — şartname metni; gereksinimlerde final otorite.
- `docs/tech_stack.md` — teknik yönelim, donanım mimarisi, CAN protokolü ve safety gate.
- `integration_todo.md` — donanım entegrasyon yol haritası ve tamamlanma durumu.
- `docs/operator_panel_interfaces_roadmap.md` — gerçek operatör paneli arayüz tabloları (KTR).
- `reports/diyagramlar/mermaid_kodu/ktr_mermaid_diagrams.md` — KTR Mermaid diyagramları.

## Takım ve Teslim Disiplini

- Yazılım ekibi: Alper, Ebubekir, Enes, Akif.
- Makine ekibi: mekanik tasarım ve imalat.
- OTR: en fazla 10 sayfa.
- KTR: en fazla 30 sayfa.
- Görev Kabiliyeti Gösterimi Videosu: tek YouTube linki, 720p+, 2-5 dakika, şartnamedeki yetenek sırasına uygun.

## Güvenlik İlkesi

UI doğrudan motor veya imha hattı sürmez. Komut akışı zorunlu olarak şu zincirden geçer:

```
Operatör Paneli → Backend API → Safety Gate → HardwareAdapterBase → CAN → Pico MCU → DM542
```

Safety Gate; **E-Stop, hareket yasak bölge, atış yasak bölge, mod uyumu, hedef/menzil kapısı, bağlantı sağlığı ve arm durumunu** UI'dan bağımsız olarak kontrol eder.

## Desktop Operatör Paneli

```bash
npm run desktop        # backend + frontend + desktop window tek komutla
npm run desktop:check  # hızlı doğrulama
```
