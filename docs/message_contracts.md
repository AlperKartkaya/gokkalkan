# Mission Core Mesaj Sözleşmeleri

Bu belge, operatör API, CAN/GPIO callback’leri ve perception süreci ile tek
sahipli Mission Core arasındaki izlenebilir mesaj sınırını tanımlar. Sözleşmenin
uygulaması `backend/src/gokkalkan_backend/messages.py` dosyasındadır.

## Sürüm politikası

- Güncel `schemaVersion`: **1**.
- Mission Core yalnız açıkça desteklediği şema sürümlerini kabul eder. Bilinmeyen
  sürüm sessizce dönüştürülmez; `409 message_contract` ile reddedilir.
- v1’e yeni, isteğe bağlı alan eklenebilir. Bir alanın anlamı veya tipi
  değişecekse yeni bir şema sürümü gerekir.
- Üretici önce yeni sürümü yazmadan önce tüketicinin o sürümü kabul ettiğini
  doğrulamalıdır. Geçiş süresince eski ve yeni decoder birlikte tutulur.
- Alan adları HTTP/JSON sınırında `camelCase`, Python içinde `snake_case` olur.

## `CommandEnvelope` v1

| Alan | Zorunlu | Anlam |
| --- | --- | --- |
| `schemaVersion` | evet | Mesaj şeması; bugün `1` |
| `runId` | evet | Backend çalıştırma/oturum kimliği |
| `commandId` | evet | Uçtan uca idempotency ve sorgulama kimliği |
| `sequence` | evet | Mission Core giriş sırası |
| `createdAtUtc` | evet | İnsanlar ve dış sistemler için UTC zamanı |
| `createdAtMonotonicNs` | evet | Aynı process içinde süre/sıra ölçümü |
| `source` | evet | `operator-http`, `perception`, `can-estop` gibi üretici |
| `kind` | evet | `ModeRequest`, `TracksUpdate`, `EStopChange` gibi komut türü |
| `payload` | evet | Türe özgü, kuyruğa girerken immutable yapılan veri |
| `causationId` | hayır | Bu komutu doğuran önceki mesaj/işlem |
| `targetId` / `trackId` | hayır | Hedef iziyle korelasyon |
| `sourceSequence` | hayır | Üreticinin kendi monoton sırası |

HTTP istemcisi `Idempotency-Key` başlığı veya payload içindeki `commandId` ile
kimliği belirleyebilir. Aynı kimlik ve aynı içerik tekrar gelirse mevcut sonuç
döner; aynı kimlik farklı içerikle kullanılırsa mesaj reddedilir.

## `EventEnvelope` v1

Her indirgenen komut tam bir olay üretir. `eventId`,
`EVT-{runId}-{sequence}` biçimindedir. Ortak alanlara ek olarak `eventType`,
`commandId` ve `payload` bulunur. `payload`, kabul/red durumunu, komut türünü ve
fiziksel çıkışın oluşup oluşmadığını taşır. Böylece HTTP cevabı, telemetri kaydı
ve state snapshot aynı `runId` / `commandId` / `eventId` zinciriyle
ilişkilendirilebilir.

## Sıralama ve backpressure

1. HTTP/CAN/sensör üreticileri state değiştirmez; bounded Mission Core kuyruğuna
   envelope bırakır.
2. Tek reducer thread’i olay sırasını üretir ve ardından immutable snapshot
   yayınlar.
3. Acil Durdur olayı kuyrukta güvenlik önceliği alır. Olay `sequence` değeri
   gerçek indirgeme sırasıdır; giriş `sequence` değerinden farklı olabilir.
4. `sourceSequence`, aynı kaynaktan gelen duplicate veya geriye giden sensör
   güncellemelerini deterministik olarak `OUT_OF_ORDER_SOURCE_SEQUENCE` ile
   reddeder.
5. Dolu Mission Core kuyruğu `503 queue_full` döndürür. Perception’ın process
   içi kuyruğu ise CPU üreticisini bekletmez; en eski sonucu düşürüp en yeni
   sonucu korur ve düşen sayısını heartbeat’te bildirir.

## Snapshot ve state stream

- `GET /state`, yayındaki immutable snapshot’ın ayrılmış JSON kopyasını döner.
- `GET /state/stream?after=N`, `text/event-stream` üzerinden `event: state`
  olayları yayınlar. `id`, `snapshotVersion` değeridir.
- Reducer her olaydan sonra ve aktif görev/bakım sayaçlarının donmaması için en
  geç bir saniyede bir yeni snapshot üretir; HTTP okuyucusu state’i hesaplamaz
  veya değiştirmez.
- Operatör paneli SSE’yi ana yol olarak kullanır; stream kesilirse iki saniyelik
  düşük hızlı REST snapshot yedeğine geçer. `/readiness` beş saniyede bir
  yenilenir ve görev state’i sayılmaz.
- `GET /commands/{commandId}`, zaman aşımı nedeniyle ilk HTTP isteği `202`
  döndüğünde de komut sonucunun izlenmesini sağlar.

## Kapanış ve hata davranışı

Mission Core yeni komut kabulünü kapatır, sıradaki mevcut komutları tamamlar ve
sonra `STOPPED` snapshot’ı yayınlar. Perception ayrı bir `systemd` process’idir;
heartbeat zaman aşımı veya açık `healthy=false` bildirimi
`PERCEPTION_UNHEALTHY` fault’u üretir, perception sağlığını ve canlı arm iznini
kapatır. Bu yazılımsal fail-closed davranış, fiziksel Acil Durdur ve Pico
watchdog zincirinin yerine geçmez.
