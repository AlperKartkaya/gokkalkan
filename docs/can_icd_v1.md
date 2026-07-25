# Gökkalkan CAN Arayüz Kontrol Dokümanı — v1

**Durum:** Host/simülatör sözleşmesi uygulanmış; Pico kartı ve fiziksel CAN hattı üzerindeki kabul testi imalat sonrasına aittir.

## Fiziksel katman

- Classical CAN 2.0B, 11-bit identifier, 500 kbit/s; bütün v1 mesajları 8 bayttır.
- Çok baytlı sayılar big-endian, açılar `int16` centidegree (`0,01°`) ölçeğindedir.
- Bayt 0 protokol sürümü (`0x01`), bayt 1 modulo-256 sequence alanıdır.
- Bayt 7 CRC-8/ATM (`poly=0x07`, `init=0x00`, bayt 0–6) alanıdır.
- Bozuk CRC, bilinmeyen sürüm, duplicate veya out-of-order paket uygulatılmadan reddedilir. Yeni sequence farkı modulo-256 aralıkta `1..127` olmalıdır.

## Mesaj tablosu

| CAN ID | Yön | Ad | Bayt 2–6 |
|---|---|---|---|
| `0x10F` | Pi→Pico | COMMAND_META | command-tag `u16`, kind, flags, reserved |
| `0x110` | Pi→Pico | PAN_TILT | pan `i16`, tilt `i16`, reserved |
| `0x111` | Pi→Pico | FIRE | active, stage, reserved ×3 |
| `0x112` | Pi→Pico | SYSTEM | operation (`0` disarm, `1` arm, `2` stop, `3` reset), reserved |
| `0x200` | Pico→Pi | STATUS | state, flags, fault, encoder flags, FW major |
| `0x201` | Pico→Pi | E-STOP | active, reason, reserved |
| `0x202` | Pico→Pi | FIRMWARE | major, minor, patch, protocol, reserved |
| `0x203` | Pico→Pi | ENCODER | pan `i16`, tilt `i16`, flags |
| `0x204` | Pico→Pi | FAULT | fault, detail, reserved |
| `0x210` | Pico→Pi | ACK/NACK | command-tag `u16`, result, state, reserved |

`COMMAND_META` ve payload aynı sequence değerini taşır. Command tag, backend command ID’sinin BLAKE2s-16 özetidir. Backend fiziksel LIVE komutunu başarılı saymak için 250 ms içinde aynı sequence ve command tag ile `ACK` almak zorundadır.

## Durumlar, bitler ve zaman aşımı

State: `0 BOOT`, `1 SAFE`, `2 READY`, `3 ARMED`, `4 FIRING`, `5 FAULT`.

STATUS flags: bit0 E-Stop, bit1 motion-ok, bit2 fire-ready, bit3 watchdog-ok. ENCODER flags: bit0 zero-reference, bit1 direction-ok, bit2 connected, bit3 overflow, bit4 expected/actual deviation fault. ACK result: `0 ACK`, `1 NACK_STATE`, `2 NACK_CRC`, `3 NACK_SEQUENCE`, `4 NACK_COMMAND`.

Pico, 250 ms heartbeat kaybında actuator çıkışlarını kapatıp `FAULT` durumuna geçer. E-Stop, encoder kopması/overflow/ters yön/sapma ve bozuk komut hiçbir motor veya imha çıkışını etkinleştiremez. Reset yalnız fiziksel E-Stop bırakılmışken `SAFE` durumuna geçebilir; yeniden arm için yeni operatör hold zinciri gerekir.

Referans codec: `backend/src/gokkalkan_backend/can_protocol.py`. Firmware karşılığı: `firmware/pico/include/can_protocol.hpp`.
