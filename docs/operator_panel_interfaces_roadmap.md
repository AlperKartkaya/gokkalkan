# Gerçek Operatör Paneli ve Arayüz Yol Haritası

Bu doküman, simülatörden ayrı olarak final fazında kullanılacak gerçek operatör paneli için önerilen mimariyi ve KTR’de anlatılacak arayüzleri toplar. Şartname nihai otoritedir; burada seçilmemiş donanım/protokol değerleri `TBD` olarak bırakılır.

## 1. Neden ayrı bir operatör paneli?

Mevcut `frontend/` ekranı yarışma eğitim simülatörüdür. Gerçek operatör paneli ise canlı backend, perception, sensör ve donanım adapter’larına bağlanan kontrol istasyonu olmalıdır. Landing ekranında `Simülasyona Başla` butonunun altında ikinci bir buton önerilir:

```text
Operatör Paneli
Gerçek sistem bağlantısı / dry-run destekli
```

İlk sürümde bu buton backend bağlantısı yoksa `Dry-run` veya `Bağlantı bekleniyor` etiketiyle açılabilir. Asla simülatör puan mantığını gerçek ateşleme durumu gibi göstermemelidir.

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

## 3. Önerilen sayfa yapısı

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
   - radar/LiDAR ölçümü,
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
   - repo içi entegrasyon yüzdesi,
   - hazır/kısmi/TBD/kilitli arayüz kartları,
   - sıradaki kritik radar/LiDAR, perception, MCU ve arming adımları.
   - Bu gösterge resmi yarışma uygunluk skoru değildir; yalnız uygulanmış yazılım arayüzlerinin durumunu dürüstçe gösterir.
7. **Kayıt / Replay çekmecesi**
   - JSONL telemetri yolu ve kayıt sayısı,
   - `/telemetry/export` kanıt paketi,
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
| `SensorFrame` | Sensor Adapter → Backend/UI | `sensor`, `rangeM`, `bearingDeg`, `radialVelocity`, `rcs/snr`, `pointCount`, `quality`, `timestamp`, `trackId` | JSON replay/stream | gerçek radar/LiDAR seçilince adapter doldurur; fixture canlı veri iddiası taşımaz |
| `HardwareCommand` | Backend → Adapter | `commandId`, `kind`, `panTilt`, `fireEnable`, `timeoutMs` | Python adapter interface | MCU protokolüne çeviri |
| `CommandResult` | Adapter → Backend/UI | `commandId`, `accepted`, `completed`, `faultCode`, `latencyMs` | JSON event | gerçek zaman ölçümü |
| `TelemetryEvent` | Tüm katmanlar → Log | `timestamp`, `stage`, `mode`, `eventType`, `payload` | JSONL | replay/rapor export |

### 4.3. Sensör ve veri aktarımı arayüzleri

| Bileşen | Veri | Arayüz durumu | Not |
| --- | --- | --- | --- |
| Kamera | görüntü karesi, frame timestamp, exposure/health | kamera seçimine bağlı TBD | İlk algı hattı OpenCV ile açıklanabilir olmalı |
| Radar / LiDAR | menzil, açı, kalite, timestamp | donanım seçimine bağlı TBD | Şimdilik `SensorFrame` adapter sözleşmesiyle soyutlanmalı |
| Perception | hedef adayı, takip izi, sınıf/dost-düşman | backend’e stream | Aşama 2’de sınıflandırma zorunlu değil; Aşama 3’te gerekli |
| Backend | görev durumu, SafetyState, CommandResult | UI’ya stream | UI, backend state olmadan live komut açmamalı |

### 4.4. Elektronik güç/sinyal arayüzleri

Kesin elektronik değerler tasarım netleşince doldurulmalıdır. KTR’de yanlış kesinlikten kaçınmak için şu format önerilir:

| Arayüz | KTR’de anlatılacak içerik | Durum |
| --- | --- | --- |
| Ana güç dağıtımı | batarya/güç kaynağı, sigorta, ana kesme, regülasyon | TBD |
| Logic güç | MCU, sensör ve haberleşme seviyeleri | TBD |
| Acil Durdur | fiziksel buton, UI’dan bağımsız kesme/disable, backend bildirimi | Zorunlu |
| MCU haberleşmesi | pan/tilt ve imha hattı komutlarının taşındığı protokol | UART/RS422/CAN/Ethernet seçilecek |
| Kamera bağlantısı | USB/CSI/Ethernet seçimi, frame aktarımı ve gecikme ölçümü | TBD |
| Radar/LiDAR bağlantısı | güç, veri, timestamp, sağlık mesajı | TBD |
| İmha hattı | patlayıcı olmayan mekanizma, interlock, Safety Gate sonrası enable | Güvenlik-kritik |

## 5. Önerilen uygulama sırası

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
   - Kamera ve radar/LiDAR ayrı adapter’lar olarak bağlanır.
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
PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server --host 127.0.0.1 --port 8088
# KTR/debug kanıtını belirli dosyaya yazmak için:
PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server --host 127.0.0.1 --port 8088 --telemetry-jsonl telemetry_data/operator-api-dry-run.jsonl
```

Uygulanan endpoint’ler:

| Endpoint | Yön | Amaç | Güvenlik notu |
| --- | --- | --- | --- |
| `GET /health` | UI → Backend | API sağlığı, dry-run ve fiziksel çıkış durumunu okur | `physicalOutputEnabled=false` döner |
| `GET /state` | UI → Backend | mod, aşama, izler, `SafetyState`, `CommandResult` ve olay akışını alır | varsayılan izler dry-run kaynaktır |
| `GET /sensor-frames` | UI → Backend | radar/LiDAR biçimli `SensorFrame` replay paketini ve sağlık özetini alır | `replayOnly=true`; gerçek sensör bağlı iddiası taşımaz |
| `GET /readiness` | UI/KTR → Backend | final fazı entegrasyon hazırlığı, arayüz durumu ve kritik sonraki adımları alır | resmi yarışma uygunluk skoru değildir; TBD değerleri açık bırakır |
| `GET /events` | UI → Backend | telemetri/komut olay listesini alır | rapor ve KTR kanıtı için JSON olaylar |
| `GET /telemetry/export` | UI/Debug → Backend | JSONL log, state, command result ve event kayıtlarını tek kanıt paketinde dışa aktarır | replay/export fiziksel çıkış üretmez |
| `GET /replay` | UI/Debug → Backend | JSONL kayıtlarından replay-only olay/komut/donanım sonucu üretir | hardware adapter çağırmaz; yalnız kayıt okur |
| `POST /stage` | UI → Backend | `StageRequest` gönderir; aşama/tur bağlamını ve beklenen modu günceller | geçersiz aşama/tur `BLOCKED_INVALID_COMMAND` olur; fiziksel çıkış yok |
| `POST /mode` | UI → Backend | `ModeRequest` gönderir | geçersiz modlar `BLOCKED_MODE` olur |
| `POST /manual-aim` | UI → Backend | `ManualAimCommand` gönderir | manuel mod + deadman koşulu yoksa engellenir |
| `POST /fire-intent` | UI → Backend | `FireIntent` gönderir | safe mod, dost hedef, menzil dışı veya live arming yoksa Hardware Adapter çağrılmaz |
| `POST /telemetry/reset` | UI/Debug → Backend | dry-run state ve JSONL kanıtını sıfırlar | safe moda döner; fiziksel çıkış üretmez |

İlk `Hardware Adapter`, `hardware_mock.dry_run` olarak davranır. Komut kabul edilse bile sonuçta `physicalOutput=false` ve “fiziksel çıkış üretilmedi” mesajı bulunur. Komut sonuçları, olaylar ve dry-run hardware sonuçları git’e eklenmeyen `telemetry_data/operator-api-dry-run.jsonl` dosyasına JSONL olarak yazılır; `GOKKALKAN_TELEMETRY_JSONL` veya `--telemetry-jsonl` ile farklı yol seçilebilir. Operatör panelindeki `Sistem Durumu` kartı `/readiness` endpoint’inden hangi arayüzlerin hazır/kısmi/TBD/kilitli olduğunu gösterir; bu yüzde resmi yarışma uygunluk skoru değildir. Kapalı gelen `Kayıt / Replay` çekmecesi export/replay endpoint’lerini okuyup KTR/debug kanıtını görselleştirir; replay akışı hardware adapter çağırmaz. Bu, gerçek MCU/radar/LiDAR protokolü seçilene kadar KTR’de “uygulanmış yazılımsal arayüz iskeleti” olarak anlatılabilir; kesin elektronik değer yerine `TBD` korunmalıdır.

## 5.2. Uygulanan dry-run operatör paneli yüzeyi

Bu geçişten sonra yazılım ekibinin mekanik/elektronik rehberi gerektirmeyen operatör paneli yüzeyi tamamlanmıştır:

- üst durum şeridi: aşama/tur, backend, perception placeholder, Radar/LiDAR replay/TBD/canlı, Safety Gate ve API kaynağı,
- `Sistem Durumu`: hazır/kısmi/TBD/kilitli arayüz kartları; resmi uygunluk skoru değildir,
- `Aşama / Tur kontrolü`: Aşama 1 manuel, Aşama 2 otonom 4 resmi tur ve sınıflandırmasız takip, Aşama 3 otonom 8 tur + dost/düşman + menzil kapısı bağlamını gösterir,
- `Radar / LiDAR`: ham menzil/açı/hız/SNR/nokta/kalite verisini yazılımsal hedef tipi, dost/düşman, güven ve range gate ile birlikte gösterir,
- hedef iz ekranı: dry-run `TrackState`, seçili hedef ayrıntısı, dost/düşman, menzil, açı, güven, kaynak ve timestamp,
- komut paneli: Safe/Manuel/Otonom/Bakım modları, deadman’li `ManualAimCommand`, hız limiti, `FireIntent`, blok gerekçesi,
- `Interlock`: Acil Durdur, hareket alanı, atış alanı, hedef kapısı, mod kapısı ve backend bağlantısı,
- hardware sonucu: backend kabulünden dönen `HardwareResult` ve açık `physicalOutput=false` gösterimi,
- `Entegrasyon`: perception adapter, Radar/LiDAR adapter, MCU/hardware protokolü ve canlı arming/interlock durumlarını mekanik/elektronik kararlarına kadar TBD/kilitli tutar,
- `Kayıt / Replay / Log`: JSONL export, replay-only özet, command/hardware kayıtları ve fiziksel çıkışsız kanıt.

Backend tarafında `ManualAimCommand` artık manuel mod + deadman yanında sayı/bounds doğrulamasından geçer. Bu bounds yazılım guardrail’idir; gerçek servo limitleri ve hızları mekanik/elektronik ekip kararından sonra güncellenecektir.

`SensorFrame` replay fixture’ı gerçek veri iddiası taşımaz. Public radar/LiDAR veri kaynakları offline test için değerlendirilebilir; örneğin Oxford Radar RobotCar Dataset Navtech FMCW radar ve Velodyne LiDAR verisi sağlar, nuScenes ise kamera/radar/LiDAR sensör süitiyle örneklenebilir. Bu repo şu an büyük dış dataset veya model dosyası commit etmez; gerçek adapter seçilene kadar fixture yalnız arayüz ve KTR kanıtı üretir.

## 5.3. Vendor LiDAR yazılımı stratejisi

RPLIDAR Viewer, Livox Viewer veya benzeri üretici yazılımları yarışma günü operatör arayüzü olmamalıdır. Bu araçlar laboratuvarda cihazın görüldüğünü, seri/Ethernet ayarlarını, firmware/kalibrasyon durumunu ve ham point cloud kalitesini doğrulamak için değerlidir; fakat `Aşama`, `Tur`, `Safety Gate`, dost/düşman, menzil kapısı, `FireIntent`, MCU interlock ve KTR/replay kanıtı bağlamını bilmezler.

Final saha hedefi tek Gökkalkan Operator Panel programıdır:

```text
Radar/LiDAR SDK veya driver
  -> Sensor Adapter servisi
  -> ortak SensorFrame akışı
  -> Backend füzyon / görev / safety gate
  -> Gökkalkan Operator Panel
```

Bu nedenle vendor viewer sadece bakım/diagnostic modunda, operatör panelinden ayrı açılabilecek yardımcı araç olarak tutulmalıdır. Ana panel, üretici viewer penceresini embed etmeye veya ekran kazımaya çalışmamalıdır; canlı görevde sensör verisini SDK/driver üzerinden `SensorFrame` sözleşmesine çevirip kendi sade polar görünümünü ve hedef kartlarını göstermelidir. `Matplotlib` canlı panel için değil, offline log analizi ve rapor grafikleri için uygundur.

Paketleme hedefi:

- geliştirme ve demo için: `npm run desktop` backend API + UI + desktop app-window akışını tek komutla başlatır; `npm run desktop:check` aynı hattı browser açmadan smoke-test eder,
- saha bilgisayarı Linux ise: backend + adapter servisleri + operatör UI tek launcher altında, tercihen AppImage veya systemd servisleri + kiosk shell,
- Windows demo gerekiyorsa: aynı launcher mantığının `.exe` çıktısı,
- her iki durumda da canlı fiziksel çıkış, `dry-run` yerine iki aşamalı arming + fiziksel interlock + hakem/operatör prosedürü tamamlanmadan açılamaz.

## 6. Karar önerisi

Kısa vadede gerçek operatör panelini mevcut React/Vite frontend içinde ayrı sayfa olarak başlatmak ve Python backend/API servisleriyle paketlemek en pratik yoldur. Bunun nedeni:

- Mevcut simülatörde yarışma dili, stage UI, hedef silüetleri ve safety summary zaten oluştu.
- Backend API ile ayrım korunursa UI teknolojisi safety-kritik karar katmanı olmaz.
- KTR için hem simülatör hem gerçek panel ekranları aynı tasarım sistemiyle tutarlı görünür.

Ancak canlı saha testi başlamadan önce şu kararlar hâlâ kapatılmalıdır:

- radar/LiDAR donanımı ve mesaj formatı,
- MCU haberleşme protokolü,
- gerçek panelin dry-run/live geçiş prosedürü,
- Acil Durdur’un fiziksel kesme hattı ve backend state bildirimi,
- dry-run için JSONL telemetri/replay yolu uygulanmıştır; canlı saha log saklama, süre/latency metriği ve export saklama politikası ayrıca netleştirilmelidir.
