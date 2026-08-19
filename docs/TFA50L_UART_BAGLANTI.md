# TFA50-L UART ve besleme bağlantısı

Bu not, **Benewake TFA50-L** veri sayfasındaki beş telli kabloyu Raspberry Pi
tarafında teşhis etmek içindir. Fiziksel çıkış/atış yetkisi vermez.

Kaynak: [Benewake TFA50-L veri sayfası](https://www.e-kom.com/Datasheet/Benewake/TFA50-L_Datasheet.pdf)
ve [Raspberry Pi UART yapılandırma dokümantasyonu](https://www.raspberrypi.com/documentation/computers/configuration.html).

## Doğrulanmış kablo eşlemesi

| TFA50-L tel | Veri sayfası işlevi | Bağlantı |
| --- | --- | --- |
| Kırmızı | 9–36 V DC besleme | Pi'ye **bağlanmaz**. Sigortalı haricî 9–36 V kaynağın `+` ucuna bağlanır. |
| Siyah | GND | Haricî kaynağın `0 V` dönüşüne bağlanır. |
| Sarı | GND | Pi UART'ın ortak referansı için sistem `0 V` ile ortaklanır; Pi fiziksel **pin 6** gibi gerçek bir GND pinine bağlanır. |
| Yeşil | LiDAR TX | Seviye güvenli UART üzerinden Pi RX: fiziksel **pin 10 / GPIO15**. |
| Mavi | LiDAR RX | Seviye güvenli UART üzerinden Pi TX: fiziksel **pin 8 / GPIO14**. |

Siyah ve sarı tel veri sayfasında ayrı GND olarak tanımlıdır. Haricî güç kaynağı
ve Pi UART iletişimi için ortak `0 V` referansı gerekir. Tüm kabloları söküp
enerjiyi kestikten sonra bağlayın.

> **Kesinlikle kullanmayın:** Pi fiziksel **pin 3**, I²C SDA (`GPIO2`) pinidir;
> TFA50-L GND veya besleme pini değildir. Pi'nin 5 V pini de TFA50-L'nin
> gerektirdiği 9–36 V besleme yerine geçmez.

TFA50-L veri sayfası UART lojik seviyesi için bu bağlantıda bir seviye değeri
vermez. Bu nedenle Pi GPIO'suna doğrudan bağlamak yerine 3,3 V-uyumlu USB-UART
ya da doğrulanmış seviye dönüştürücü kullanın. Doğrudan GPIO ancak ölçülmüş ve
3,3 V-uyumlu olduğu doğrulandıktan sonra kullanılabilir.

## Raspberry Pi 5 UART seçimi

Pi 5'te `/dev/serial0`, varsayılan olarak üç pinli **debug header** üzerindeki
`ttyAMA10`'dur; 40 pinli GPIO header üzerindeki pin 8/10 değildir. Pin 8/10'u
UART0 olarak açmak için `/boot/firmware/config.txt` dosyasına aşağıdaki satır
eklenmelidir:

```ini
dtoverlay=uart0-pi5
```

Bu, açılışta uygulanan Device Tree ayarıdır; ekledikten sonra **Pi yeniden
başlatılmalıdır**. Yeniden başladıktan sonra GPIO header UART cihazı
`/dev/ttyAMA0` olarak doğrulanır. Bu proje profilindeki LiDAR yolu bu nedenle
`/dev/ttyAMA0` yapılmıştır; `/dev/serial0` kullanılmamalıdır.

## Güvenli ilk teşhis

TFA50-L varsayılanı `460800 8N1` ve her ölçüm çerçevesi 4 bayttır. Güç,
topraklama ve TX/RX eşlemesi yapıldıktan sonra Pi'de yalnızca alıcı çalışan şu
komutu kullanın:

```bash
sudo -u gokkalkan /opt/gokkalkan/.venv/bin/gokkalkan lidar probe \
  --port /dev/ttyAMA0 --baud-rate 460800 --timeout-sec 3
```

Bu komut LiDAR'a UART komutu yazmaz, fiziksel çıkışları açmaz ve yalnız gelen
ölçüm çerçevelerini çözer. Başarılı sonuçta `"ok": true`, en az bir geçerli
çerçeve ve `lastMeasurement.distanceM` görünür. Başarısızsa cihazı yeniden
başlatmak yerine önce beslemeyi (9–36 V), ortak GND'yi, yeşil/mavi çaprazını ve
UART lojik seviyesini doğrulayın.

Başarılı probe, LiDAR menzilinin füzyon veya atış için kabul edildiği anlamına
gelmez. Bunun için seri numarası/firmware, montaj revizyonu ve 5/10/15 m
kalibrasyon kanıtı ayrıca yapılandırılmalıdır.

Bu kanıtlar tamamlanana kadar `/etc/gokkalkan/runtime.toml` içindeki aşağıdaki
ayar `false` kalmalıdır:

```toml
lidar_input_enabled = false
```

Onaylanmış kimlik, montaj ve kalibrasyon girildikten sonra yalnız LiDAR
girdisini SIM/HIL profilde başlatmak için `true` yapılabilir. Bu bayrak fiziksel
çıkışları etkinleştirmez; `live_output_enabled` ayrı ve kapalı kalır.
