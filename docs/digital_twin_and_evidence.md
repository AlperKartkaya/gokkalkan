# Faz 6–7: Dijital İkiz, Session, Replay ve Kanıt

Bu belge imalat öncesi yazılım doğrulama yolunu açıklar. Buradaki sonuçlar
**yazılım/mock kanıtıdır**. Şartname v1.4 §2.4.4’teki entegre sistem, 15 m balon,
hareket/atış sırasında Acil Durdur, gerçek hedef takibi ve sınıflandırma
gösterimlerinin yerine geçmez.

## 1. Dijital ikiz

`gokkalkan_backend.digital_twin` şu sınırları modellenebilir yapar. Aşağıdaki
COBS/ACK maddeleri aktif Arduino saha taşıması değil, legacy protokol regresyonudur:

- USB taşımasında da korunan tarihsel v1 META + payload, sequence ve ACK/NACK;
- ACK gecikmesi, drop/timeout, bozuk ACK, E-Stop, heartbeat ve encoder fault;
- pan/tilt hız, ivme, soft limit, backlash ve encoder geri bildirimi;
- kamera track ve TFA50-L menzil/no-detection fixture’ları;
- bozuk UART, stale, dropout ve clock-skew sensör akışları;
- Safety Gate kararı olmadan etkinleşmeyen fiziksel çıkışsız lamba/yapay yük.

Dinamik varsayılanları ölçüm değildir. İmalat sonrası gerçek motor, redüksiyon,
enkoder ve yük ölçümleriyle config’e taşınmalı; test beklentileri ölçüm tutanağına
bağlanmalıdır.

```bash
gokkalkan scenario run stage1-manual
gokkalkan scenario run stage2-autonomous
gokkalkan scenario run stage3-friend-foe
gokkalkan scenario run estop
gokkalkan scenario run connection-loss
gokkalkan scenario run wrong-target
gokkalkan scenario fixtures telemetry_data/sensor-fixtures.jsonl
```

## 2. Tek-yazarlı session

Producer’lar backend içinde bounded queue’ya veya
`TelemetryProducer` ile Unix datagram socket’ine yazar. Kalıcı event ID ve
sequence yalnız `SessionTelemetryStore` writer’ında atanır.

Bir session:

- `events.sqlite3`: WAL event/media index’i;
- `events-NNNNNN.jsonl`: taşınabilir segmentli export;
- `manifest.json`: Git SHA, build/operator, OS/Python/paket sürümleri ve
  config/calibration/BOM hash’leri;
- `media_index`: kamera/video, LiDAR ve CAN kayıtlarının ortak monotonic aralığı;
- bütünlük sorunları: düşük disk, quota/retention, eksik medya/kaynak.

Runtime config her zaman manifest’e girer. Kalibrasyon ve BOM için
`GOKKALKAN_CALIBRATION_FILE` ve `GOKKALKAN_BOM_FILE`; operatör için
`GOKKALKAN_OPERATOR_ID`, build için `GOKKALKAN_BUILD_ID` kullanılır.

## 3. Güvenli replay ve doğrulama

Replay salt okunurdur; `HardwareAdapter` oluşturmaz ve `physicalOutput=false`
sınırını doğrular.

```bash
gokkalkan replay verify telemetry_data/operator-api-dry-run-<zaman>-<id>.session
gokkalkan replay run telemetry_data/operator-api-dry-run-<zaman>-<id>.session
gokkalkan evidence verify telemetry_data/operator-api-dry-run-<zaman>-<id>.session
```

`ok=false` üreten session rapor/KTR kanıtı olarak kullanılmamalıdır.

## 4. Kanıt paketi

Önce session kapatılıp finalize edilmelidir. Event’lerin `monotonicNs` aralığı
seçilerek yetenek kimliği, ilgili event’ler, kesişen medya dosyaları, session
manifest’i ve SHA-256 manifest’i tek ZIP’e alınır:

```bash
gokkalkan evidence build telemetry_data/operator-api-dry-run-<zaman>-<id>.session \
  --output telemetry_data/VID-Y3.zip \
  --capability VID-Y3-ESTOP-MOTION \
  --start-ns 1000000000 \
  --end-ns 2000000000

gokkalkan evidence verify telemetry_data/VID-Y3.zip
```

Kamera karesi, TFA50-L paketi, MCU ACK’i ve sonuç olayı aynı
`commandId` ve monotonic zaman aralığıyla ilişkilendirilmelidir. Fiziksel testte
video segmenti ayrıca session’a `index_media` ile bağlanmalıdır.

## 5. İmalat sonrası açık kabul kapıları

1. USB/Pico gerçek ACK zamanları, disconnect/reconnect davranışı ve hata oranı.
2. Motor yükü altında hız/ivme/backlash ve encoder sapması.
3. Kablolu E-Stop’un motor ve imha enerjisini fiziksel kesmesi.
4. TFA50-L gerçek UART/no-detection/stale davranışı ve kamera-LiDAR hizası.
5. Disk kotası, video segment süresi ve retention’ın saha bilgisayarında yük testi.
6. Şartname §2.4.4 yeteneklerinin tek, 720p+, 2–5 dakikalık entegre videoda
   şartnamedeki sırayla gösterilmesi.
