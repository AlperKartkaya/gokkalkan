# Gerçek Operatör Paneli ve Arayüz Yol Haritası

> **Durum (2026-08-28):** Yol haritasının ana yazılım yüzeyi uygulanmıştır.
> Aşağıdaki Pico/CAN ifadeleri tarihsel tasarım kaydıdır; aktif saha taşıması
> Arduino Uno seri adaptörüdür. Güncel kullanım için kök `README.md`, ADR-006
> ve `frontend/` esas alınır.

Bu doküman, simülatörden ayrı gerçek operatör panelinin arayüz kararlarını ve KTR’de anlatılacak sınırları toplar. Fiziksel kamera, TFA50-L, motor, E-Stop ve imha hattı saha kabulü ayrı kalır.

## 1. Neden ayrı bir operatör paneli?

`frontend/` yarışma eğitim simülatörü ile canlı backend, perception, sensör ve
donanım adapter’larına bağlanan operatör panelini ayrı çalışma yüzeyleri olarak
içerir. Landing ekranı iki yüzeyi birbirinden açıkça ayırır:

```text
Operatör Paneli
Gerçek sistem bağlantısı / dry-run destekli
```

Backend bağlantısı yoksa panel `Bağlantı bekleniyor` durumunda fail-closed
kalır. Simülatör puan mantığını gerçek ateşleme durumu gibi göstermez.

## 2. Temel güvenlik kararı

UI doğrudan ateşleme hattını enerjilendirmez ve motor sürmez. UI yalnızca yüksek seviyeli niyet gönderir:

```text
FireIntent, ModeRequest, ManualAimCommand, MaintenanceRequest
```

Backend şu kontrollerden sonra düşük seviye komut üretir:

1. mod uyumu,
2. Acil Durdur pasif/güvenli,
3. harekete yasak alan kontrolü,
4. atışa yasak alan kontrolü,
5. hedef dost/düşman ve menzil kapısı,
6. donanım bağlantı sağlığı,
7. operatör/hakem/dry-run/live kilidi.

## 3. Uygulanan sayfa yapısı

### 3.1. Landing entegrasyonu

- `Simülasyona Başla`: mevcut eğitim simülatörü.
- `Operatör Paneli`: gerçek sistem paneli.
- Geliştirme sürecinde panel açılırken üstte kalıcı durum etiketi bulunmalı:
  - `DRY-RUN — fiziksel çıkış yok`,
  - `CANLI BAĞLANTI — Safety Gate aktif`,
  - `BAĞLANTI YOK — komut gönderilemez`.

### 3.2. Gerçek panel ekranı

1. **Üst canlı durum şeridi**
   - mod, aşama, tur/süre,
   - backend bağlantısı,
   - perception bağlantısı,
   - sensor adapter sağlığı,
   - Safety Gate özeti,
   - Acil Durdur durumu.
2. **Canlı görüntü ve sensör füzyonu**
   - kamera görüntüsü,
   - hedef izi,
   - TFA50-L 1D menzil ölçümü,
   - hedef tipi/dost-düşman/menzil.
3. **Komut paneli**
   - Manuel/Otonom/Safe/Bakım mod geçişi,
   - manuel pan/tilt komutları,
   - güvenli arming durumu,
   - FireIntent butonu ve blok gerekçesi.
4. **Güvenlik ve olay akışı**
   - `SafetyState`, `CommandResult`, `TelemetryEvent`, `HardwareFault`.
5. **Entegrasyon / bakım çekmecesi**
   - sensör kalibrasyonu,
   - servo limitleri,
   - dry-run/live ayrımı,
   - ham mesajlar.
6. **Sistem Durumu göstergesi**
   - `/readiness` raporu,
   - hazır/kısmi/TBD/kilitli arayüz kartları,
   - sıradaki kritik TFA50-L, perception, MCU ve arming adımları.
   - Backend readiness raporu yoksa panel yüzde veya hazır bileşen uydurmaz; adapter’ları açıkça `TBD` gösterir.
7. **Kayıt / Replay çekmecesi**
   - SQLite WAL session, segmentli JSONL export yolu ve kayıt sayısı,
   - `/telemetry/export` görünümü ile `gokkalkan evidence` hash’li kanıt paketi,
   - replay-only olay/komut/hardware sonucu özeti,
   - fiziksel çıkış üretmediğini gösteren açık durum.

## 4. KTR için arayüz tabloları

### 4.1. Kullanıcı arayüzleri

| Arayüz | Kullanıcı | Görev | Mesajlar / veri | Güvenlik sınırı |
| --- | --- | --- | --- | --- |
| Yarışma simülatörü | Yarışmacı / geliştirici | Aşama pratiği ve eğitim | Simülasyon hedefleri, puan, onboarding | Fiziksel çıkış yok |
| Gerçek operatör paneli | Operatör | Mod seçimi, hedef izleme, komut niyeti | `ModeRequest`, `FireIntent`, `SafetyState`, `TrackState` | Backend Safety Gate yetkilidir |
| Bakım/debug paneli | Yazılım/elektronik ekip | Kalibrasyon ve teşhis | ham sensör, adapter health, log | Operatör ana akışından ayrıdır |

### 4.2. Yazılımsal mesaj arayüzleri

| Arayüz | Yön | Örnek alanlar | İlk uygulanacak biçim | Gelecek iyileştirme |
| --- | --- | --- | --- | --- |
| `ModeRequest` | UI → Backend | `requestedMode`, `operatorId`, `timestamp`, `reason` | JSON/HTTP | imzalı/oturumlu komut |
| `StageRequest` | UI → Backend | `stage`, `round`, `operatorId`, `timestamp`, `reason` | JSON/HTTP | resmi aşama/tur ve mode expectation validasyonu |
| `ManualAimCommand` | UI → Backend | `panDelta`, `tiltDelta`, `rateLimit`, `deadmanActive` | JSON/WebSocket | joystick input stream |
| `FireIntent` | UI → Backend | `targetId`, `stage`, `round`, `operatorConfirm`, `dryRun` | JSON/HTTP veya WebSocket command | iki aşamalı arming protokolü |
| `SafetyState` | Backend → UI | `estop`, `motionZoneOk`, `fireZoneOk`, `modeOk`, `targetGate`, `blockReason` | WebSocket state stream | kod + Türkçe açıklama sözlüğü |
| `TrackState` | Perception/Sensor → Backend/UI | `trackId`, `x`, `y`, `rangeM`, `bearingDeg`, `type`, `friendFoe`, `confidence` | JSON stream | binary/protobuf yalnız ihtiyaç olursa |
| `SensorFrame` | Sensor Adapter → Backend/UI | `sensor`, `rangeM`, `bearingDeg`, `quality`, `timestamp`, `trackId` | JSON replay/stream | Kamera + TFA50-L fixture’ı canlı veri iddiası taşımaz; 1D LiDAR point-cloud üretmez |
| `HardwareCommand` | Backend → Adapter | `commandId`, `kind`, `panTilt`, `fireEnable`, `timeoutMs` | Python adapter interface | MCU protokolüne çeviri |
| `CommandResult` | Adapter → Backend/UI | `commandId`, `accepted`, `completed`, `faultCode`, `latencyMs` | JSON event | gerçek zaman ölçümü |
| `TelemetryEvent` | Tüm katmanlar → Log | `timestamp`, `stage`, `mode`, `eventType`, `payload` | JSONL | replay/rapor export |

### 4.3. Sensör ve veri aktarımı arayüzleri

| Bileşen | Veri | Arayüz durumu | Not |
| --- | --- | --- | --- |
| Kamera | görüntü karesi, frame timestamp, exposure/health | Picamera2/OpenCV + MJPEG uygulanmış | Fiziksel kamera kabulü ve gecikme ölçümü açık |
| TFA50-L 1D LiDAR | boresight menzili, kalite, receive timestamp | UART decoder + serial adapter uygulanmış | Gerçek 5/10/15 m kalibrasyon kanıtı açık |
| Perception | hedef adayı, takip izi, sınıf/dost-düşman | backend’e stream | Aşama 2’de sınıflandırma zorunlu değil; Aşama 3’te gerekli |
| Backend | görev durumu, SafetyState, CommandResult | UI’ya stream | UI, backend state olmadan live komut açmamalı |

### 4.4. Elektronik güç/sinyal arayüzleri

Kesin elektronik değerler tasarım netleşince doldurulmalıdır. KTR’de yanlış kesinlikten kaçınmak için şu format önerilir:

| Arayüz | KTR’de anlatılacak içerik | Durum |
| --- | --- | --- |
| Ana güç dağıtımı | Mean Well RSP-500-24, sigorta, ana kesme ve regülasyon | Tasarım onaylı; fiziksel kabul açık |
| Logic güç | 24V→5V ve 24V→12V regülasyon hatları | Tasarım onaylı; fiziksel kabul açık |
| Acil Durdur | fiziksel buton, UI’dan bağımsız kesme/disable, backend bildirimi | Zorunlu |
| MCU haberleşmesi | pan/tilt ve imha hattı komutlarının taşındığı protokol | Klasik CAN 2.0B / 500 kbit/s; fiziksel HIL açık |
| Kamera bağlantısı | CSI/Picamera2; USB/OpenCV geliştirme fallback’i | Yazılım uygulanmış; fiziksel gecikme ölçümü açık |
| TFA50-L bağlantısı | UART, receive timestamp ve health | Yazılım uygulanmış; fiziksel kalibrasyon açık |
| İmha hattı | patlayıcı olmayan mekanizma, interlock, Safety Gate sonrası enable | Güvenlik-kritik |

## 5. Uygulama ve doğrulama sırası

1. **Paylaşılan mesaj sözleşmeleri**
   - TypeScript ve Python tarafında aynı `SafetyState`, `TrackState`, `FireIntent`, `CommandResult` alanları belgelenir.
   - İlk sürüm JSON schema veya Markdown tabloyla başlayabilir; kod üretimi şart değil.
2. **Backend API iskeleti**
   - `GET /state`, `POST /mode`, `POST /manual-aim`, `POST /fire-intent`, `WS /events` gibi dry-run endpoint’leri.
   - İlk adapter `hardware_mock` olmalı; fiziksel çıkış yok.
3. **Operatör paneli sayfası**
   - Landing’den erişilir.
   - Backend bağlantı yoksa komut butonları kapalı ve gerekçe görünür.
   - Simülatör bileşenlerinden yalnız görsel/UX pattern’leri alınır; simülasyon puanı alınmaz.
4. **Perception/sensör adapter’ları**
   - Kamera ve TFA50-L 1D LiDAR ayrı adapter’lar olarak bağlanır.
   - Her adapter `health`, `timestamp`, `latency`, `confidence` üretir.
5. **Safety Gate entegrasyonu**
   - Her hareket/ateş isteği backend Safety Gate’ten geçer.
   - E-stop ve yasak alan blokları hem UI hem telemetry’de görünür.
6. **Hardware-in-the-loop dry-run**
   - Önce motor/ateş çıkışı devre dışı, yalnız command_result ve latency ölçümü.
   - Sonra düşük güç/güvenli koşul testi.
7. **KTR ve video kanıtı**
   - Arayüz ekran görüntüleri, mesaj akış tabloları ve Mermaid sequence diyagramları KTR’ye taşınır.

## 5.1. İlk uygulanmış dry-run API sözleşmesi

Bu geçişte backend tarafında bağımlılıksız Python iskeleti başlatılmıştır:

```bash
.venv/bin/gokkalkan operator-api --config config/runtime/sim.toml
# KTR/debug kanıtını belirli dosyaya yazmak için:
.venv/bin/gokkalkan operator-api --config config/runtime/sim.toml \
  --telemetry-jsonl telemetry_data/operator-api-dry-run.jsonl
```

Uygulanan endpoint’ler:

| Endpoint | Yön | Amaç | Güvenlik notu |
| --- | --- | --- | --- |
| `GET /health` | UI → Backend | API sağlığı, dry-run ve fiziksel çıkış durumunu okur | `physicalOutputEnabled=false` döner |
| `GET /state` | UI → Backend | mod, aşama, izler, `SafetyState`, `CommandResult` ve olay akışını alır | varsayılan izler dry-run kaynaktır |
| `GET /sensor-frames` | UI → Backend | kamera + TFA50-L `SensorFrame` replay paketini ve sağlık özetini alır | `replayOnly=true`; gerçek sensör bağlı iddiası taşımaz |
| `GET /readiness` | UI/KTR → Backend | final fazı entegrasyon hazırlığı, arayüz durumu ve kritik sonraki adımları alır | resmi yarışma uygunluk skoru değildir; TBD değerleri açık bırakır |
| `GET /events` | UI → Backend | telemetri/komut olay listesini alır | rapor ve KTR kanıtı için JSON olaylar |
| `GET /telemetry/export` | UI/Debug → Backend | JSONL log, state, command result ve event kayıtlarını tek kanıt paketinde dışa aktarır | replay/export fiziksel çıkış üretmez |
| `GET /replay` | UI/Debug → Backend | JSONL kayıtlarından replay-only olay/komut/donanım sonucu üretir | hardware adapter çağırmaz; yalnız kayıt okur |
| `POST /stage` | UI → Backend | `StageRequest` gönderir; aşama/tur bağlamını ve beklenen modu günceller | geçersiz aşama/tur `BLOCKED_INVALID_COMMAND` olur; fiziksel çıkış yok |
| `POST /mode` | UI → Backend | `ModeRequest` gönderir | geçersiz modlar `BLOCKED_MODE` olur |
| `POST /manual-aim` | UI → Backend | `ManualAimCommand` gönderir | manuel mod + deadman koşulu yoksa engellenir |
| `POST /fire-intent` | UI → Backend | `FireIntent` gönderir | safe mod, dost hedef, menzil dışı veya live arming yoksa Hardware Adapter çağrılmaz |
| `POST /telemetry/reset` | UI/Debug → Backend | dry-run state ve JSONL kanıtını sıfırlar | safe moda döner; fiziksel çıkış üretmez |

İlk `Hardware Adapter`, `hardware_mock.dry_run` olarak davranır. Komut kabul edilse bile sonuçta `physicalOutput=false` ve “fiziksel çıkış üretilmedi” mesajı bulunur. Komut sonuçları, olaylar ve dry-run hardware sonuçları git’e eklenmeyen `telemetry_data/operator-api-dry-run.jsonl` dosyasına JSONL olarak yazılır; `GOKKALKAN_TELEMETRY_JSONL` veya `--telemetry-jsonl` ile farklı yol seçilebilir. Operatör panelindeki `Sistem Durumu` kartı `/readiness` endpoint’inden hangi arayüzlerin hazır/kısmi/TBD/kilitli olduğunu gösterir; bu yüzde resmi yarışma uygunluk skoru değildir. Kapalı gelen `Kayıt / Replay` çekmecesi export/replay endpoint’lerini okuyup KTR/debug kanıtını görselleştirir; replay akışı hardware adapter çağırmaz. MCU hattı ADR-002 ile klasik CAN olarak, menzil sensörü ADR-003 ile TFA50-L olarak seçilmiştir; gerçek firmware, serial adapter ve kalibrasyon tamamlanana kadar canlı arming kilitli kalır.

## 5.2. Uygulanan dry-run operatör paneli yüzeyi

Bu geçişten sonra yazılım ekibinin mekanik/elektronik rehberi gerektirmeyen operatör paneli yüzeyi tamamlanmıştır:

- üst durum şeridi: aşama/tur, backend, perception, TFA50-L 1D menzil, Safety Gate ve API kaynağı,
- `Sistem Durumu`: hazır/kısmi/TBD/kilitli arayüz kartları; resmi uygunluk skoru değildir,
- `Aşama / Tur kontrolü`: Aşama 1 manuel, Aşama 2 otonom 4 resmi tur ve sınıflandırmasız takip, Aşama 3 otonom 8 tur + dost/düşman + menzil kapısı bağlamını gösterir,
- Aşama 1 kamera görünümü: gerçek MJPEG akışı, merkez nişangâh, canlı boresight menzili ve kalibre edilmiş balistik holdover,
- hedef iz ekranı: dry-run `TrackState`, seçili hedef ayrıntısı, dost/düşman, menzil, açı, güven, kaynak ve timestamp,
- komut paneli: Safe/Manuel/Otonom/Bakım modları, deadman’li `ManualAimCommand`, hız limiti, `FireIntent`, blok gerekçesi,
- `Interlock`: Acil Durdur, hareket alanı, atış alanı, hedef kapısı, mod kapısı ve backend bağlantısı,
- hardware sonucu: backend kabulünden dönen `HardwareResult` ve açık `physicalOutput=false` gösterimi,
- `Entegrasyon`: perception adapter, TFA50-L adapter, MCU/hardware protokolü ve canlı arming/interlock durumlarını gerçek fiziksel kanıt gelene kadar kısmi/kilitli tutar,
- `Kayıt / Replay / Log`: JSONL export, replay-only özet, command/hardware kayıtları ve fiziksel çıkışsız kanıt.

Backend tarafında `ManualAimCommand` artık manuel mod + deadman yanında sayı/bounds doğrulamasından geçer. Bu bounds yazılım guardrail’idir; gerçek servo limitleri ve hızları mekanik/elektronik ekip kararından sonra güncellenecektir.

`SensorFrame` replay fixture’ı gerçek veri iddiası taşımaz. Seçilen TFA50-L tek
nokta menzil sensörünün kabulü kendi 5/10/15 m kayıtlarıyla yapılır. Bu repo
büyük dış dataset veya model dosyası commit etmez; fiziksel UART ve kalibrasyon
kanıtı tamamlanana kadar fixture yalnız arayüz ve KTR kanıtı üretir.

## 5.3. TFA50-L 1D teşhis stratejisi

TFA50-L bir tarama/point-cloud sensörü değildir; bu nedenle ayrı bir ham LiDAR
sayfası veya vendor viewer görev arayüzüne eklenmez. Seri port, firmware, health,
boresight hizası ve 5/10/15 m kalibrasyon kanıtı bakım/telemetri yüzeyinde
izlenir.

Final saha hedefi tek Gökkalkan Operator Panel programıdır:

```text
TFA50-L UART adapterı
  -> Sensor Adapter servisi
  -> ortak SensorFrame akışı
  -> Backend füzyon / görev / safety gate
  -> Gökkalkan Operator Panel
```

Ana panel canlı görevde 1D menzili kamera/taret ekseniyle birlikte sayısal olarak
gösterir. Ayrıntılı seri mesajlar ve kalibrasyon raporları operatör akışını
kalabalıklaştırmadan bakım/telemetri tarafında kalır.

Paketleme hedefi:

- geliştirme ve demo için: `npm run desktop` backend API + UI + desktop app-window akışını tek komutla başlatır; `npm run desktop:check` aynı hattı browser açmadan smoke-test eder,
- saha bilgisayarı Linux ise: backend + adapter servisleri + operatör UI tek launcher altında, tercihen AppImage veya systemd servisleri + kiosk shell,
- Windows demo gerekiyorsa: aynı launcher mantığının `.exe` çıktısı,
- her iki durumda da canlı fiziksel çıkış, `dry-run` yerine iki aşamalı arming + fiziksel interlock + hakem/operatör prosedürü tamamlanmadan açılamaz.

## 6. Karar ve kalan fiziksel doğrulama

Gerçek operatör paneli mevcut React/Vite frontend içinde ayrı sayfa ve Python
backend/API servisleriyle uygulanmıştır. Bu seçim korunmalıdır; çünkü:

- Mevcut simülatörde yarışma dili, stage UI, hedef silüetleri ve safety summary zaten oluştu.
- Backend API ile ayrım korunursa UI teknolojisi safety-kritik karar katmanı olmaz.
- KTR için hem simülatör hem gerçek panel ekranları aynı tasarım sistemiyle tutarlı görünür.

Canlı saha testi başlamadan önce şu fiziksel kabuller hâlâ kapatılmalıdır:

- TFA50-L güç/UART/hizalama ve 5/10/15 m kabulü,
- USB CDC protokolünün gerçek Pico ile disconnect/reconnect, ACK ve EMI HIL kabulü,
- gerçek panelin dry-run/live geçiş prosedürü,
- Acil Durdur’un fiziksel kesme hattı ve backend state bildirimi,
- SQLite WAL + segmentli JSONL session/replay yolu uygulanmıştır; saha quota,
  video segment süresi ve retention değerleri fiziksel bilgisayar yük testinde
  kalibre edilmelidir.
