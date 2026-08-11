# Pi–Pico USB seri taşıma sözleşmesi v1

- Fiziksel hat: Raspberry Pi 5 USB-A host → kısa veri destekli kablo → Pico Micro-USB device.
- Cihaz sınıfı: USB CDC serial.
- Linux cihaz seçimi: yalnız kararlı `/dev/serial/by-id/...` yolu; `ttyACM0` sabit kabul edilmez.
- Varsayılan seri ayarı: 115200 baud. USB CDC hız alanı fiziksel USB hızını belirlemez; konfigürasyon/teşhis sözleşmesidir.

## Çerçeve

USB bir byte stream olduğu için her mesaj şu şekilde taşınır:

```text
COBS(version:u8 | message_id:u16 | length:u8 | payload | CRC16-CCITT) | 0x00
```

- `version`: `1`
- `message_id`: tarihsel CAN v1 ICD'deki 11-bit mesaj kimliği
- `length`: 0–64 byte
- `CRC16-CCITT`: poly `0x1021`, init `0xFFFF`
- Bozuk, fazla uzun, eksik veya bilinmeyen çerçeve uygulanmadan reddedilir.

Komut/status payload'ları `docs/can_icd_v1.md` v1 semantiğini korur. CAN fiziksel katmanı kullanılmaz; belge yalnız payload kimlikleri ve geriye dönük test vektörleri için tarihsel kaynaktır.

## Ek USB mesajı

| Kimlik | Yön | İçerik |
|---|---|---|
| `0x120` | Pi → Pico | 8-byte CRC-8 korumalı heartbeat |

Pi 100 ms aralıkla heartbeat gönderir. Pico 250 ms boyunca geçerli heartbeat görmezse `FAULT` durumuna geçer; hareket ve ateş çıkışlarını kapatır. USB kopması, Pico reseti veya yeniden enumeration otomatik arm üretmez.

## Yetkilendirme

- Her komut `COMMAND_META` + payload ve eşleşen sequence ile gönderilir.
- Backend 250 ms içinde aynı sequence ve command-tag ile ACK almazsa komutu başarısız sayar.
- Yeniden bağlanan MCU `SAFE` kabul edilir; manuel reset/arm zinciri yeniden tamamlanır.
- USB, emniyet rölesi değildir. E-Stop → 3SK1111 → LP1K1201BD fiziksel zinciri USB ve Linux'tan bağımsızdır.
- Fiziksel HIL monitor-only modunda yalnız heartbeat gönderilir; hareket, arm ve
  ateş komutları engellenir. Komut/ACK testi `loop://` veya aktüatörlerden
  fiziksel olarak ayrılmış özel güvenli-yük prosedürüyle yapılır.
