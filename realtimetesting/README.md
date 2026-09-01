# Gökkalkan — Arduino Uno + DM542 R1 bakım ve entegrasyon rehberi

Bu dizin, Arduino Uno ile iki DM542 sürücüsünün **kontrollü bakım/HIL öncesi
entegrasyon** araçlarını taşır. Buradaki Python araçları operatör API'sinin
yerine geçmez ve fiziksel hareket, E-Stop veya yarışma güvenlik kabulü kanıtı
sayılmaz.

> **Saha profili:** `GKK-UNO-DM542-1600PPR-R1`
> **Firmware:** [`arduino_uno/arduino_uno.ino`](arduino_uno/arduino_uno.ino)
> **Kanonik pin/kabul kaydı:**
> [`docs/hardware/GKK-IO-REV-B_PIN_MAP.md`](../docs/hardware/GKK-IO-REV-B_PIN_MAP.md)

## 1. R1 pin profili

| Sinyal | Uno pini | DM542 R1 bağlantısı |
|---|---:|---|
| PAN darbe | D2 | PAN `PUL+` |
| PAN yön | D3 | PAN `DIR+` |
| TILT darbe | D4 | TILT `PUL+` |
| TILT yön | D5 | TILT `DIR+` |
| Ortak dönüş | GND | Her iki sürücüde `PUL-` ve `DIR-` (ortak katot) |
| Tanısal LED | D13 | Kart üzeri LED |
| Enable | — | Lite R1 referansında bağlı değil |

`ENA+`/`ENA-`nin R1 referansında boş olması evrensel güvenlik kuralı değildir.
Bir sürücüde bağlanması düşünülürse üretici dokümanı, giriş devresi ve haricî
E-Stop/kontaktör davranışı enerji verilmeden önce doğrulanmalıdır. Yazılım
`STOP`u, motor enerjisini Arduino'dan bağımsız kesen fiziksel E-Stop'un yerine
geçmez.

Lite referansı 1600 pulse/revolution (`≈4,444 pulse/derece`) hedefler. DM542
DIP mikroadım ve akım ayarları sürücü/motor varyantına göre tekrar doğrulanmalı,
gerçek ayar saha konfigürasyon kaydına işlenmelidir; burada varsayım olarak
uygulanmaz.

## 2. Firmware yükleme ve profil kontrolü

1. Fiziksel güç kesikken kablo, izolasyon, ortak dönüş ve E-Stop/kontaktör
   zincirini kanonik pin haritasındaki kabul kapılarına göre inceleyin.
2. Arduino IDE'de `arduino_uno/arduino_uno.ino` dosyasını açın; kart olarak
   **Arduino Uno**, ardından doğru portu seçip yükleyin.
3. Seri monitörde `115200` baud ve `Newline` seçin. Motor komutundan önce:

   ```text
   PING
   # PONG
   PROFILE
   # PROFILE GKK-UNO-DM542-1600PPR-R1
   ```

`PONG` veya tam profil yanıtı yoksa motor komutu vermeyin. Backend ve bakım
araçları da aynı doğrulamayı zorunlu tutar.

## 3. Sınırlı seri protokol

| Komut | Sınır |
|---|---|
| `STEP_PAN <pulse> <half_period_us> <CW\|CCW>` / `STEP_TILT …` | `1..1600` pulse, `80..1_000_000 µs` |
| `RUN[_PAN\|_TILT] <sec> <speed_hz> [CW\|CCW]` | Yalnız bakım; `1..15 s`, `1..1250 Hz` |
| `JOG_PAN [half_period_us] [CW\|CCW]` / `JOG_TILT …` | Yalnız bakım; en çok `1 s` sonra firmware durdurur |
| `STOP` | Her iki PUL hattını düşük tutan idempotent duruş |
| `PING`, `PROFILE`, `STATUS` | Tanı/kimlik doğrulama |

`FIRE`, `ARM` ve otomatik hedefleme komutu yoktur. Limit dışı veya hatalı
argümanlar `ERR …` ile reddedilir. `RUN` ve JOG'u yalnız boş, erişimi sınırlandırılmış,
düşük enerjili çalışma alanında kullanın.

## 4. Python bakım araçları

Gerekli bağımlılık:

```bash
.venv/bin/python -m pip install pyserial
```

Araçlar önce R1 `PING`/`PROFILE` eşleşmesini denetler; doğrulama başarısızsa
motor komutu göndermez.

```bash
# En çok 15 saniyelik, profil denetimli PAN bakım testi
.venv/bin/python realtimetesting/test_motor_15s.py \
  --port /dev/serial/by-id/ARDUINO_CIHAZ_YOLU --motor pan --duration 15 --speed 800

# Etkileşimli süreli bakım paneli
.venv/bin/python realtimetesting/interactive_motor_control.py

# Adım bazlı WASD bakım kontrolü; JOG modu her komutta en çok 1 sn sürer
.venv/bin/python realtimetesting/wasd_motor_control.py \
  --port /dev/serial/by-id/ARDUINO_CIHAZ_YOLU
```

`test_motor_15s.py`nin zaman çubuğu yalnız komut zaman penceresidir. Motorun
hareket ettiği, doğru yönde döndüğü, konumunu koruduğu veya E-Stop'un enerjiyi
kestiği anlamına gelmez; bunlar ölçülüp kaydedilecek fiziksel kabul maddeleridir.

## 5. Saha kabul sırası

1. D2–D5'i sürücü güç katı bağlı değilken ölçün; reset/`STOP`ta PUL düşük
   kalmalıdır.
2. Haricî E-Stop'a basıldığında kontaktörün Arduino/USB'den bağımsız motor
   enerjisini kestiğini ölçün.
3. R1 profile yanıtını kaydedin; eski sketch veya başka USB cihazında durun.
4. Tek eksende küçük `STEP_*`, ardından `STOP`; gerçek yön ve mekanik limitleri
   ölçün. Sonra ikinci ekseni değerlendirin.
5. Safety Gate'in hareket yasak bölgesi ve telemetri/HIL kanıtını ayrı olarak
   doğrulayın. Ateşleme/otonom kontrol bu R1 firmware'in kapsamı dışındadır.

TFA50-L/TF-Luna/TFmini teşhis araçları bu motor profilinden bağımsızdır. LiDAR
kablolama ve kalibrasyon sonuçları ayrıca kayıt altına alınmalıdır.
