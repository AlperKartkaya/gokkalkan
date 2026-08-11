# Gökkalkan İmalat Öncesi Yazılım TODO

> Amaç: Mekanik imalat tamamlandığında yazılımı ilk kez bir araya getirmek yerine; görev mantığı, güvenlik, firmware, donanım haberleşmesi, algı, telemetri, operatör arayüzü ve hata senaryolarını imalat öncesinde simülasyon ve düşük güçlü HIL masasında doğrulamak.
>
> **Durum notu (11 Ağustos 2026):** Bu dosya tamamlanan imalat öncesi
> fazların tarihsel kanıtı olarak korunur. Fiziksel imalat sonrası eksikler,
> yeni USB/Pico kararı, motor–enkoder–airsoft firmware'i, LIVE bootstrap ve
> Aşama 2/3 kabul sırası için kanonik takip belgesi
> `docs/YAZILIM_DONANIM_UCTAN_UCA_ENTEGRASYON_PLANI.md` dosyasıdır.

## Kullanım

- Bu dosya tamamlanan imalat öncesi yazılım işlerinin tarihsel takip listesidir.
- İşler yukarıdan aşağıya bağımlılık sırasıyla ele alınmalıdır.
- Bir görev tamamlandığında kutusu işaretlenmeli ve altına PR/commit/test kanıtı eklenmelidir.
- Donanım üzerinde doğrulanmayan davranış için “tamamlandı” değil, “mock/HIL üzerinde doğrulandı” ifadesi kullanılmalıdır.
- Her iş mümkünse `WP-01`–`WP-05` etiketlerinden biriyle ilişkilendirilmelidir.
- Büyük görevler ayrı issue’lara bölünebilir; bu dosyadaki kimlikler issue başlığında korunmalıdır.

## Değiştirilmeyecek temel kararlar

- Hedef bilgisayar: Raspberry Pi 5 üzerinde doğrudan 64-bit Raspberry Pi OS; hedefte sanal makine yok.
- Bu fazda ROS 2 yok. Ölçülmüş ve belgelenmiş bir ihtiyaç oluşmadan ROS workspace eklenmeyecek.
- Tam Rust yeniden yazımı yok. Backend ve algı Python, arayüz React/TypeScript, Pico firmware C/C++ kalacak.
- Safety Gate’in sahibi backend’dir. UI yalnız yüksek seviyeli komut niyeti gönderir.
- Gerçek zamanlı E-Stop/watchdog güvenliği Linux thread’lerine değil Pico firmware ve fiziksel emniyet zincirine dayanır.
- Görev state’inin tek sahibi olacak; HTTP, CAN ve sensör thread/process’leri ortak state’i doğrudan değiştirmeyecek.
- Replay modu fiziksel çıkış adapter’ını yükleyemeyecek.
- Ana menzil sensörü adayı **Benewake TFA50-L tek nokta LiDAR**’dır. Sensör, yaw ile dönen fakat silah pitch hareketine katılmayan iki yan plaka arasındaki merkezî köprü/profil üzerine yerleştirilecek; merkezî düşey kızak/direk aynı kinematiği sağladığı sürece mekanik alternatiftir.
- LiDAR yüksekliği yalnız kurulum/kalibrasyon sırasında elle ayarlanacak ve mekanik olarak kilitlenecek; bu köprü/kızak için motor, eksen veya çalışma zamanı hareket komutu yazılmayacak. Yükseklik değişikliği mevcut kalibrasyonu geçersiz kılacak.
- TFA50-L yazılımı adapter sınırının arkasında kalacak. 2D tarayıcı ancak gerçek hedef bench testinde yaw ile eşlenmiş tek nokta ölçümünün güvenilir olmadığı kanıtlanırsa fallback olarak yeniden değerlendirilecek.
- Şartname ile repo belgeleri çelişirse şartname esas alınır.

## LiDAR mekanik referansları

- `docs/images/gokkalkan_izometrik_cizim.png`: Taretin temel izometrik görünümü; dış yan plakalar yaw tablasıyla döner, iç mekanizma pitch ekseninde hareket eder.
- `docs/images/gokkalkan_izometrik_cizim_uzerinde_lidar_konumu.png`: Öncelikli çözüm; iki pitch-sabit yan plakayı birleştiren, yüksekliği elle ayarlanıp kilitlenen köprü/profil ve merkezde TFA50-L.
- `docs/images/gokkalkan_izometrik_cizim_lidar_konumu_2.png`: Alternatif çözüm; yaw tablasına bağlı, merkezî ve elle yükseltilip alçaltılabilen kızak/direk.
- Her iki çözümde de LiDAR taret yaw açısını takip eder, silahın yukarı-aşağı pitch hareketini takip etmez. Böylece silah hedefin üstüne nişan alırken menzil huzmesi hedef yüksekliğinde kalabilir.

## Her görev için tamamlanma standardı

Bir kutu ancak aşağıdakiler sağlandığında tamamlanır:

1. Davranış testle veya tekrarlanabilir komutla doğrulanmıştır.
2. Güvenlik etkisi değerlendirilmiştir; hata yolu fail-safe davranır.
3. Yeni config/protokol/schema belgelenmiştir.
4. İlgili log/telemetri olayı üretilmektedir.
5. Lint/typecheck/test çıktısı okunmuş ve başarısızlık bırakılmamıştır.
6. Commit mesajı repo Lore Commit Protocol biçimine uygundur.

---

# Faz 0 — Canlı çıkışı güvenli biçimde dondur

**Kapı:** Bu faz bitmeden gerçek motor veya imha çıkışı bağlanmaz.

- [x] **SAFE-001 — Client kaynaklı `dryRun` bypass’ını kapat** `[WP-04]`
  - `dryRun`, `physicalOutputEnabled` ve canlı arm kararı yalnız backend konfigürasyonundan gelmeli.
  - İstek payload’ı güvenlik koşullarını gevşetememeli.
  - Kabul: canlı servis + payload `dryRun=true` fiziksel adapter çağrısı üretmez.
  - Kanıt: `tests/test_operator_api.py::OperatorServiceTest::test_live_service_ignores_client_dry_run_override`; backend çalışma modu `OperatorService.dry_run` üzerinden sunucu-otoritatif hâle getirildi.

- [x] **SAFE-002 — Fiziksel adapter’ı varsayılan kapalı yap** `[WP-04]`
  - Açıkça seçilmiş backend live config, fiziksel interlock ve readiness olmadan gerçek adapter yüklenmemeli.
  - Başlangıç logu çalışma modunu `SIM`, `HIL` veya `LIVE` olarak açıkça yazmalı.
  - Kanıt: `gokkalkan_backend.runtime_mode`; `UsbSerialMcuAdapter` varsayılanı çıkışsızdır, HIL varsayılan olarak `loop://` kullanır, genel CLI preflight olmadığı için LIVE’ı fail-closed reddeder.

- [x] **SAFE-003 — Kritik bypass regresyon testlerini ekle** `[WP-04]`
  - UI/config/payload kombinasyonları denenmeli.
  - Test spy adapter ile “sıfır fiziksel çağrı” invariant’ını kanıtlamalı.
  - Kanıt: `tests/test_runtime_mode.py`, `test_live_service_ignores_client_dry_run_override`, `test_can_adapter_defaults_to_no_transmit_and_no_physical_output`.

**Faz kanıtı:** Güvenilmeyen istemci girdilerinin hiçbir kombinasyonu canlı
çıkışı etkinleştiremiyor. Kurulu paket üzerinden çalışan Python regresyon paketi
ile fiziksel CAN yetkisi olmayan adapter’ın `can0` iletim girişimi de reddedildi.

---

# Faz 1 — Kaynakları ve arayüz kararlarını sabitle

- [x] **DOC-001 — Güncel şartname yolunu ve sürümünü kanonikleştir**
  - README, AGENTS, teknik dokümanlar ve rapor bağlantıları mevcut PDF adına yönelmeli.
  - Aranabilir metin çıktısı üretilmeli; PDF son otorite olarak kalmalı.
  - Kanıt: `docs/sartname_v4.pdf`, `docs/sartname_v4.txt`, `docs/requirements_source.md`; eski kanonik yola aktif bağlantı kalmadı.

- [x] **DOC-002 — Takvim ve video yükümlülüklerini senkronize et**
  - `TARIHLER.md`, rapor notları ve görev traceability matrisi aynı tarihleri kullanmalı.
  - Video yetenekleri şartnamedeki sırayla test kimliklerine bağlanmalı.
  - Kanıt: `TARIHLER.md`, `docs/delivery_video_plan.md`; v1.4’e göre KTR sonucu 25.06.2026, video teslimi 17.08.2026 17:00.

- [x] **ADR-001 — Hedef çalışma ortamı ADR’ını yaz**
  - Raspberry Pi OS, Python/React/Pico C++, `systemd`, no-ROS2 ve no-full-Rust kararları kaydedilmeli.
  - ROS 2’yi yeniden değerlendirme koşulları belirtilmeli.
  - Kanıt: `docs/adr/001-target-runtime.md`.

- [x] **ADR-002 — MCU ve saha haberleşmesini kesinleştir**
  - Pico/Arduino çelişkisi kapatılmalı.
  - CAN veya CAN-FD tek karar olarak seçilmeli.
  - Bitrate, frame biçimi, transceiver ve hata davranışı tanımlanmalı.
  - Kanıt: `docs/adr/002-mcu-can.md`; Pico/RP2040 + klasik CAN 2.0B, 500 kbit/s, SN65HVD230, mevcut ICD v0 ve fail-safe davranış kaydedildi.

- [x] **ADR-003 — Kamera/LiDAR yerleşim kararını kaydet**
  - Temel ve nihai CAD görseli karar kanıtı olarak bağlanmalı.
  - Tek `camera_main`, yaw ekseni, silah pitch ekseni, 700 mm LiDAR optik merkezi ve TFA50-L referans koordinatları tanımlanmalı.
  - Kamera ve LiDAR'ın yaw'ı izlediği, silah pitch'ini izlemediği; ayrı nişan kamerası olmadığı belirtilmeli.
  - Profil kilitleme yöntemi, kamera-LiDAR-bore extrinsic'i ve kablo güzergâhı imalat sonrası ölçülmeli.
  - TFA50-L gerçek hedef testini geçemezse fallback sırası: optik/algoritmik iyileştirme → ikinci tek nokta sensör değerlendirmesi → 2D tarayıcı değerlendirmesi.
  - Kanıt: `docs/adr/003-camera-lidar-placement.md` ve `docs/taret_mekanik_ve_sensor_yerlesimi.md`; koordinat çerçeveleri, tek kamera, 700 mm LiDAR merkezi ve kalibrasyon alanları kaydedildi.

- [x] **DOC-003 — Şartname traceability matrisini oluştur**
  - Her zorunlu yetenek için requirement ID, modül, test, telemetri olayı ve video kanıtı alanları bulunmalı.
  - Kanıt: `docs/requirements_traceability.md`; teslim, güvenlik, mod/aşama ve VID-Y1–Y7 bağları.

**Faz kanıtı:** Aktif belgelerde OS, MCU, protokol, sensör rolü, kamera sayısı ve
tarih çelişkisi kalmıyor. Yerel Markdown bağlantı denetimi geçti; eski şartname
yoluna referans bulunmadı; PDF hash’i `docs/requirements_source.md` ile eşleşti.

---

# Faz 2 — Tekrarlanabilir geliştirme ve Pi çalışma ortamı

- [x] **ENV-001 — Backend’i gerçek Python paketi hâline getir**
  - `pyproject.toml`, paket metadata’sı, test config’i ve giriş noktaları eklenmeli.
  - Geçici `PYTHONPATH` gereksinimi kaldırılmalı.
  - Kanıt: `pyproject.toml`; editable `.venv` kurulumunda `gokkalkan`,
    `gokkalkan-operator-api`, `gokkalkan-doctor`, static server ve recorder
    giriş noktaları çalıştı; testler kurulu paket üzerinden geçti.

- [x] **ENV-002 — Python bağımlılıklarını eksiksiz ve kilitli tanımla**
  - Backend, test ve perception bağımlılıkları ayrıştırılmalı.
  - OpenCV, NumPy ve hedef Pi’de kullanılan kamera bağımlılıkları belgelenmeli.
  - Büyük model dosyaları repoya eklenmemeli.
  - Kanıt: `requirements/backend.lock`, `dev.lock`,
    `perception-dev.lock` ve `deploy/pi/manifest.toml`; Pi’de
    NumPy/OpenCV/Picamera2 aynı apt yığınından gelir. Frontend `package-lock`
    yenilendi ve `npm audit` sıfır açık raporladı.

- [x] **ENV-003 — Raspberry Pi kurulum manifestini oluştur**
  - OS sürümü, sistem paketleri, kullanıcı/grup izinleri, CAN ve kamera ayarları yazılmalı.
  - Temiz imaj kurulumunun tekrarlanabilir kontrolü bulunmalı.
  - Kanıt: `deploy/pi/manifest.toml`, `deploy/pi/README.md`,
    `scripts/bootstrap_pi.sh`, `scripts/verify_pi_manifest.py`;
    manifest-only doğrulaması geçti. Fiziksel Pi host kontrolü donanım geldiğinde
    aynı scriptin `--host` modu ile yapılacak.

- [x] **ENV-004 — Runtime config şeması oluştur**
  - `SIM`, `HIL`, `LIVE` profilleri açıkça ayrılmalı.
  - Soft limit, timeout, port, kayıt kotası ve sensör eşikleri doğrulanmalı.
  - Eksik güvenlik config’i live başlangıcını engellemeli.
  - Kanıt: `gokkalkan_backend.runtime_config`,
    `config/runtime/{sim,hil,live,pi-sim}.toml`,
    `tests/test_runtime_config.py`; repo `LIVE` profili explicit enable kapalı
    olduğu için CLI adapter oluşturmadan çıkış kodu 2 ile reddedildi.

- [x] **ENV-005 — `systemd` servislerini ekle**
  - Backend/Mission Core, perception, UI/static server ve telemetry recorder servisleri hazırlanmalı.
  - Restart politikası, dependency sırası, graceful shutdown ve log yönlendirmesi tanımlanmalı.
  - Kanıt: `deploy/systemd/`; backend, perception, bağımlılıksız static/proxy
    UI ve opsiyonel Unix-socket recorder birimleri ile `gokkalkan.target`.
    Birimler restart, sıra, sinyal, timeout ve journald politikasını içerir.
    Faz 7’de backend kanonik tek-yazarlı session deposunun sahibi yapıldı;
    bağımsız process recorder’ı ikinci kanonik log oluşturmaması için target
    dışında opsiyonel kaldı. Kalıcı sequence yalnız ilgili writer’da atanır.

- [x] **ENV-006 — Tek komutlu geliştirme ve dry-run başlatma ekle**
  - Mevcut frontend scriptleri korunmalı.
  - Backend + simulator + UI health kontrolü tek akışta doğrulanmalı.
  - Kanıt: `npm run setup`, `npm run desktop`, `npm run dev:check`;
    launcher backend health’inde `runtimeMode=SIM` ve
    `physicalOutputEnabled=false` doğrulamadan hazır saymıyor. Smoke geçti.

- [x] **ENV-007 — `gokkalkan doctor` tanılama komutunu ekle**
  - Kamera, disk, saat, config, API, Pico/CAN ve kayıt dizini durumunu raporlamalı.
  - Tanılama fiziksel çıkış üretememeli.
  - Kanıt: `gokkalkan_backend.doctor`, `tests/test_doctor.py`;
    JSON raporu config, saat, disk, recording, kamera, CAN, API ve Pico
    kontrollerini verdi ve `physicalOutputAttempted=false` kaldı.

**Faz kanıtı:** `.github/workflows/verify.yml` temiz Python 3.11/Node 22 Linux
kurulumu, test/build ve dry-run stack smoke akışını tanımlar. Yerel temiz `.venv`
kurulumu, 95 Python testi, doctor ve `npm run dev:check` geçti. Fiziksel Pi
üzerindeki `--host` doğrulaması imalat/donanım olmadan tamamlanmış sayılmıyor.
Pi deploy hedefi AI HAT+ resmi gereksinimi nedeniyle Raspberry Pi OS Trixie /
Python 3.13 olarak kilitlendi; CI'nin Python 3.11 alt sınırı korunur.

---

# Faz 3 — Tek sahipli görev çekirdeği ve mesaj sözleşmeleri

- [x] **CORE-001 — Mission Core state modelini ayır** `[WP-01][WP-02][WP-03]`
  - Mod, aşama, tur, hedef, arm, bakım ve fault state’leri tek modelde tanımlanmalı.
  - State değişikliği yalnız Mission Core tarafından yapılmalı.

- [x] **CORE-002 — `CommandEnvelope` ve `EventEnvelope` şemalarını tanımla**
  - En az `run_id`, `event_id`, `sequence`, UTC/monotonic zaman, source, schema version, command/causation ID ve target/track ID alanları bulunmalı.
  - Şema sürümü ve geriye uyumluluk politikası yazılmalı.

- [x] **CORE-003 — HTTP komutlarını kuyruğa taşı**
  - HTTP handler’ları paylaşılan state’i veya donanım adapter’ını doğrudan çağırmamalı.
  - Kabul/red cevabı command ID ile izlenebilmeli.

- [x] **CORE-004 — CAN/sensör thread’lerini event köprüsüne taşı**
  - Thread’ler state değiştirmemeli.
  - `loop.call_soon_threadsafe` veya eşdeğer güvenli köprü kullanılmalı.

- [x] **CORE-005 — CPU-ağır perception’ı ayrı process yap**
  - Process sınırı, health heartbeat’i, queue backpressure ve kapanış davranışı tanımlanmalı.
  - Perception çökmesi Mission Core’u çökertmemeli; angajman kapanmalı.

- [x] **CORE-006 — Immutable state snapshot yayını ekle**
  - UI ve kayıt katmanı tutarlı snapshot okumalı.
  - Polling yerine SSE veya WebSocket state stream tercih edilmeli.

- [x] **CORE-007 — Concurrency ve ordering testlerini ekle**
  - Aynı anda komut, CAN ve sensör olaylarıyla sequence bütünlüğü test edilmeli.
  - Duplicate/out-of-order olaylar deterministik işlenmeli veya reddedilmeli.

**Faz kanıtı:** `tests/test_mission_core.py`, 80 eşzamanlı komutta ve eşzamanlı
HTTP/CAN/sensör kaynak karışımında tek, kesintisiz event sırasını; owner-thread
ihlalini, idempotency’yi, duplicate/out-of-order sensör olaylarını, CAN-benzeri
external thread köprüsünü, perception heartbeat timeout’unu, kuyruk boşaltmalı
kapanışı ve SSE yayını doğrular. `tests/test_perception_bridge.py`, ayrı servis
process’i içindeki bounded latest-wins queue, heartbeat ve temiz thread
kapanışını doğrular. Sözleşme ve karar kayıtları
`docs/message_contracts.md` ile ADR-004’tedir.

---

# Faz 4 — Safety Gate ve canlı arm zinciri

- [x] **SAFE-010 — Safety kararını saf ve merkezi bir fonksiyon yap** `[WP-04]`
  - Hareket ve imha kararları aynı sunucu-otoriter kapıdan geçmeli.
  - Karar `allowed`, reason code ve kullanılan input snapshot’ını üretmeli.

- [x] **SAFE-011 — Fail-closed hata politikasını uygula** `[WP-04]`
  - Exception, eksik config, stale sensör, geçersiz paket ve health kaybı izin üretmemeli.
  - Soft-limit kontrolü hata aldığında hareketi serbest bırakmamalı.

- [x] **SAFE-012 — Bütün sağlık girdilerini Safety Gate’e bağla** `[WP-04]`
  - E-Stop, Pico heartbeat, CAN, encoder, kamera, track, LiDAR, disk/kayıt ve runtime mode.

- [x] **SAFE-013 — Hareket ve imha yasak bölgelerini backend’de uygula** `[WP-04]`
  - Bölgeler sürümlü config olmalı.
  - Sınır, dış bölge ve geçersiz geometri testleri bulunmalı.

- [x] **SAFE-014 — Live arm state machine’i oluştur** `[WP-04]`
  - Fiziksel interlock, backend readiness, operatör hold-to-arm ve kısa timeout birlikte gerekli olmalı.
  - Arm bağlantı/heartbeat kaybında otomatik düşmeli.

- [x] **SAFE-015 — E-Stop reset zincirini güvenli yap** `[WP-04]`
  - HTTP çağrısı tek başına fiziksel E-Stop’u temizleyememeli.
  - Fiziksel bırakma, Pico safe durumu ve kontrollü reset birlikte gerekli olmalı.

- [x] **SAFE-016 — API erişim sınırlarını daralt** `[WP-04]`
  - Saha profili localhost/izinli arayüzle sınırlanmalı.
  - State değiştiren komutlar session/token ve audit identity taşımalı.
  - CORS wildcard live profilde bulunmamalı.

- [x] **SAFE-017 — Safety invariant test paketini oluştur** `[WP-04]`
  - E-Stop, stale input, heartbeat loss, invalid zone, client bypass ve restart senaryoları fiziksel çağrı üretmemeli.

**Faz 4 yazılım kanıtı (25.07.2026):** `safety_gate.py` saf karar + input snapshot üretir; LIVE sağlık matrisi, sürümlü bölge geometrisi, hold-to-arm/timeout, kontrollü E-Stop reset ve token/operatör kimliği testleri `tests/test_phase4_safety.py` içinde doğrulanır. Fault injection fiziksel adapter çağrısı üretmez. Bu kanıt fiziksel E-Stop/interlock kabulü değildir.

---

# Faz 5 — Pico firmware ve CAN protokolü

- [x] **FW-001 — Pico SDK firmware yapısını ekle** `[WP-04]`
  - Build, flash ve host-side test yönergeleri bulunmalı.
  - Firmware sürümü backend health çıktısında görünmeli.

- [x] **FW-002 — Pico güvenlik durum makinesini uygula** `[WP-04]`
  - `BOOT → SAFE → READY → ARMED → FIRING/FAULT`.
  - Reset ve boot çıkışları enerjisiz/güvenli başlamalı.

- [x] **FW-003 — Donanımsal E-Stop ve watchdog davranışını uygula** `[WP-04]`
  - Linux’tan bağımsız çıkış kesme.
  - Heartbeat kaybı ve Pico fault durumunda motor/imha hattını kapatma.

- [x] **FW-004 — Sürümlü CAN ICD oluştur**
  - Command/status/fault frame’leri, ölçekler, endian, bitrate ve timeout tanımlanmalı.
  - Sequence, CRC/checksum, ACK/NACK ve command ID bulunmalı.

- [x] **FW-005 — Backend CAN codec’ini ICD ile uyumlu yap**
  - Status checksum doğrulanmalı.
  - Duplicate, out-of-order, corrupt ve timeout paketleri reddedilmeli.

- [x] **FW-006 — Firmware/simulator contract testlerini ortaklaştır**
  - Aynı input vektörleri aynı state transition ve reason code’ları üretmeli.
  - Simülatör E-Stop ve fault sırasında komutları gerçek firmware gibi reddetmeli.

- [x] **FW-007 — Encoder ve limit geri bildirimlerini bağla**
  - Yön, sıfır, overflow, kopukluk ve beklenen/gerçek açı farkı fault’a dönüşmeli.

- [x] **FW-008 — Pi–Pico taşımasını CAN'dan USB seriye geçir** `[WP-04]`
  - **Yazılım kanıtı (11.08.2026):** `UsbSerialMcuAdapter`, COBS+CRC16 framing, kısmi/çoklu paket decoder'ı, 100 ms heartbeat, ACK/sequence korunumu ve `/dev/serial/by-id/...` LIVE kapısı uygulandı.
  - Pico firmware USB stdio/CDC endpoint'i, stream decoder, status/ACK üretimi ve 250 ms fail-closed heartbeat watchdog'u içerir.
  - SIM/HIL/LIVE profilleri `[mcu]` USB ayarlarına geçirildi; ADR-005 aktiftir, ADR-002 tarihsel olarak işaretlendi.
  - **Açık fiziksel kapı:** Pico flash, motor/kontaktör EMI testi, kablo çekme, disconnect/reconnect ve safe-load HIL kanıtı tamamlanmadan LIVE açılmaz.

**Faz 5 yazılım/host kanıtı (11.08.2026):** CAN v1 payload semantiği USB CDC üzerinde COBS+CRC16 çerçevesiyle korunmuştur. Python transport/adapter testleri ile CMake/CTest firmware host testi geçer. Bu kanıt fiziksel Pico flash, USB EMI, E-Stop, motor veya imha hattı kabulü değildir; bunlar imalat sonrası HIL kapısı olarak açıktır.

---

# Faz 6 — Donanım simülasyonu ve dijital ikiz

- [x] **SIM-001 — MCU simülatörünü gerçek protokol davranışına yükselt**
  - State machine, ACK/NACK, gecikme, timeout ve fault injection desteklemeli.

- [x] **SIM-002 — Pan/tilt dinamik mock’u ekle**
  - Hız, ivme, soft limit, basit backlash ve encoder feedback modellenmeli.
  - Parametreler resmî donanım ölçümü gibi sunulmamalı.

- [x] **SIM-003 — Sensör fixture ve replay adapter’ları ekle**
  - Kamera track, TFA50-L tek nokta menzil/no-detection, bozuk UART frame, stale/dropout ve zaman kayması senaryoları üretilebilmeli.

- [x] **SIM-004 — Güvenli imha çıkışı mock’u ekle**
  - Gerçek çıkış yerine event/lamba/yapay yük davranışı.
  - Fire command yalnız Safety Gate kararından sonra kabul edilmeli.

- [x] **SIM-005 — Senaryo çalıştırıcısı oluştur**
  - Aşama 1/2/3, E-Stop, bağlantı kaybı ve yanlış hedef senaryoları komut satırından tekrarlanabilmeli.

**Faz 6 yazılım/mock kanıtı (25.07.2026):**
`gokkalkan_backend.digital_twin`, CAN v1 uyumlu
`backend/hardware_mock/mcu_simulator.py` ve `gokkalkan scenario` CLI’sı;
Aşama 1/2/3, dost/düşman, E-Stop, bağlantı kaybı ve yanlış hedef yollarını
deterministik yürütür. `tests/test_digital_twin.py` hız/ivme/backlash/limit,
ACK gecikmesi-drop-bozulma, sensör fault fixture’ları ve fiziksel çıkışsız
SafeFireMock sınırını doğrular. Parametreler ölçülmüş donanım değeri değildir;
gerçek motor/enkoder/sensör kabulü imalat sonrası kalır.

---

# Faz 7 — Telemetri, kayıt, kanıt ve replay

- [x] **TEL-001 — Tek-yazarlı telemetry pipeline kur** `[WP-05]`
  - Producer’lar kuyruğa yazar; yalnız recorder kalıcı depoya yazar.
  - Event ID ve sequence process/thread güvenli olmalı.

- [x] **TEL-002 — SQLite WAL event index’i ekle** `[WP-05]`
  - JSONL taşınabilir export olarak korunabilir.
  - `/state` veya health istekleri bütün logu baştan okumamalı.

- [x] **TEL-003 — Session manifest oluştur** `[WP-05]`
  - Git SHA, build ID, OS/paket sürümleri, config/calibration/BOM hash’leri, operatör ve dosya hash’leri kaydedilmeli.

- [x] **TEL-004 — Kamera ve ham sensör kayıtlarını session’a bağla** `[WP-05]`
  - Segmentli video/frame index’i, LiDAR paketleri ve CAN frame’leri ortak zaman tabanında ilişkilendirilmeli.

- [x] **TEL-005 — Disk yönetimi ve bozulma davranışı ekle** `[WP-05]`
  - Rotation, kota, retention, düşük disk alarmı ve graceful degradation.
  - Eksik/bozuk session açıkça `invalid evidence` olmalı.

- [x] **TEL-006 — Güvenli replay motorunu oluştur** `[WP-05]`
  - Replay fiziksel adapter yükleyememeli.
  - Aynı session aynı karar ve event sırasını üretmeli.

- [x] **TEL-007 — Kanıt paketi üreticisi ekle** `[WP-05]`
  - Şartname yeteneği, video zaman aralığı, ilgili event’ler ve hash manifest birlikte export edilmeli.

- [x] **TEL-008 — Doğrulama CLI’larını ekle** `[WP-05]`
  - `gokkalkan replay verify <session>`
  - `gokkalkan evidence verify <session>`

**Faz 7 yazılım/mock kanıtı (25.07.2026):**
`SessionTelemetryStore` queue/soket producer’larını tek writer’da sıralar;
SQLite WAL index, segmentli JSONL, manifest ve monotonic medya index’i üretir.
`gokkalkan replay verify|run` ile `gokkalkan evidence build|verify` fiziksel
adapter yüklemeden çalışır. `tests/test_telemetry_session.py` kamera karesi,
LiDAR paketi, Safety kararı, MCU ACK’i, komut sonucu ve video aralığını aynı
`commandId`/zaman tabanında paketleyip hash doğrulamasından geçirir. Düşük disk,
retention, eksik medya ve tamper session’ı `invalid evidence` yapar. Bu kanıt,
şartnamenin §2.4.4 fiziksel video/yetenek gösteriminin yerine geçmez.

---

# Faz 8 — Görev state machine ve operatör paneli

- [x] **MIS-001 — Aşama 1 state machine’ini tamamla** `[WP-01]`
  - Hedef sırası, 300 saniye, manuel yönelim, deadman ve kullanıcı komutlu FireIntent.

- [x] **MIS-002 — Aşama 2 state machine’ini tamamla** `[WP-02]`
  - Gerçek track’lerle otonom tespit/takip, hedef önceliği ve tur ilerlemesi.
  - Hedef tipi sınıflandırması zorunlu varsayılmamalı.

- [x] **MIS-003 — Aşama 3 state machine’ini tamamla** `[WP-03]`
  - Dost/düşman, hedef tipi, ölçülmüş menzil ve hedef tipine bağlı menzil kapısı.

- [x] **MIS-004 — Bakım/stop/resume/E-Stop akışlarını tekleştir** `[WP-04]`
  - UI local state’i gerçek backend state’inden ayrışmamalı.
  - Bakım bütçesi ve geçiş nedenleri loglanmalı.

- [x] **UI-001 — Manuel aim ve deadman kontrolünü bağla** `[WP-01]`
  - UI yalnız niyet gönderir; backend limit/Safety kararını verir.

- [x] **UI-002 — Sentetik hedefleri gerçek track’lerle değiştir** `[WP-02][WP-03]`
  - UI hedef kimliği üretmemeli.
  - Hedef seçimi backend/perception kaynaklı track ID kullanmalı.

- [x] **UI-003 — Health, arm ve blok nedenlerini görünür yap** `[WP-04]`
  - `SIM/HIL/LIVE`, physical output, E-Stop, Pico/CAN, kamera, LiDAR, kayıt ve Safety reason aynı yüzeyde anlaşılmalı.
  - Kritik anlam yalnız renkle verilmemeli.

- [x] **UI-004 — Backend state stream’e geç**
  - UI optimistik güvenlik state’i üretmemeli.
  - Reconnect ve backend restart sonrası state yeniden senkronize olmalı.

- [x] **UI-005 — Büyük panel sorumluluklarını böl**
  - Mevcut tasarım dilini koruyarak görev, güvenlik, donanım, sensör ve event yüzeyleri ayrıştırılmalı.
  - Yeni dependency eklemeden önce mevcut bileşen ve yardımcılar kullanılmalı.

**Faz kanıtı:** Aşama 1/2/3, bakım ve E-Stop akışları gerçek backend cevaplarıyla E2E testlerinden geçiyor.

**Uygulama/kanıt notu (2026-07-25):**
- `MissionFlow`, tek sahipli `MissionCore` içinde hedef sırası, görev ilerlemesi,
  duraklatma, bakım ve mandallı E-Stop geçişlerinin tek otoritesidir.
- Aşama 1'in 300 saniyelik sınırı dolduğunda görev fail-closed duraklatılır;
  manuel yönelim deadman olmadan ve atış kullanıcı niyeti olmadan kabul edilmez.
- Aşama 2, perception kaynaklı track ID'lerini menzil önceliğiyle kullanır ve
  tip sınıflandırmasını zorunlu tutmaz. Aşama 3 dost/düşman, hedef tipi ve
  ölçülmüş menzil kaynağını birlikte kapılar.
- Operatör paneli hedef, Safety, bakım, görev ve health durumunu SSE/REST
  backend snapshot'ından alır; sentetik hedef/kimlik ve optimistik güvenlik
  state'i üretmez. Reconnect/restart tam snapshot ile yeniden eşitlenir.
- Yazılım kanıtları: `tests/test_phase8_mission_flow.py` ve
  `frontend/tests/e2e/phase8-backend.spec.ts`. Bunlar gerçek `MissionCore` ve
  HTTP cevaplarını kullanır fakat **SIM/dry-run kanıtıdır**; fiziksel E-Stop,
  TFA50-L, kamera, Pico/CAN ve imha hattı kabulünün yerine geçmez.

---

# Faz 9 — Perception ve LiDAR/kamera füzyonu

- [x] **PER-001 — Gerçek kamera adapter’ını ekle** `[WP-02]`
  - Picamera2 frame’i kamera timestamp’i ve receive monotonic zamanı ile üretilmeli.
  - Kamera yokluğu/crash/stale health’e yansımalı.

- [x] **PER-002 — Tek yaw-köprüsü kamera track hattını oluştur** `[WP-02]`
  - Hedef adayı, track ID, merkez, bbox, confidence, velocity ve freshness.

- [x] **PER-003 — Tek kamera ile weapon-bore merkezleme sınırını oluştur** `[WP-02]`
  - Seçili track ile taret koordinatı arasındaki hata, kamera-bore extrinsic ve
    balistik holdover ile kalibre edilmeli; ikinci kamera varsayılmamalı.

- [x] **PER-004 — Track lifecycle kurallarını tamamla** `[WP-02]`
  - TTL, boş frame update’i, kayıp/yeniden edinim ve duplicate association.
  - Tek update sonrası bağlantı durumu sonsuza kadar true kalmamalı.

- [ ] **PER-005 — Gerçek hedef veri seti ve değerlendirme aracını oluştur** `[WP-02][WP-03]`
  - Renk/şekil/tip sınıflandırması gerçek görsellerle ölçülmeli.
  - Confusion matrix, precision/recall, FPS ve gecikme raporlanmalı.
  - Gereksiz YOLO/DeepSORT eklenmemeli; ihtiyaç ölçümle gösterilmeli.

- [ ] **PER-006 — AI HAT+ 26 TOPS detector/classifier modelini kabul et** `[WP-02][WP-03]`
  - [x] Hailo-8 donanım kimliği ve HEF artefaktı health sınırı eklendi.
  - [x] Pi manifesti `hailo-all`, Hailo-8 ve tek Camera Module 3 Standard'a kilitlendi.
  - [ ] CAD sentetik + gerçek hedef veri setiyle eğitilen model seçilmeli ve HEF'e derlenmeli.
  - [ ] Precision/recall, 5/10/15 m, yaw tarama açıları, FPS ve p95 gecikme kabulü yapılmalı.

- [ ] **LID-001 — TFA50-L UART protokolünü ve adapter’ını tamamla** `[WP-03]`
  - Protokol kaynağı: [TFA50-L Datasheet](https://www.e-kom.com/Datasheet/Benewake/TFA50-L_Datasheet.pdf); runtime vendor uygulamasına bağımlı olmamalı.
  - [x] Dört baytlık `0x5C` menzil frame’i, little-endian santimetre, checksum ve `0xFFFF` no-detection ayrıştırıcısı eklendi.
  - [x] Parçalı/noisy UART akışı için yeniden senkronize olan bağımlılıksız stream decoder ve unit testleri eklendi.
  - [x] UART portu, baud rate ve örnekleme frekansı config’ten gelmeli; bağlantı kesilmesi/stale/yeniden bağlanma health’e yansımalı.
  - [x] Alınan ham frame, receive monotonic timestamp, geçerli/geçersiz nedeni ve kabul edilen metre değeri telemetriye yazılmalı.
  - [ ] Gerçek sensör seri numarası/firmware bilgisi okunup etkin config ile session manifestine kaydedilmeli.

- [ ] **LID-002 — Mekanik hizalama ve kalibrasyon iş akışını ekle** `[WP-03]`
  - [x] Kalibrasyon şeması, mount revision/hash kontrolü ve 5/10/15 m
    gözlem raporu yazılımı eklendi.
  - [ ] Gerçek köprü/kızak kilitlendikten sonra fiziksel gözlem dosyası üretilmeli.
  - Config: `mount_height_m`, `yaw_offset_deg`, `pitch_offset_deg`, kabul edilen hedef düşey bandı, kalibrasyon ID/hash/tarih/operatör.
  - Köprü/kızak elle değiştirildikten sonra eski kalibrasyon otomatik olarak “doğrulanmamış” sayılmalı; live arm kapanmalı.
  - Görünür hizalama noktası yalnız güvenli kurulum prosedüründe kullanılmalı; çalışma zamanı algoritmasının zorunlu girdisi olmamalı.
  - 5/10/15 m sabit hedef ölçümleriyle ofset, tekrar edilebilirlik ve no-detection oranı kaydedilmeli.

- [x] **LID-003 — Yaw-to-track menzil eşlemesini uygula** `[WP-03]`
  - LiDAR yaw açısı, taret encoder yaw’ı ve kalibre edilmiş `yaw_offset_deg` ile hesaplanmalı; silah pitch’i bu ölçüm doğrultusuna eklenmemeli.
  - Yalnız seçili kamera track’inin bearing’i LiDAR doğrultu toleransı içindeyken ölçüm o track’e atanmalı.
  - Timestamp yakınlığı, art arda örnek sayısı, menzil değişim hızı ve aykırı değer filtresi kullanılmalı.
  - TFA50-L menzil frame’i kalite/sinyal gücü taşımadığı için sahte bir “quality” alanı üretilmemeli; kabul/ret nedeni açıkça kaydedilmeli.

- [x] **LID-004 — Menzil güvenlik kapısını gerçek sensöre bağla** `[WP-03][WP-04]`
  - Bbox alanından üretilen kaba menzil Safety Gate’te kullanılmamalı.
  - UART health, kalibrasyon geçerliliği, yaw hizası, track freshness ve kararlı menzil birlikte sağlanmadan imha izni açılmamalı.
  - Stale/checksum hatalı/no-detection/ambiguous LiDAR ölçümü fail-safe biçimde imha iznini kapatmalı.

- [ ] **LID-005 — TFA50-L mekanik ve optik kabul testini yap** `[WP-03]`
  - Köprü/profil ve merkezî kızak/direk seçenekleri titreşim, merkezleme, kablo hareketi ve kilit kaçırma açısından karşılaştırılmalı.
  - Silah pitch hareket ederken LiDAR’ın hedef yüksekliğinde kaldığı; yaw hareketinde ise seçili hedefi takip ettiği doğrulanmalı.
  - Gerçek yarışma hedef malzemesi/renkleriyle 5/10/15 m ve sağ/merkez/sol yaw noktalarında algılama oranı ölçülmeli.
  - Kabul kriteri karşılanmazsa ADR-003 fallback sırası işletilmeli; 2D LiDAR’a ölçümsüz geçilmemeli.

- [x] **PER-006 — Kayıtlı veri replay eşitliğini doğrula**
  - Aynı kayıt canlı ve replay pipeline’da deterministik track/range kararları üretmeli.

**Faz kanıtı (yazılım):** Stale, checksum hatalı, no-detection, kalibrasyonu
geçersiz, yaw ile eşleşmeyen veya art arda kararlı olmayan menzil kararı
`MissionCore` tarafından kabul edilmiyor. `camera-bbox-estimate` yalnız
görselleştirme/öncelik verisidir; LIVE menzil kapısını açamaz.

**Uygulama/kanıt notu (2026-07-25):**
- Kamera frame zarfı kamera timestamp’i, receive monotonic zamanı, sequence ve
  timestamp kaynağı taşır; mock kamera LIVE-health üretmez.
- Tracker ID üretimi ve hareket hesabı deterministiktir; boş kare de lifecycle
  update’idir. Nişan kamerası için hash’li pixel→yaw/pitch kalibrasyon hesabı
  ve stale ret yolu vardır.
- TFA50-L UART adapter’ı config kaynaklı **460800 baud / 1000 Hz** varsayılanı,
  reconnect/stale health, ham frame ve açık ret nedeni telemetrisi taşır.
- Kamera-relative bearing önce taret encoder yaw’ı + kamera yaw ofsetiyle dünya/
  encoder koordinatına çevrilir; TFA50-L doğrultusu da encoder yaw + LiDAR yaw
  ofsetidir. Silah pitch’i LiDAR doğrultusuna eklenmez. Köprü/kızak
  `mount_revision` değişirse eski kalibrasyon geçersiz olur.
- `config/calibration/tfa50_l.toml` kasıtlı olarak `UNVERIFIED` durumundadır.
  Bu nedenle fiziksel sensör bağlanmadan LIVE arm açılamaz.
- `PER-005`, `LID-001`, `LID-002` ve `LID-005` üzerindeki açık durum kod
  eksikliği değil; gerçek hedef görüntüsü, sensör kimliği ve 5/10/15 m mekanik/
  optik ölçüm kanıtı eksikliğidir.

---

# Faz 10 — CI, kalite kapıları ve saldırgan testler

- [x] **QA-001 — Linux CI workflow ekle**
  - Python unit/integration, frontend unit, typecheck, build ve seçili E2E testleri.

- [x] **QA-002 — Mevcut Playwright sapmasını düzelt**
  - Landing beklentisi güncel ürün kararıyla senkronize edilmeli.

- [x] **QA-003 — Hardware adapter ve HTTP coverage’ını artır**
  - Özellikle error/timeout/invalid-input yolları kapsanmalı.

- [x] **QA-004 — Safety test marker/gate ekle**
  - `pytest -m safety`; başarısızsa merge/release engellenmeli.

- [x] **QA-005 — Protocol contract test gate’i ekle**
  - `pytest -m protocol`; firmware/simulator/backend vektörleri aynı olmalı.

- [x] **QA-006 — Replay determinism test gate’i ekle**
  - `pytest -m replay`; fiziksel adapter import/yükleme denetimi içermeli.

- [x] **QA-007 — Fault-injection senaryo paketi ekle**
  - Corrupt checksum, duplicate sequence, heartbeat loss, CAN disconnect, E-Stop, stale sensör, disk full, process restart ve UI/backend ayrışması.

- [ ] **QA-008 — Uzun süreli dry-run/soak testi ekle**
  - [x] Sanal-zaman ve duvar-saati modları, queue/disk/reconnect raporu eklendi.
  - [ ] Pi üzerinde kesintisiz 30 dakika `--real-time` kanıtı alınmalı.
  - En az 30 dakika olay, video segmenti, disk kullanımı ve reconnect davranışı izlenmeli.

- [ ] **QA-009 — Performans bütçelerini tanımla ve ölç**
  - [x] Sürümlü bütçe dosyası ve pass/fail değerlendirme aracı eklendi.
  - [ ] Gerçek kamera/Pi/CAN üzerinde ölçüm raporu alınmalı.
  - Kamera FPS, frame drop, algı gecikmesi, command-to-ACK, state stream ve recorder queue derinliği.
  - Ölçülmeden Rust/native/ROS 2 optimizasyonu yapılmamalı.

**Faz kanıtı:** P0/P1 güvenlik ve görev invariant’ları başarısızken merge veya live release üretilemiyor.

**Uygulama/kanıt notu (2026-07-25):**
- Ubuntu CI; safety/protocol/replay marker kapıları, tam pytest+coverage,
  frontend type/unit/desktop/build, tüm Playwright E2E, fault-injection ve
  1800 saniyelik sanal-zaman soak koşularını içerir.
- Fault paketi checksum, duplicate sequence, heartbeat, CAN, E-Stop, stale
  kamera/LiDAR, disk, restart ve backend ayrışmasını fail-closed doğrular.
- 30 dakikalık soak harness’ı sanal veya `--real-time` duvar saati modunda
  çalışabilir. Bu turdaki hızlı kanıt sanal zamandır; Pi üzerinde duvar saati
  raporu ayrıca üretilmelidir.
- Performans eşikleri `config/quality/performance.toml` içindedir. Bunlar
  donanım ölçümü değil kabul bütçesidir; ölçülmeden Rust/native/ROS 2 kararı
  verilmez.

---

# Faz 11 — İmalat öncesi HIL yazılımı ve release adayı

- [x] **HIL-001 — HIL profilini oluştur**
  - Pi + Pico + gerçek CAN + güvenli test motoru/encoder + E-Stop/röle + kamera/LiDAR + lamba/yapay yük.
  - HIL hiçbir koşulda gerçek imha elemanını kullanmamalı.

- [x] **HIL-002 — HIL senaryo otomasyonunu ekle**
  - Boot/safe, Pico reset, heartbeat loss, CAN çıkarma, encoder ters/kopuk, kamera/LiDAR stale ve E-Stop.

- [x] **HIL-003 — HIL sonuç raporunu otomatik üret**
  - Test kimliği, run ID, config/calibration hash, event özeti ve pass/fail.

- [x] **HIL-004 — Süreç restart/session recovery doğrula**
  - Backend, perception ve recorder ayrı ayrı yeniden başlatıldığında güvenli state ve kayıt bütünlüğü korunmalı.

- [x] **HIL-005 — Operatör panelinden bütün blok nedenlerini doğrula**
  - Her Safety reason görünür, anlaşılır ve telemetriyle aynı olmalı.

- [x] **REL-001 — İmalat öncesi yazılım release adayı oluştur**
  - Sürümlü config, firmware, backend, UI, simulator, test fixture ve kurulum manifesti aynı release’e bağlanmalı.

- [x] **REL-002 — Software Gate’i kapat**
  - Safety, görev, replay, UI, fault-injection ve clean-install testleri yeşil.

- [ ] **REL-003 — Sensor Gate’i kapat**
  - Kamera + TFA50-L çözümünün kayıtlı 5/10/15 m, sağ/merkez/sol yaw verileri ve adapter/replay yolu yeşil.

- [ ] **REL-004 — HIL Gate’i kapat**
  - Pico, CAN, encoder, E-Stop, röle ve yapay yük senaryoları yeşil.

**İmalat öncesi stop koşulu:** Software Gate, Sensor Gate ve HIL Gate birlikte geçmeden “imalat sonrası yalnız montaj ve kalibrasyon kalacak” denmez.

**Uygulama/kanıt notu (2026-07-25):**
- `config/runtime/hil.toml` vcan preflight; `hil-physical.toml` ise gerçek
  SocketCAN için yalnız lamba/yapay yük profili sağlar. Her ikisinde de gerçek
  imha çıkışı kapalıdır.
- `gokkalkan hil` on iki güvenli HIL senaryosunu ve config/kalibrasyon hash’ini
  raporlar; fiziksel observation verilmezse sonuçları `NOT_RUN_PHYSICAL`
  bırakarak HIL Gate’i kapatmaz.
- `gokkalkan release` backend, perception, UI, simulator, testler, firmware ve
  config dosyalarını SHA-256 ile tek release manifestine bağlar.
- `REL-002 Software Gate` repo içi test kanıtıyla kapatılmıştır. `HIL-001` ve
  `HIL-004` için profil/recovery yazılımı hazırdır; bunların fiziksel uygulama
  kanıtı ile `REL-003` ve `REL-004` donanım olmadan bilinçli olarak açık
  bırakılmıştır.

---

# Yazılım dışında kalan fakat yazılımı bloke eden kararlar

Bu maddeler yazılım görevi değildir; ilgili ekip tarafından sonuçlandırılmadan bazı adapter ve kalibrasyon işleri kapatılamaz:

- [ ] TFA50-L’nin 5/10/15 m gerçek hedef testi ve nihai satın alma kabulü.
- [ ] Köprü/profil veya merkezî kızak/direk seçimi; manuel yükseklik aralığı, ölçü skalası, merkezleme toleransı ve mekanik kilit.
- [ ] TFA50-L için 9–36 V besleme, UART elektrik seviyesi/izolasyonu, konnektör ve Raspberry Pi bağlantı devresi.
- [x] Klasik CAN 2.0B, SN65HVD230 ve 500 kbit/s kararı (`ADR-002`).
- [ ] Enkoder tam modeli, çözünürlüğü ve elektriksel arayüzü.
- [ ] Motor sürücüsü ve limit switch arayüzleri.
- [ ] E-Stop, emniyet rölesi/kontaktör ve reset devresi.
- [ ] İki kamera lens/FOV ve kablo yerleşimi.
- [ ] Taret yaw, silah pitch, kamera ve TFA50-L referans koordinatları/extrinsic ölçüleri ile hedeflerin düşey merkez bandı.
- [ ] İmha mekanizmasının menzil–pitch kalibrasyon yöntemi ve güvenli yapay yük arayüzü.

---

# Mevcut ve hedef doğrulama komutları

Mevcut repo komutları:

```bash
npm run setup
.venv/bin/python -m pytest -q
npm run typecheck
npm run test:unit
npm run build
npm run test:desktop
npm run test:competition
npm run dev:check
.venv/bin/gokkalkan doctor
```

Plan sonunda bulunması beklenen komutlar:

```bash
.venv/bin/python -m pytest -m safety
.venv/bin/python -m pytest -m protocol
.venv/bin/python -m pytest -m replay
.venv/bin/python -m pytest -m hil
gokkalkan doctor
gokkalkan replay verify <session>
gokkalkan evidence verify <session>
gokkalkan quality faults
gokkalkan quality soak --duration-sec 1800 --step-sec 0.1 --real-time --output <rapor.json>
gokkalkan quality performance <ölçüm.json>
gokkalkan lidar calibrate <gözlemler.json> --output <kalibrasyon-raporu.json>
gokkalkan hil --output <hil-raporu.json>
gokkalkan release --version <sürüm> --software-gate --output <manifest.json>
gokkalkan release verify <manifest.json>
```

## Agent için son kontrol

Her çalışma turunun sonunda:

- [ ] Hangi TODO kimliklerinin kapandığını yaz.
- [ ] Değişen dosyaları listele.
- [ ] Çalıştırılan testleri ve sonuçlarını kaydet.
- [ ] Donanım olmadan doğrulanamayan noktaları açıkça belirt.
- [ ] Yeni risk veya çelişki bulduysan bu TODO’ya ekle.
- [ ] Güvenlik kapısını geçici olarak bypass eden test/debug kodu bırakma.
