# ADR-006 — Arduino Uno saha motor yolu

## Durum

Kabul edildi (2026-08-26). İmalat ekibinin sahadaki kartı **Arduino Uno**'dur;
Pico firmware'i aktif donanım sözleşmesi değildir.

## Karar

- RPi 5 ile Arduino Uno arasında 115200 baud USB seri bağlantı kullanılır.
- Arduino firmware sözleşmesi `realtimetesting/arduino_uno/arduino_uno.ino`
  içindeki satır komutlarıdır: `STEP_PAN`, `STEP_TILT`, `RUN_*`, `JOG_*`,
  `STOP` ve `STATUS`.
- Pin haritası sabittir: PAN PUL/DIR = 2/3, TILT PUL/DIR = 4/5; DM542 ENA
  uçları boş bırakılır. Ayrıntılı saha prosedürü `realtimetesting/README.md`'dedir.
- `ArduinoUnoMotorAdapter` komutları lazy-connect ile gönderir; bağlantı yoksa
  hata döndürür ve fiziksel çıkış üretmez. E-Stop ve arm yetkisi backend Safety
  Gate tarafından ayrıca korunur.
- SIM/HIL çalışma yolu Arduino adapter'ının `loop://` seri bağlantısını kullanır;
  backend artık Arduino'ya COBS/CAN çerçevesi göndermez. Eski COBS/ACK adapter'ı
  yalnız tarihsel regresyon testleri için açıkça çağrılabilir.
- `hil-physical.toml`, açıkça seçildiğinde yalnız manuel PAN/TILT hareketine
  fiziksel çıkış yetkisi verir. Operatör deadman'i bırakıldığında yeni hareket
  gönderilmez; yazılım Acil Durdur ve kontrollü durdurma akışları Arduino'ya
  idempotent `STOP` gönderir. Encoder/konum geri bildirimi eklenene kadar
  `AutonomousAimCommand` adaptör sınırında reddedilir.
- `firmware/pico/`, `usb_serial_mcu_protocol.md` ve CAN codec dosyaları legacy
  referans olarak tutulur; yeni saha özelliği bu yola eklenmez.

## Sınırlar

Arduino firmware'i mevcut saha testinde motor/LiDAR teşhisi sağlar; encoder,
ateşleme interlock'u ve heartbeat/ACK güvenlik telemetrisi henüz bu metin
protokolünde yoktur. Bu nedenle LIVE fiziksel arm kapısı, ölçülmüş interlock ve
HIL kanıtı olmadan açılamaz. Unit/SIM testleri fiziksel kabul anlamına gelmez.
