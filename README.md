# Gökkalkan

Gökkalkan, TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması için geliştirilen yazılım, simülasyon ve KTR/rapor hazırlık çalışma alanıdır. Nihai gereksinim kaynağı `docs/sartname_v1_3.pdf` ve aranabilir metin karşılığı `docs/sartname_v1_3.txt` dosyalarıdır.

## Güncel Durum

- `frontend/` — React + Vite + TypeScript tabanlı **yarışma eğitim simülatörü**. Aşama 1/2/3 senaryolarını görselleştirir.
- `backend/` — **Çalışan Operatör API**. Varsayılan `SIM`, sanal CAN için `HIL`; `LIVE` fiziksel interlock/readiness bootstrap tamamlanana kadar fail-closed kilitlidir. JSONL telemetri, Safety Gate ve görev endpoint’leri aktiftir.
- `backend/hardware_mock/` — **Pico MCU simülatörü** (`mcu_simulator.py`). Gerçek Pico olmadan tam CAN protokol testi.
- `perception/` — **Kamera nodu + HSV renk takipçisi + perception bridge**. RPi Camera Module 3 (Picamera2) veya USB kamera (OpenCV) otomatik seçimi.
- Tek sahipli **Mission Core**, sürümlü komut/olay envelope’ları, immutable state
  snapshot’ı, SSE operatör akışı ve ayrı perception process sınırı
  uygulanmıştır.
- İmalat öncesi sıradaki işler; Pico firmware, canlı arm/interlock zinciri,
  gerçek kamera/TFA50-L adapter’ları, HIL ve uçtan uca fault-injection
  testleridir. Kanonik sıra: `docs/imalat_oncesi_yazilim_todo.md`.

## Komut Zinciri

```
Operatör Paneli (UI)
      ↓  HTTP POST /manual-aim  /fire-intent
Backend API → bounded CommandEnvelope kuyruğu
      ↓  tek sahipli Mission Core reducer + immutable snapshot/SSE
OperatorService + Safety Gate
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

### Temiz geliştirme kurulumu

```bash
npm run setup
npm run dev:check   # Backend + UI health kontrolü; tarayıcı açmadan kapanır
npm run desktop     # SIM backend + operatör paneli
npm run doctor
```

Python paketi `.venv` içine editable kurulur; `PYTHONPATH` gerekmez. Kilit
dosyaları `requirements/`, runtime profilleri `config/runtime/`, Raspberry Pi
kurulum sözleşmesi `deploy/pi/` altındadır.

### Geliştirme — Sanal CAN (donanım olmadan)

**Linux / RPi5:**
```bash
bash scripts/setup_virtual_can.sh          # vcan0 kur

# Terminal 1: Pico MCU simülatörü
python3 backend/hardware_mock/mcu_simulator.py --channel vcan0 --bustype socketcan

# Terminal 2: Backend
.venv/bin/gokkalkan operator-api --config config/runtime/hil.toml

# Terminal 3: Operatör paneli
npm --prefix frontend run dev
# http://127.0.0.1:5173/?operator=1
```

**macOS (aynı process içinde python-can virtual + MCU simülatörü):**
```bash
.venv/bin/gokkalkan operator-api --config config/runtime/hil.toml \
  --vcan
npm --prefix frontend run dev
# http://127.0.0.1:5173/?operator=1
```

`npm run desktop` kendi güvenli SIM backend’ini de başlatır; bu nedenle ayrı
HIL backend’i çalışırken yalnız frontend dev server kullanılır.

### LIVE hazırlığı (RPi5 + Pico + can0)

Genel CLI fiziksel preflight üretmez ve `LIVE` başlatmayı reddeder. Gerçek CAN
adapter’ı; `docs/adr/001-target-runtime.md` ve `docs/adr/002-mcu-can.md`
gereğince fiziksel interlock, backend readiness ve ayrı arm zinciri tamamlandıktan
sonra güvenli bootstrap üzerinden açılacaktır. Bu kapı tamamlanmadan `can0`
komutu dokümante edilmez.

### Simülatör

```bash
cd frontend && npm install && npm run dev
```

## Backend API Endpoint'leri

| Endpoint | Yöntem | Açıklama |
|----------|--------|----------|
| `/state` | GET | Tüm sistem durumu |
| `/state/stream?after=N` | GET | SSE üzerinden immutable state snapshot akışı |
| `/health` | GET | Backend sağlık |
| `/commands/{commandId}` | GET | Kuyruktaki/tamamlanan komutun izlenebilir sonucu |
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
.venv/bin/python -m pytest -v

# Kapsama raporu (pytest-cov gerekli)
.venv/bin/python -m pytest --cov=gokkalkan_backend --cov-report=term-missing

# Hızlı doğrulama
.venv/bin/python -m pytest -q

# Frontend tip kontrolü
cd frontend && npm run typecheck && npm run build
```

## Önemli Dokümanlar

- `docs/sartname_v1_3.txt` — şartname metni; gereksinimlerde final otorite.
- `docs/requirements_source.md` — şartname sürümü, hash ve güncelleme prosedürü.
- `docs/requirements_traceability.md` — requirement → modül/test/telemetri/video matrisi.
- `docs/delivery_video_plan.md` — güncel takvim ve sıralı video kanıt planı.
- `docs/adr/` — kabul edilmiş çalışma ortamı, CAN ve kamera/LiDAR kararları.
- `docs/message_contracts.md` — Mission Core komut/olay şeması, sıralama ve
  geriye uyumluluk politikası.
- `config/runtime/` — doğrulanan SIM/HIL/LIVE ayar şeması ve profilleri.
- `deploy/pi/` ve `deploy/systemd/` — temiz Pi kurulumu ve servis sözleşmeleri.
- `requirements/` — backend, test ve perception bağımlılık kilitleri.
- `docs/tech_stack.md` — teknik yönelim, donanım mimarisi, CAN protokolü ve safety gate.
- `docs/imalat_oncesi_yazilim_todo.md` — imalat öncesi yazılım yol haritası.
- `docs/operator_panel_interfaces_roadmap.md` — gerçek operatör paneli arayüz tabloları (KTR).
- `reports/diyagramlar/mermaid_kodu/ktr_mermaid_diagrams.md` — KTR Mermaid diyagramları.

## Takım ve Teslim Disiplini

- Yazılım ekibi: Alper, Ebubekir, Enes, Akif.
- Makine ekibi: mekanik tasarım ve imalat.
- OTR: en fazla 10 sayfa.
- KTR: en fazla 30 sayfa.
- Görev Kabiliyeti Gösterimi Videosu: tek YouTube linki, 720p+, 2-5 dakika, şartnamedeki yetenek sırasına uygun.
- Sistem Kabiliyeti Videoları son teslimi: **17.08.2026 17:00**.

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
