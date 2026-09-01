# ADR-006 — Arduino Uno saha motor yolu ve R1 profil doğrulaması

## Durum

Kabul edildi (2026-08-26), R1 profil sözleşmesiyle güncellendi (2026-09-01).
İmalat ekibinin sahadaki kartı Arduino Uno'dur; Pico firmware'i aktif donanım
sözleşmesi değildir.

## Bağlam

Yerel `GOKKALKAN-LITE` referansı Arduino Uno üzerinden iki DM542 sürücünün
mekanik/elektronik entegrasyon sonrasında hareket ettirilebildiğini bildiren pin
ve seri protokol ayrıntılarını içerir. Bu bilgi, şematik, ölçülmüş interlock ve
fiziksel kabulün yerini tutmaz. Şartname; hareket/atış yasak bölgelerini,
haricî Acil Durdur'u ve güvenlik uygunluk onayını zorunlu kılar.

## Karar

- Aktif Pi 5 ↔ Arduino Uno yolu `115200` baud USB seri, ASCII ve satır sonu
  `\n` protokolüdür.
- Sabit R1 kimliği `GKK-UNO-DM542-1600PPR-R1`dir. Firmware ile backend bu
  kimliği paylaşır; pinler PAN PUL/DIR=`D2/D3`, TILT PUL/DIR=`D4/D5`tir.
  Arduino GND'nin DM542 `PUL-`/`DIR-` ile ortak katot kullanımı Lite R1
  referansıdır ve her gerçek sürücüde elektriksel olarak doğrulanmalıdır.
- Firmware flash sonrasında fiziksel adapter `PING → PONG` ve
  `PROFILE → PROFILE <R1>` doğrulamasını yapmadan `STEP_*` göndermez.
  Uyumsuz/yanıtsız cihaz kapatılır. `loop://` bu adımı kasıtlı olarak atlar;
  yalnız seri çerçeveleme simülasyonudur ve health yüzeyinde firmware hazır
  sayılmaz.
- `1600` pulse/revolution kalibrasyonundan `4,444…` pulse/derece kullanılır.
  Backend tek manuel niyeti `11,25°`, `30°/s` ve firmware'in adım/gecikme
  sınırları ile daraltır; istenen hız yarım-periyot gecikmesine çevrilir.
- Firmware, `STEP_*`, sınırlı `RUN*`, watchdog'lı bakım `JOG_*`, `STOP`,
  `PING`, `PROFILE` ve `STATUS` ile sınırlıdır. Sayısal aralık, yön ve fazla
  argüman hatalarını açık `ERR …` yanıtlarıyla reddeder.
- `JOG_*` en fazla bir saniye sürer. Operatör API'si JOG kullanmaz; `RUN*` ve
  Python araçları yalnız kontrollü bakım amaçlıdır.
- `FIRE`, `ARM`, hedefleme ve encoder geri bildirimi Arduino seri
  sözleşmesinden bilinçli olarak çıkarılmıştır. `FireIntent` ve
  `AutonomousAimCommand` adapter sınırında, seri cihaz açılmadan reddedilir.
- `hil-physical.toml`, açıkça seçildiğinde yalnız manuel PAN/TILT hareketine
  fiziksel çıkış yetkisi verebilir. Deadman/Safety Gate geçerlidir; yazılım
  E-Stop ve kontrollü duruşlar idempotent `STOP` gönderir.
- `firmware/pico/`, `usb_serial_mcu_protocol.md` ve CAN codec dosyaları legacy
  referans olarak tutulur; yeni saha özelliği bu yola eklenmez.

## Sonuçlar ve kabul sınırı

Bu karar, hatalı USB cihazına veya eski firmware'e hareket komutu gönderme
riskini azaltır ve Lite'taki pin/pulse bilgisini izlenebilir bir sözleşmeye
bağlar. Bunun karşılığında R1 olmayan kartlar motor komutu alamaz; sahada
firmware flash ve profil kontrolü zorunlu bakım adımıdır.

Arduino firmware'i E-Stop kontaktörü, encoder, ateşleme interlock'u veya
sürekli güvenlik telemetrisi sağlamaz. Bu nedenle test/SIM/loopback sonucundan
fiziksel kablo, motor yönü, E-Stop veya LIVE kabulü çıkarılamaz. Ayrıntılı pin
haritası, komut sınırları ve ölçüm kapıları
[`GKK-IO-REV-B_PIN_MAP.md`](../hardware/GKK-IO-REV-B_PIN_MAP.md) dosyasındadır.
