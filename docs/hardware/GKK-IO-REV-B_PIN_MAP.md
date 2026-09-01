# GKK-IO-REV-B — Arduino Uno + DM542 saha profili R1

> **Durum:** Yazılım/firmware sözleşmesine işlendi; elektriksel ve hareket
> kabulü açık. Profil, sahada motor döndürmek için kullanılan
> `GOKKALKAN-LITE` entegrasyon referansından türetilmiştir. Bu referans yerel
> olarak `.gitignore` altındadır; kendi başına şema, ölçüm veya yarışma kabul
> kanıtı değildir.
>
> **Profil kimliği:** `GKK-UNO-DM542-1600PPR-R1`
> **Firmware:** `realtimetesting/arduino_uno/arduino_uno.ino`
> **Backend sınırı:** `ArduinoUnoMotorAdapter`

Bu belge aktif Arduino yolunu tanımlar; Pico/COBS/CAN dosyaları yalnız legacy
regresyon bağlamındadır. Şartname gereği hareket ve atış yasak bölgeleri,
haricî Acil Durdur ve hakem güvenlik onayı bu profilden bağımsız zorunluluktur.

## R1 pin ve kablolama profili

| Sinyal | Arduino Uno | DM542 bağlantısı | Firmware davranışı | Doğrulama durumu |
|---|---:|---|---|---|
| PAN `PUL+` | D2 | PAN sürücü `PUL+` | Adım darbesi | Lite saha referansı; osiloskop/boş yük doğrulaması açık |
| PAN `DIR+` | D3 | PAN sürücü `DIR+` | `HIGH=CW`, `LOW=CCW` | Mekanik yön etiketi sahada doğrulanacak |
| TILT `PUL+` | D4 | TILT sürücü `PUL+` | Adım darbesi | Lite saha referansı; osiloskop/boş yük doğrulaması açık |
| TILT `DIR+` | D5 | TILT sürücü `DIR+` | `HIGH=CW`, `LOW=CCW` | Mekanik yön etiketi sahada doğrulanacak |
| Ortak dönüş | Arduino GND | Her iki sürücüde `PUL-` ve `DIR-` | Ortak katot | Sürücü giriş türü ve kaçak/toprak ölçümü zorunlu |
| Etkinlik göstergesi | D13 | Kart üzeri LED | Motor aktifken yanar | Tanısal; emniyet işlevi yok |
| `ENA+` / `ENA-` | Bağlı değil | Lite R1 referansında bağlı değil | Firmware sürmez | Evrensel kural değildir; yalnız sürücü dokümanı ve elektriksel inceleme sonrası değiştirilebilir |
| E-Stop güvenli duruşu | Arduino pini yok | Haricî E-Stop/kontaktör zinciri | Motor enerjisini Arduino'dan bağımsız kesmelidir | Fiziksel kabul açık |
| `FIRE_OUT`, arm, geri bildirim | Yok | Ayrı güvenlik-kritik tasarım | Bu firmware'de yok | Fail-closed; aktarılamaz |
| PAN/TILT encoder | Yok | Ayrı alıcı/protokol gerekir | Otonom hareket engellenir | Açık |

**Önemli:** Ortak katot satırı yalnız R1 Lite saha bağlantı referansıdır. DM542
klonları, giriş optokuplörleri ve ortak toprak düzeni farklı olabilir. Ana güç,
koruyucu toprak ve sürücü lojik girişlerinin bağlantısı enerji verilmeden önce
üretici dokümanı, izolasyon ve süreklilik ölçümüyle yetkili ekip tarafından
doğrulanmalıdır.

## Kalibrasyon ve komut sınırları

R1, `1600` pulse/revolution varsayımıyla çalışır:

- `1600 / 360 = 4,444…` pulse/derece.
- Backend tek manuel komutta en çok `11,25°` yani `50` pulse üretir.
- Manuel hız üst sınırı `30°/s`tir. İstenen hız, firmware'e yarım-periyot
  gecikmesi olarak çevrilir; örneğin `15°/s` için `7500 µs` gönderilir.
- Firmware `STEP_*` için `1..1600` pulse ve `80..1_000_000 µs` yarım periyot
  aralığını kabul eder.
- `RUN*` sadece bakım içindir: `1..15 s`, `1..1250 Hz`.
- `JOG_*` yalnız bakım içindir ve en fazla `1000 ms` sonra otomatik `STOP`
  durumuna geçer. Operatör API'si `JOG` kullanmaz.

Lite referansında 1600 pulse/revolution için belirli DM542 DIP anahtarları ve
akım ayarları önerilmiştir; sürücü varyantı ve motor etiketleri bilinmeden bu
ayarlar kanonik kabul edilmez. Kullanılan sürücü üzerindeki gerçek DIP durumu,
üretici tablosu ve akım değeri saha konfigürasyon kaydına yazılmalıdır.

## 115200 baud R1 seri sözleşmesi

Fiziksel Arduino yolu ASCII, satır sonu `\n` ve `115200` baud kullanır.
Fiziksel çıkıştan önce backend şu karşılıklı doğrulamayı yapar:

```text
PING       -> PONG
PROFILE    -> PROFILE GKK-UNO-DM542-1600PPR-R1
```

`PING`, `PROFILE` veya beklenen profil uyuşmazsa adapter seri bağlantıyı kapatır
ve hiçbir `STEP_*` komutu göndermez. `loop://` yalnız çerçeveleme/SIM-HIL
kanıtıdır; firmware, USB cihazı veya kablo doğrulaması sayılmaz.

| Komut | Biçim | Yanıt / sınır |
|---|---|---|
| Bağlantı | `PING`, `PROFILE` | Yukarıdaki kesin yanıtlar |
| Durum | `STATUS` | `STATUS … PROFILE=…` |
| Sınırlı hareket | `STEP_PAN <pulse> <half_period_us> <CW\|CCW>`; `STEP_TILT …` | `OK STEP_*` veya `ERR …` |
| Bakım koşusu | `RUN[_PAN\|_TILT] <sec> <speed_hz> [CW\|CCW]` | En fazla 15 s; `OK RUNNING …` |
| Bakım jog'u | `JOG_PAN [half_period_us] [CW\|CCW]`; `JOG_TILT …` | En fazla 1 s; watchdog sonrası `ERR JOG_TIMEOUT_STOPPED` |
| Durdurma | `STOP` (`0` / `S` menü eşdeğeri) | İdempotent `OK STOPPED` |

Firmware eksik/fazla argümanları, negatif değerleri, taşmaları, limit dışı
sayısal değerleri ve tanımsız yönleri `ERR …` ile reddeder. `FIRE`, `ARM`,
hedef seçimi veya encoder konumu için seri komut **yoktur**.

## Güvenlik ve kabul kapıları

Bu sırayı tamamlamadan fiziksel motor komutu gönderilmemelidir:

1. **Enerjisiz inceleme:** D2–D5, GND, sürücü güç/toprak ve kablo izolasyonunu
   şemaya ve sürücü veri sayfasına göre kontrol et; açık iletken bırakma.
2. **Haricî güvenli duruş:** E-Stop'un kontaktörü Arduino/USB'den bağımsız
   bıraktığını, motor beslemesini kestiğini ve resetin kontrollü olduğunu ölç.
3. **Sinyal doğrulama:** DM542 güç katı bağlı değilken boot/reset ve `STOP`
   sırasında PUL düşük seviyesini, D2–D5 frekans/yönünü osiloskopla doğrula.
4. **Profil doğrulama:** Yalnız R1 firmware ile `PING`/`PROFILE` eşleşmesini
   kaydet. Eski sketch, başka USB cihazı veya `loop://` fiziksel kabul değildir.
5. **Düşük enerjili hareket:** Boş ve erişimi sınırlı çalışma alanında tek
   eksen, küçük `STEP_*`, ardından `STOP`; gerçek yönü ve mekanik limitleri
   ölç. Sonra iki ekseni ayrı ayrı değerlendir.
6. **Sistem kabulü:** Safety Gate hareket yasak bölgesi, E-Stop altında hareket
   kesilmesi, telemetri kanıtı ve yarışma hakeminin güvenlik uygunluğu ayrı
   testlerle doğrulanır.

Yazılımın `STOP` göndermesi fiziksel kontaktör/E-Stop doğrulamasının yerine
geçmez. Bu R1 profilinde ateşleme ve geri bildirim hattı bilinçli olarak
uygulanmamıştır; bu nedenle fiziksel HIL kanıtı, LIVE yetkisi veya yarışma
kabulü iddia edilmez.
