# ADR-002 — MCU ve Saha Haberleşmesi

- Durum: **ADR-006 tarafından fiziksel taşıma açısından geçersiz kılındı; tarihsel payload sözleşmesi korunuyor**
- Tarih: **25.07.2026**
- İlgili işler: `ADR-002`, `FW-001`–`FW-007`, `SAFE-002`

## Bağlam

KTR’de Raspberry Pi Pico/RP2040 seçilmiş, fakat haberleşme tablosunda CAN-FD
yazılmıştır. Mevcut malzeme/teknik notlar SN65HVD230, 500 kbit/s ve 8 bayt
çerçeveler; mevcut backend codec’i de klasik CAN kullanmaktadır. CAN-FD için
uygun denetleyici/transceiver ve daha yüksek veri fazına ihtiyaç gösteren ölçülmüş
bir gereksinim yoktur.

## Tarihsel karar

> 11.08.2026 itibarıyla fiziksel CAN kararı [`ADR-005`](005-pi-pico-usb-serial.md) ile USB CDC Serial olarak değiştirilmiştir. Aşağıdaki içerik CAN dönemi ve korunmuş v1 payload kimlikleri için tutulur.


### MCU

- Tek düşük seviye kontrolcü: **Raspberry Pi Pico / RP2040**.
- Arduino ayrı bir kontrolcü veya firmware hedefi değildir.
- Firmware: Pico SDK, C/C++.
- Pico; pan/tilt darbesi, enkoder, watchdog, Acil Durdur girişi ve ateş hattı
  izninin düşük seviye sahibidir.

### Tarihsel fiziksel hat

- **Klasik CAN 2.0B**, ISO 11898-2, 11-bit standard ID.
- Bitrate: **500 kbit/s**.
- Planlanan transceiver: **SN65HVD230**, 3,3 V mantık seviyesi.
- Hat iki uçtan 120 Ω sonlandırılır; kesin kablo/konnektör/izolasyon elektronik
  kabulünde kaydedilir.
- CAN-FD kullanılmaz. Yeni bant genişliği ihtiyacı ölçülürse denetleyici,
  transceiver ve ICD birlikte değiştirilmeden CAN-FD etiketi kullanılamaz.

### ICD v0 — tarihsel host/simülatör sözleşmesi

Tüm çok baytlı sayılar big-endian, açı ve hız birimi `0.01°`’dir.

| CAN ID | Yön | Uzunluk | İçerik |
| --- | --- | ---: | --- |
| `0x100` | RPi → Pico | 8 | pan `int16`, tilt `int16`, rate `uint16`, deadman flags, XOR8 |
| `0x101` | RPi → Pico | 8 | fire, stage, reserved, XOR8 |
| `0x102` | RPi → Pico | 8 | arm/disarm, reserved, XOR8 |
| `0x200` | Pico → RPi | 8 | pan, tilt, estop/motion/fire flags, error, reserved, XOR8 |
| `0x201` | Pico → RPi | 1 | Acil Durdur aktif/pasif olayı |

Bu tablo mevcut backend ve simülatörün test edilen sözleşmesidir. Sequence,
command ID, ACK/NACK ve protokol sürümü henüz v0’da yoktur; `FW-004` bunları
geriye uyumsuzluğu açıkça yöneten [`docs/can_icd_v1.md`](../can_icd_v1.md) sözleşmesinde tamamlanmıştır. v0 fiziksel LIVE
release için yeterli kabul edilmez ve yeni LIVE adapter yolu v1 ACK bekler.

### Hata davranışı

- Geçersiz uzunluk/checksum, bilinmeyen ID ve sınır dışı komut uygulanmaz.
- `0x200` heartbeat/status yaşı 2 saniyeyi geçtiğinde backend bağlantıyı sağlıklı
  saymaz; nihai firmware timeout’u HIL ölçümüyle daha sıkılaştırılabilir.
- Bus-off, heartbeat kaybı, Pico reset, E-Stop veya encoder fault; hareket ve ateş
  iznini düşürür ve güvenli stop üretir.
- Reconnect fiziksel çıkışı kendiliğinden arm etmez.
- Bu bölüm yalnız tarihsel CAN davranışını kaydeder. Aktif SIM/HIL/LIVE taşıma
  kuralları ve fail-closed kapıları ADR-005 ile `config/runtime/` profillerindedir.

## Reddedilen seçenekler

- **Arduino + ayrı Pico:** Gereksiz ikinci firmware ve protokol yüzeyi.
- **CAN-FD:** Mevcut 8 bayt kontrol trafiği için ölçülmüş gerekçe yok; KTR’deki
  ifade mevcut transceiver/codec ile uyumlu değil.
- **Motorları doğrudan Raspberry Pi’dan sürmek:** Linux gerçek zamanlı emniyet
  ve watchdog sahibi olmamalı.

## Kaynaklar

- [`backend/src/gokkalkan_backend/hardware_adapter.py`](../../backend/src/gokkalkan_backend/hardware_adapter.py)
- [`reports/Gökkalkan Kritik Tasarım Raporu.pdf`](../../reports/Gökkalkan%20Kritik%20Tasarım%20Raporu.pdf), §4.2.1.
- [`docs/tech_stack.md`](../tech_stack.md).
