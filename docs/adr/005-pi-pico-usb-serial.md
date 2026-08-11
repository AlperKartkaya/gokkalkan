# ADR-005 — Pi–Pico haberleşmesinde USB CDC Serial

- Durum: **Kabul edildi; fiziksel HIL kabulü bekliyor**
- Tarih: **11.08.2026**
- Yerine geçtiği karar: `ADR-002` fiziksel CAN hattı

## Bağlam

Sistemde tek Raspberry Pi 5 ve tek Raspberry Pi Pico vardır. Pico, USB device donanımını içerir. Fiziksel CAN için Pi HAT, Pico CAN denetleyicisi/transceiver, sonlandırma ve ek kablolama gerekir. Güncel imalat kararı kısa, veri destekli USB-A → Micro-USB kablosudur.

## Karar

- Fiziksel taşıma USB CDC serial olacaktır.
- Backend `UsbSerialMcuAdapter` kullanacaktır.
- USB byte stream'i COBS, length ve CRC16 ile çerçevelenir.
- Mevcut sequence, command-tag, ACK/NACK, status, fault ve 250 ms Pico watchdog semantiği korunur.
- LIVE yalnız `/dev/serial/by-id/...` cihaz yolu, fiziksel interlock ve readiness preflight ile açılır.
- USB kopması/reconnect otomatik arm üretmez.
- Fiziksel E-Stop, Siemens 3SK1111 ve LP1K1201BD zinciri yazılımdan bağımsızdır.

## Reddedilen seçenekler

- TTL UART: diferansiyel değildir; motor/kontaktör EMI ortamında ortak toprak ve parazit riski daha yüksektir.
- RS-485: USB saha testleri başarısız olursa ilk yedek seçenektir; mevcut kısa tek-nokta hattında ek transceiver gerektirir.
- CAN: çok düğümlü saha ağı için güçlüdür; mevcut tek Pi–tek Pico topolojisinde ek donanım ve imalat yükü getirir.

## Kabul sınırı

Host Python testleri ve Pico host C++ testleri fiziksel USB, EMI, konektör, backfeed veya aktüatör kabulü değildir. Motorlar ve kontaktör çalışırken disconnect/reconnect, heartbeat kaybı ve safe-load HIL kanıtı alınmadan LIVE açılmaz.
