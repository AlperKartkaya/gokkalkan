# GKK-IO-REV-B — Arduino Uno saha pin haritası

> **Durum:** Arduino Uno + DM542 motor yolu (2026-08-26 imalat kararı).
> Bu belge Pico GPIO/USB-COBS tasarımının yerine geçer. Arduino firmware'i
> yalnız motor sürüşü ve seri teşhis komutlarını taşır; E-Stop, encoder ve FIRE
> geri bildirimi bu sürümde MCU protokolü değildir.

| Sinyal | Arduino pini | Aktif seviye | Saha bağlantısı | Durum |
|---|---:|---|---|---|
| PAN `PUL+` | D2 | Darbe | DM542 PAN PUL+ | Firmware'de aktif |
| PAN `DIR+` | D3 | HIGH=CW | DM542 PAN DIR+ | Firmware'de aktif |
| TILT `PUL+` | D4 | Darbe | DM542 TILT PUL+ | Firmware'de aktif |
| TILT `DIR+` | D5 | HIGH=CW | DM542 TILT DIR+ | Firmware'de aktif |
| DM542 `PUL-/DIR-` | GND | Ortak katot | Arduino GND ortak dönüş | İmalat şemasına göre doğrula |
| Arduino `D13` | D13 | Aktivite LED'i | Kart üzeri LED | Firmware'de aktif |
| `ESTOP_SAFE_SENSE` | — | — | Fiziksel kontaktör zinciri | Arduino'ya bağlı değil |
| `FIRE_OUT` / feedback | — | — | Ayrı, henüz tanımlı değil | Yazılımda fail-closed |
| PAN/TILT encoder | — | — | Ayrı alıcı/protokol gerekli | Yazılımda hazır değil |

## Seri protokol

- 115200 baud, satır sonu `\\n`.
- Backend'in tek sınırı `ArduinoUnoMotorAdapter`'dır.
- Desteklenen komutlar: `STEP_PAN`, `STEP_TILT`, `JOG_PAN`, `JOG_TILT`,
  `RUN_PAN`, `RUN_TILT`, `RUN`, `STOP`, `PING`, `STATUS`.
- Arduino firmware'inde `FIRE` veya `ARM` komutu yoktur; backend bu niyetleri
  COBS/CAN'a dönüştürmez ve güvenli biçimde reddeder.

## Kabul kapıları

1. D2–D5 sinyal seviyelerini DM542 bağlı değilken ölç.
2. Boot/reset anında PUL hatlarının pasif kaldığını doğrula.
3. Fiziksel E-Stop'un kontaktörü bıraktığını ve Arduino'dan bağımsız olarak
   motor enerjisini kestiğini ölç.
4. Her iki ekseni önce düşük enerji/güvenli yük ile `STEP_*` ve `STOP` komutlarıyla
   dene; yazılım testi fiziksel hareket kabulü değildir.

Bağlayıcı firmware ve pin açıklaması: `realtimetesting/arduino_uno/arduino_uno.ino`.
Runtime sınırı: `docs/adr/006-arduino-uno-motor-transport.md`.
