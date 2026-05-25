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
5. **Bakım/kalibrasyon çekmecesi**
   - sensör kalibrasyonu,
   - servo limitleri,
   - dry-run/live ayrımı,
   - ham mesajlar.

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
| `ManualAimCommand` | UI → Backend | `panDelta`, `tiltDelta`, `rateLimit`, `deadmanActive` | JSON/WebSocket | joystick input stream |
| `FireIntent` | UI → Backend | `targetId`, `stage`, `round`, `operatorConfirm`, `dryRun` | JSON/HTTP veya WebSocket command | iki aşamalı arming protokolü |
| `SafetyState` | Backend → UI | `estop`, `motionZoneOk`, `fireZoneOk`, `modeOk`, `targetGate`, `blockReason` | WebSocket state stream | kod + Türkçe açıklama sözlüğü |
| `TrackState` | Perception/Sensor → Backend/UI | `trackId`, `x`, `y`, `rangeM`, `bearingDeg`, `type`, `friendFoe`, `confidence` | JSON stream | binary/protobuf yalnız ihtiyaç olursa |
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

## 6. Karar önerisi

Kısa vadede gerçek operatör panelini mevcut React/Vite frontend içinde ayrı sayfa olarak başlatmak en pratik yoldur. Bunun nedeni:

- Mevcut simülatörde yarışma dili, stage UI, hedef silüetleri ve safety summary zaten oluştu.
- Backend API ile ayrım korunursa UI teknolojisi safety-kritik karar katmanı olmaz.
- KTR için hem simülatör hem gerçek panel ekranları aynı tasarım sistemiyle tutarlı görünür.

Ancak canlı saha testi başlamadan önce şu kararlar kapatılmalıdır:

- radar/LiDAR donanımı ve mesaj formatı,
- MCU haberleşme protokolü,
- gerçek panelin dry-run/live geçiş prosedürü,
- Acil Durdur’un fiziksel kesme hattı ve backend state bildirimi,
- log/telemetri saklama formatı ve KTR kanıt export yolu.
