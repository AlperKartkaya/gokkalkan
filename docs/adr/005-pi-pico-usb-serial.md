# ADR-005 — Pi–Pico haberleşmesinde USB CDC Serial

- Durum: **Yerine geçti — ADR-006 Arduino Uno saha yolu**
- Tarih: **11.08.2026**
- Yerine geçtiği karar: `ADR-002` fiziksel CAN hattı

## Bağlam

Sistemde tek Raspberry Pi 5 ve tek Raspberry Pi Pico vardır. Pico, USB device donanımını içerir. Fiziksel CAN için Pi HAT, Pico CAN denetleyicisi/transceiver, sonlandırma ve ek kablolama gerekir. Güncel imalat kararı kısa, veri destekli USB-A → Micro-USB kablosudur.

## Karar

- Fiziksel taşıma USB CDC serial olacaktır.
- Backend `UsbSerialMcuAdapter` kullanacaktır.
- USB byte stream'i COBS, length ve CRC16 ile çerçevelenir.
- Mevcut sequence, command-tag, ACK/NACK, status, fault ve 250 ms Pico watchdog semantiği korunur.
- LIVE yalnız `/dev/serial/by-id/...` cihaz yolu, taze PC817 `ESTOP_SAFE_SENSE`, airsoft fiziksel interlock ve readiness preflight ile açılır.
- USB kopması/reconnect otomatik arm üretmez.
- Fiziksel tek NK E-Stop, LP1K1210BD kontaktör, anlık 1NA START mühürlemesi ve LA4KE1B bobin bastırma devresi yazılımdan bağımsızdır. `X` noktası 24 V girişli PC817 ile Pico'ya izole edilir.

Bu asgari emniyet mimarisi çift kanallı/SIL olarak tanımlanmaz. `ESTOP_SAFE_SENSE`, E-Stop hattının kapalı olduğunu bildirir; kontaktör ana-kutup geri bildirimi değildir. Airsoft ayrı 7,4 V T-Plug alanında, ayrı sigorta ve DC motor/inrush değeri doğrulanmış fiziksel kesme elemanıyla kalır.

## Reddedilen seçenekler

- TTL UART: diferansiyel değildir; motor/kontaktör EMI ortamında ortak toprak ve parazit riski daha yüksektir.
- RS-485: USB saha testleri başarısız olursa ilk yedek seçenektir; mevcut kısa tek-nokta hattında ek transceiver gerektirir.
- CAN: çok düğümlü saha ağı için güçlüdür; mevcut tek Pi–tek Pico topolojisinde ek donanım ve imalat yükü getirir.

## Kabul sınırı

Host Python testleri ve Pico host C++ testleri fiziksel USB, EMI, konektör, backfeed veya aktüatör kabulü değildir. Motorlar ve kontaktör çalışırken disconnect/reconnect, heartbeat kaybı ve safe-load HIL kanıtı alınmadan LIVE açılmaz.
