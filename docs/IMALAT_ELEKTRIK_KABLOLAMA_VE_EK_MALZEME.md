# Gökkalkan İmalat Elektrik, Kablolama ve Ek Malzeme Kılavuzu

> **Hedef kitle:** Elektrik/elektronik ve mekanik imalat ekibi  
> **Kaynaklar:** `docs/MALZEME_LISTESI.md`, `docs/can_icd_v1.md`, `docs/adr/002-mcu-can.md`, `docs/adr/003-camera-lidar.md`, `docs/tech_stack.md` ve `docs/sartname_v4.txt`  
> **Durum:** Tasarım ve masaüstü/SIM doğrulama kılavuzu. Nihai kablo kesiti, sigorta, pin numarası ve konnektör seçimi fiziksel ürün etiketi/veri sayfası ile imalat sorumlusu tarafından onaylanmadan enerji verilmez.

## 1. Güvenlik sınırı

Bu sistem 220 VAC şebeke, güçlü step motorlar, Li-ion batarya ve airsoft tabanlı hedef-imha mekanizması içerir. Aşağıdaki kurallar zorunludur:

1. Şebeke ve yüksek akım kablolaması yalnız yetkin elektrik/elektronik personeli tarafından yapılır.
2. Lehimleme ve süreklilik testleri **tüm enerji kaynakları ayrılmışken** yapılır. Airsoft bataryası, şebeke fişi ve kondansatörlü güç kaynakları aynı anda sistemden ayrılır.
3. Acil Durdur yalnız yazılıma bağlanmaz. İki kanallı güvenlik zinciri ana kontaktör üzerinden motor ve imha enerjisini fiziksel olarak keser; Pico/Raspberry Pi yalnız yardımcı kontağı izler.
4. Mevcut BOM’daki YL-314-C-T bir otomotiv rölesidir; güvenlik rölesi değildir ve Acil Durdur güvenlik fonksiyonunda kullanılmaz.
5. Airsoft tüfeğin akü/motor güç hattı kesilmez, ETU/gearbox korumaları baypas edilmez ve tüfek içinde doğrudan yüksek akım lehimi yapılmaz. Uzaktan komut yalnız stok tetik girişine paralel, galvanik izole, normalde açık bir **kuru kontak** üzerinden verilir.
6. İlk enerji verme airsoft tüfek ve BB olmadan; ikinci doğrulama yalnız direnç/lamba gibi yapay yükle; son HIL testi boş şarjör ve güvenli saha prosedürüyle yapılır.
7. Kodun testten geçmesi fiziksel kabul değildir. Acil Durdur, kontaktör, topraklama, izolasyon, kablo ısınması, tek-atış davranışı ve yanlış hedefe ateş etmeme ayrı kabul kalemleridir.

## 2. Sistem bağlantı özeti

```text
220 VAC saha beslemesi
  │
  ├─ Kaçak akım + ana sigorta/şalter + PE barası
  │
  └─ İki kanallı Acil Durdur güvenlik rölesi
       │
       └─ 24 VDC bobinli ana kontaktör
            │
            └─ Mean Well RSP-500-24 (24 VDC bara)
                 ├─ Sigorta F1/F2 → DM542 #1/#2 → NEMA23 pan/tilt
                 ├─ Sigorta F3 → 24→5 V DC-DC → Raspberry Pi 5
                 ├─ Sigorta F4 → 24→5 V DC-DC → Pico + CAN mantığı
                 ├─ Sigorta F5 → 24 V fanlar
                 └─ Ayrı yardımcı dal → röle/arayüz ve kontaktör bobini

Raspberry Pi 5 ─SPI/USB─ CAN arabirimi ══ 120 Ω bükümlü çift ══ Pico CAN arabirimi
     │                                                            │
     ├─ CSI → Camera Module 3                                     ├─ STEP/DIR/ENA sürücü katı → DM542
     ├─ PCIe → AI HAT+                                            ├─ Enkoder giriş/izolasyon katı
     └─ UART → TFA50-L                                            ├─ E-Stop yardımcı kontak izleme
                                                                  └─ İzole kuru kontak rölesi → airsoft stok tetik girişi

Airsoft 7,4 V batarya → stok T-Plug → stok ETU/gearbox/motor
                                      (24 VDC bara ile birleştirilmez)
```

## 3. Ek satın alma listesi

Bağlantılar örnek tedarik/arama bağlantılarıdır. Satın almada aynı elektriksel sınıfta, tercihen endüstriyel ve belgeli eşdeğer ürün seçilebilir.

| Öncelik | Ek malzeme | Önerilen miktar | Asgari özellik / seçim gerekçesi | Örnek tedarik bağlantısı |
|---|---|---:|---|---|
| Kritik | İki kanallı güvenlik rölesi | 1 | 24 VDC, iki kanal E-Stop, reset ve kontaktör geri-besleme (EDM) destekli; YL-314 yerine | [Schneider Preventa XPS araması](https://www.se.com/tr/tr/search/?q=XPS%20safety%20relay) |
| Kritik | Çift NC kontaklı, kilitlemeli Acil Durdur butonu | 1 | İki bağımsız NC kanal; mevcut tek NC olduğu doğrulanırsa değiştirilir | [Schneider Harmony Acil Durdur araması](https://www.se.com/tr/tr/search/?q=emergency%20stop%202NC) |
| Kritik | Ana kaçak akım koruması + 2 kutuplu otomatik sigorta | 1 set | Saha panosuna ve yük hesabına uygun; değer elektrik sorumlusu tarafından seçilir | [Schneider Acti9 ürün ailesi](https://www.se.com/tr/tr/product-range/7559-acti9/) |
| Kritik | DIN-ray sigortalı klemens ve yedek sigortalar | 6–10 hat | Her 24 V dalını ayrı korumak; motor, Pi, Pico, fan ve yardımcı devre ayrılır | [Phoenix Contact klemens ürünleri](https://www.phoenixcontact.com/tr-tr/products/terminal-blocks) |
| Kritik | CAN arabirimi — Raspberry Pi | 1 | SocketCAN uyumlu, 3,3 V güvenli MCP2515/CAN HAT veya USB-CAN; Pi 5 ile sürücü doğrulanmalı | [Waveshare 2-CH CAN HAT](https://www.waveshare.com/2-ch-can-hat.htm) |
| Kritik | CAN arabirimi — Pico | 1 | MCP2515 + transceiver veya doğrulanmış RP2040 PIO-CAN çözümü; yalnız SN65HVD230 transceiver yeterli değildir | [MCP2515 CAN modülü araması](https://www.robotistan.com/arama?q=mcp2515) |
| Kritik | CAN kablosu | Gereken uzunluk + %20 | 120 Ω karakteristik empedanslı, bükümlü ve tercihen ekranlı 1 çift; papatya zinciri | [LAPP CAN BUS ürün sorgusu](https://www.lapp.com/tr/tr/) |
| Kritik | 120 Ω sonlandırma direnci | 2 + 2 yedek | CAN hattının yalnız iki fiziksel ucunda, %1, en az 0,25 W | [Direnc.net 120 Ω araması](https://www.direnc.net/arama?q=120%20ohm%20diren%C3%A7) |
| Kritik | İzole kuru kontak röle/PhotoMOS arayüzü | 1 + 1 yedek | Pico 3,3 V ile sürülen, normalde açık kuru kontak; yalnız stok tetik girişine paralel | [PhotoMOS röle araması](https://www.direnc.net/arama?q=photomos) |
| Kritik | Tetik rölesi geri bildirim kontağı | 1 | Zorlamalı kontaklı ara röle veya ayrı yardımcı kontak; yapışma/takılı kalma algısı | [Phoenix Contact röle modülleri](https://www.phoenixcontact.com/tr-tr/products/relay-modules) |
| Kritik | DM542 lojik sürücü katı | 2 kanal × 3 sinyal | Pico GPIO’yu PUL/DIR/ENA optik girişlerinden ayıran open-collector/line-driver; GPIO doğrudan bağlanmaz | [ULN2803A araması](https://www.direnc.net/arama?q=ULN2803A) |
| Kritik | Enkoder giriş izolasyonu/seviye çevirici | 2 | Kesin enkoder modelinin A/B/Z çıkışına uygun hızlı optokuplör veya diferansiyel receiver | [6N137 hızlı optokuplör araması](https://www.direnc.net/arama?q=6N137) |
| Kritik | 5 V dağıtım sigortaları | 2–3 | Pi ve Pico dalları ayrı; DC-DC gerçek sürekli akımına göre seçilir | [Otomotiv bıçak sigorta yuvası araması](https://www.motorobit.com/arama?q=sigorta%20yuvas%C4%B1) |
| Kritik | 3 × 1,5 mm² esnek şebeke kablosu | Gereken uzunluk | L/N/PE; yağ/ısı ve hareket koşuluna uygun H05VV-F/H07RN-F sınıfı | [Öznur 3×1,5 kablo araması](https://www.elektrikmarket.com.tr/arama?q=3x1.5%20kablo) |
| Kritik | 2 × 2,5 mm² DC güç kablosu | Gereken uzunluk | 24 V motor/güç dalları; nihai kesit akım, uzunluk ve gerilim düşümüne göre hesaplanır | [2×2,5 kablo araması](https://www.elektrikmarket.com.tr/arama?q=2x2.5%20kablo) |
| Kritik | 4 × 0,75 mm² kontrol kablosu | Gereken uzunluk | E-Stop iki kanal ve düşük akım kontrol; güç kablosundan ayrı güzergâh | [4×0,75 kontrol kablosu araması](https://www.elektrikmarket.com.tr/arama?q=4x0.75%20kontrol%20kablosu) |
| Gerekli | 2 × 0,22–0,34 mm² bükümlü sinyal kablosu | Gereken uzunluk | STEP/DIR, UART ve düşük seviye sinyaller; motor kablosundan ayrı | [LIYCY sinyal kablosu araması](https://www.elektrikmarket.com.tr/arama?q=LIYCY%20kablo) |
| Gerekli | Kablo yüksüğü seti | 1 set | 0,25–2,5 mm² izoleli ferrül; vidalı klemense çıplak çok telli kablo sokulmaz | [Kablo yüksüğü araması](https://www.direnc.net/arama?q=kablo%20y%C3%BCks%C3%BC%C4%9F%C3%BC) |
| Gerekli | Ratchet ferrül/faston krimp pensesi | 1 | Ferrül ve faston için uygun kalıp; pense ile ezme/lehimleme yapılmaz | [Krimp pensesi araması](https://www.direnc.net/arama?q=krimp%20pensesi) |
| Gerekli | 6,3 mm erkek faston + izole kılıf | 1 set | BOM’daki dişi fastonların eşleri; kablo kesitine uygun renk/sınıf | [Erkek faston araması](https://www.direnc.net/arama?q=6.3mm%20erkek%20faston) |
| Gerekli | T-Plug erkek/dişi konnektör ve silikon kablo | 2 çift | Airsoft batarya hattında anahtarlanmış/korumalı sökülebilir bağlantı; polarite işaretli | [T-Plug araması](https://www.robotistan.com/arama?q=t-plug) |
| Gerekli | JST-GH/JST-XH konnektör seti | 1 set | TFA50-L/enkoder/yardımcı sensörler için kilitli, anahtarlı düşük akım bağlantı | [JST konnektör araması](https://www.robotistan.com/arama?q=jst%20konnekt%C3%B6r) |
| Gerekli | Isı büzüşmeli makaron | 1 set | Her lehim ekinde çift katman; kablo kimliği için renk/kod | [Makaron araması](https://www.robotistan.com/arama?q=makaron) |
| Gerekli | Kablo rakoru, spiral/kablo kanalı ve örgü kılıf | Set | Çekme emniyeti, keskin kenar ve hareketli eksen koruması | [Kablo rakoru araması](https://www.elektrikmarket.com.tr/arama?q=kablo%20rakoru) |
| Gerekli | DIN ray, PE/N/24V/0V klemensleri ve köprüler | Pano ölçüsüne göre | Yıldız dağıtım, numaralandırma ve sökülebilir bakım | [Phoenix Contact klemens araması](https://www.phoenixcontact.com/tr-tr/products/terminal-blocks) |
| Gerekli | Kablo etiketi ve numaratör | 1 set | Aşağıdaki tel numaralarının her iki uçta kalıcı işaretlenmesi | [Kablo etiketi araması](https://www.elektrikmarket.com.tr/arama?q=kablo%20etiketi) |
| Gerekli | Lehim sarfı | 1 set | Ayarlı havya, elektronik lehim teli, flux, lehim fitili, izopropil alkol | [Robotistan lehim araması](https://www.robotistan.com/arama?q=lehim) |
| Gerekli | Multimetre + pens ampermetre | 1’er | Enerjisiz süreklilik/izolasyon ve ilk enerjide dal akımı ölçümü | [Ölçü aletleri](https://www.direnc.net/olcum-aletleri) |
| Önerilen | TVS diyot ve sigortalı dağıtım kartı | Dal başına | 24 V transient ve ters bağlantı koruması; değeri devre mühendisi seçer | [TVS diyot araması](https://www.direnc.net/arama?q=TVS%20diyot) |

## 4. Kesinleştirilmesi gereken mevcut BOM sorunları

| Konu | Mevcut durum | İmalattan önce karar |
|---|---|---|
| Enkoder | Excel `Fenac F50-1024`; bağlantı Omron E6B2-CWZ6C 1000 P/R | Fiziksel etiketi fotoğraflayıp besleme, A/B/Z çıkış tipi, P/R ve pin renklerini kesinleştir |
| Emniyet rölesi | YL-314-C-T 24 V/40 A otomotiv rölesi | Güvenlik zincirinden çıkar; sertifikalı iki kanallı güvenlik rölesi satın al |
| Kontaktör | LP1K1210BD, 24 VDC bobin | Kesilecek yükün DC/AC türü ve akımına göre kontak uygunluğunu onayla; EDM yardımcı kontağını güvenlik rölesine bağla |
| CAN | SN65HVD230 transceiver listelenmiş fakat sipariş verilmeyecek | Pi ve Pico için CAN controller + transceiver topolojisini kesinleştir; yalnız transceiver CAN üretmez |
| Pico firmware | Güvenlik çekirdeği ve protokol testleri var; kart pin haritası/CAN sürücüsü yok | Revizyonlu şema ve pin tablosu onaylanmadan fiziksel çıktı derlenmez |
| Airsoft tetik | APS PER701, SDU 2.0 ETU | Stok tetik kontak uçları üretici/servis tarafından tespit edilir; motor/batarya hattı baypas edilmez |
| Batarya/şarj | 7,4 V Li-ion batarya; ürün adı LiPo şarj cihazı | Hücre kimyası, 2S balans soketi ve 4,2 V/hücre profili belgelenmeden şarj edilmez |
| Rulman | 6205-ZZ “eksenel” yazılmış | Mekanik yük hesabına göre radyal/eksenel yatak seçimini düzelt |

## 5. Kablo ve tel numarası planı

| Tel no | Başlangıç → bitiş | Kablo | Renk önerisi | Koruma / not |
|---|---|---|---|---|
| AC-L01 | Şebeke giriş L → ana şalter/RCD → kontaktör → RSP-500 L | 1,5 mm² | Kahverengi | Değerleri pano sorumlusu seçer |
| AC-N01 | Şebeke giriş N → RCD → RSP-500 N | 1,5 mm² | Mavi | N, DC 0 V ile birleştirilmez |
| PE-01 | Şebeke PE → PE barası → PSU/kabin/metal şase | 1,5 mm² min. | Sarı-yeşil | Boya kazınmış yıldız rondelalı gövde noktası |
| ES-11/12 | E-Stop NC kanal 1 → güvenlik rölesi CH1 | 0,75 mm² | Kırmızı çift | Ayrı kanal, kısa devre izlemeli |
| ES-21/22 | E-Stop NC kanal 2 → güvenlik rölesi CH2 | 0,75 mm² | Kırmızı çift | CH1 ile köprülenmez |
| EDM-01 | Kontaktör yardımcı NC → güvenlik rölesi EDM | 0,75 mm² | Turuncu | Kaynaklanmış kontaktör algısı |
| 24P-M1/24N-M1 | 24 V bara → F1 → DM542 pan | 2,5 mm² | Kırmızı/siyah | Ayrı sigorta |
| 24P-M2/24N-M2 | 24 V bara → F2 → DM542 tilt | 2,5 mm² | Kırmızı/siyah | Ayrı sigorta |
| 24P-5V/24N-5V | 24 V bara → F3/F4 → DC-DC girişleri | 1–1,5 mm² | Kırmızı/siyah | Pi ve Pico ayrı çıkış/dal |
| 5P-PI/5N-PI | 5 V DC-DC → Pi 5 güç girişi | 1–1,5 mm² kısa hat | Kırmızı/siyah | Yük altında Pi ucunda gerilim ölç |
| 5P-MCU/5N-MCU | 5 V DC-DC → Pico/CAN mantığı | 0,5–0,75 mm² | Kırmızı/siyah | Pico 3V3 pinine 5 V verilmez |
| CAN-H/CAN-L | Pi CAN → Pico CAN | 120 Ω bükümlü çift | Beyaz/mavi | Yalnız iki uçta 120 Ω |
| CAN-SH | Kablo ekranı → pano PE | Ekran/drain | Çıplak/şeffaf | Tek noktadan, pano tarafında |
| PT-PUL/DIR/ENA | Pico sürücü kartı → DM542 #1/#2 | 0,22–0,34 mm² | Numaralı | Her sinyal dönüşüyle bükümlü |
| ENC-A/B/Z | Enkoder → izolasyon → Pico | Ekranlı 4–6 damarlı | Numaralı | Kesin modele göre pinlenir |
| LID-TX/RX/GND | TFA50-L → Pi UART | Kilitli 3/4 damar | Numaralı | TX↔RX çapraz; lojik seviye doğrula |
| FIRE-COM/NO | İzole kuru kontak → stok tetik iki ucu | 0,22–0,34 mm² | Mor çift | Batarya/motor akımı taşımaz |
| FIRE-FB | Röle yardımcı kontak → Pico giriş | 0,22–0,34 mm² | Gri | Takılı röle/tetik geri bildirimi |

## 6. Alt sistem bağlantıları

### 6.1 Şebeke, koruyucu toprak ve 24 V dağıtım

1. IEC/fiş girişindeki L ve N önce iki kutuplu ana şalter/koruma üzerinden geçirilir.
2. E-Stop güvenlik rölesinin güvenli çıkışı LP1K1210BD kontaktör bobinini sürer. Yazılım kontaktörü doğrudan enerjileyemez.
3. Kontaktör ana kontağı, tehlikeli hareket/imha enerjisini kesen tarafta konumlandırılır. Raspberry Pi'nin kontrollü kapanması gerekiyorsa bilgisayar beslemesi ayrı “kontrol gücü” dalında tutulabilir; bu karar risk analizine yazılır.
4. PE kablosu önce PE barasına, oradan yıldız topolojiyle RSP-500 kasasına, metal elektrik panosuna ve metal şaseye gider.
5. RSP-500 `V+`/`V-` çıkışları doğrudan çoklu kablo altında sıkıştırılmaz; DIN klemens/sigortalı dağıtım üzerinden dallanır.
6. Her dal ilk enerjide laboratuvar kaynağı veya akım sınırlayıcı ile denenir; boşta gerilim ve yükte gerilim düşümü kaydedilir.

### 6.2 Raspberry Pi 5, AI HAT+ ve Camera Module 3

1. AI HAT+ Raspberry Pi 5 PCIe FFC kablosu ve mekanik standoff'larla üretici yönüne göre takılır.
2. Camera Module 3, Pi 5'in 22-pin CAM/DISP portuna uygun 22-pin→15-pin kamera kablosuyla bağlanır. FFC kilidi açıkken kablo takılır; mavi takviye yüzünün yönü Pi/kamera kılavuzuna göre kontrol edilir.
3. Kamera ve PCIe FFC kablolarında lehim yapılmaz, uzatma/ek yapılmaz.
4. 5 V regülatörün gerçek 5 A sürekli kapasitesi doğrulanmadan Pi 5 bu hatta bağlanmaz. İlk açılışta Pi tarafında düşük gerilim uyarısı ve regülatör sıcaklığı izlenir.

### 6.3 CAN hattı

1. Topoloji yıldız değil, tek omurga/papatya zinciridir: Pi CAN → Pico CAN. Başka düğüm eklenecekse kısa stub kullanılır.
2. Omurganın iki fiziksel ucuna birer 120 Ω direnç bağlanır. Enerjisizken CAN-H ile CAN-L arasında yaklaşık 60 Ω görülmelidir.
3. CAN-H/CAN-L polaritesi tüm düğümlerde aynı tutulur. Ekran tek noktadan PE'ye bağlanır.
4. Pi tarafı SocketCAN uyumlu CAN controller gerektirir. Pico tarafı da controller + transceiver gerektirir; SN65HVD230 yalnız fiziksel katmandır.
5. CAN ve enkoder kabloları motor faz kablolarından en az birkaç santimetre ayrılır; kesişme gerekiyorsa 90° yapılır.

### 6.4 DM542 ve NEMA23 motorlar

1. Her NEMA23 motorun iki bobin çifti ohmmetreyle bulunur; bobinler arası sonsuz/çok yüksek direnç görülmelidir.
2. Bobin A uçları `A+/A-`, bobin B uçları `B+/B-` terminallerine bağlanır. Motor enerjiliyken faz kablosu sökülmez.
3. DM542 `VDC+/VDC-` girişleri kendi sigortalı 24 V dalına bağlanır.
4. Pico GPIO, `PUL/DIR/ENA` uçlarına doğrudan bağlanmaz. Open-collector/izole sürücü katı kullanılır; common-anode veya common-cathode düzeni DM542 veri sayfasına göre tek tip seçilip şemada belirtilir.
5. DIP akım ayarı motor etiketindeki faz akımına göre; mikro-adım ayarı çözünürlük/hız testine göre yapılır. Bilinmeyen akımda en düşük güvenli ayarla başlanır.
6. Pan/tilt limit mikro switch'leri normalde kapalı bağlanır; kablo kopması limit/fault üretmelidir.

### 6.5 Enkoderler

1. Fiziksel model kesinleşmeden renk koduna güvenilmez. Üretici pin şeması ile V+, 0 V, A, B ve varsa Z bulunur.
2. 5/12/24 V enkoder çıkışı Pico GPIO'ya doğrudan verilmez. NPN/PNP, push-pull veya line-driver tipine uygun hızlı izolasyon/receiver kullanılır.
3. Ekranlı kablonun ekranı pano tarafında tek noktadan PE'ye alınır; sinyal 0 V'si PE yerine doğru mantık referansına bağlanır.
4. Yazılımda zero, yön, overflow ve sapma fault'ları görülmeden `encoderOk=true` kabul edilmez.

### 6.6 TFA50-L

1. Sensörün satın alınan varyantına ait pin dizilimi ve UART lojik seviyesi üretici dokümanından doğrulanır.
2. Sensör TX → Pi RX, sensör RX → Pi TX ve GND → sinyal GND bağlanır; besleme ayrı sigortalı/filtreli daldan gelir.
3. Pi UART 3,3 V toleranslıdır; sensör çıkışı daha yüksekse uygun seviye çevirici kullanılır.
4. Motor kablosundan uzak, kilitli konnektörlü kablo kullanılır. Mesafe geçerlilik biti/timeout backend Safety Gate'i fail-closed tutmalıdır.

### 6.7 Airsoft APS PER701 entegrasyonu

Airsoft platformu 7,4 V T-Plug batarya, stok SDU 2.0 ETU/eSilver Edge gearbox ve kendi motor hattıyla korunur. 24 V sistem barası airsoft batarya hattına bağlanmaz.

```text
Pico FIRE_OUT (3,3 V logic)
  → transistor/PhotoMOS sürücü
  → galvanik izole NO kuru kontak
  → stok tetik switch'inin iki düşük-akım kontak ucuna paralel

İzole röle yardımcı NC/feedback
  → Pico FIRE_FEEDBACK girişi

Fiziksel güvenlik rölesi/kontaktör
  → airsoft bataryasını veya onaylı arm hattını sistem E-Stop'ta fiziksel ayırır
```

Uygulama sırası:

1. Tüfek boş, batarya ayrılmış ve şarjör çıkarılmış durumda servis dokümanına göre tetik switch'inin iki **düşük akım** ucu yetkin teknisyen tarafından belirlenir.
2. Stok kablo kesilmez. Sökülebilir, polaritesiz iki pinli servis konnektörü üzerinden iki paralel algılama/komut teli çıkarılır.
3. Bu iki tel yalnız normalde açık kuru kontağa gider. Pico, ETU, batarya ve motor arasında galvanik elektrik bağlantısı kurulmaz.
4. Kuru kontak “kapalı” süresi firmware tarafından en fazla 120 ms tutulur. SDU 2.0 fiziksel seçim anahtarı yalnız **semi/tek atış** modunda kilitlenir.
5. Yardımcı feedback kontağı, rölenin enerjisiz/serbest konumunu Pico'ya bildirir. Komut öncesi serbest değilse veya atış sırasında takılı kalırsa firmware `TRIGGER_FEEDBACK_STUCK` fault üretip çıkışı keser.
6. Acil Durdur, yazılımdan bağımsız olarak röle/airsoft arm enerjisini keser. E-Stop bırakılınca sistem kendiliğinden yeniden arm olmaz; kontrollü reset ve yeniden hold-to-arm gerekir.
7. İlk test kuru kontaktaki multimetre ile; ikinci test tüfek yerine LED/lamba yapay yükle; üçüncü test boş şarjörle yapılır. BB ile test yalnız kapalı ve yetkili saha prosedüründe gerçekleştirilir.

> **Yasak bağlantılar:** Pico GPIO'dan airsoft motoruna doğrudan MOSFET sürmek; 24 V'u airsoft ETU'ya vermek; 1N4007'yi tek güvenlik katmanı saymak; YL-314 röleyi emniyet rölesi saymak; tetik kontaklarını kalıcı kısa devre etmek; stok ETU/termal/aşırı akım korumasını baypas etmek.

## 7. Lehimleme ve sonlandırma talimatı

### Lehim yapılacak yerler

- Pico/CAN prototip kartındaki pin header ve düşük akım sinyal konnektörleri.
- 120 Ω CAN sonlandırma dirençleri yalnız kart üzerinde bunun için ayrılmış noktaya; sökülebilir jumper/anahtar tercih edilir.
- PhotoMOS/izole tetik arayüzünün düşük akım PCB bağlantıları.
- T-Plug pigtail gerekiyorsa yalnız sökülebilir batarya ara kablosu üzerinde, uygun yüksek akım silikon kabloyla.
- Sensör pigtail'leri yalnız üretici konnektörü hazır kablolu değilse.

### Lehim yapılmayacak yerler

- DM542, Mean Well, kontaktör, güvenlik rölesi ve DIN klemens vidalarının altındaki çok telli kablo: ferrül krimplenir.
- Acil Durdur, faston ve güç konnektörleri: uygun krimp terminal kullanılır.
- Raspberry Pi kamera/PCIe FFC kabloları.
- Airsoft batarya hücreleri, stok ETU kartı ve motor uçları; üretici/servis dışında müdahale edilmez.
- PE/toprak bağlantısı: pabuç + yıldız rondela + mekanik sıkma yapılır, lehime güvenilmez.

### Standart lehim adımları

1. Enerjiyi ayır, multimetreyle gerilim olmadığını doğrula.
2. Kabloyu yalnız gerekli kadar soy; damarları kesme. Önceden uygun çapta makaron geçir.
3. Ucu ve pedi az miktarda flux ile ayrı ayrı kalayla. Lehim telini havya ucuna yığmak yerine birleşim noktasına besle.
4. Kabloyu mekanik olarak sabit tutup kısa sürede ısıt; lehim ek boyunca akıp parlak/konkav bir fillet oluşturmalı.
5. Soğurken oynatma. Flux kalıntısını uygun izopropil alkolle temizle.
6. Büyüteçle köprü, soğuk lehim, çatlak ve açıkta tel kontrolü yap.
7. Süreklilik ve komşu pin kısa-devre testinden sonra makaronu kapat; kabloya çekme emniyeti uygula.
8. Her iki uca tel numarası tak ve `as-built` şemaya gerçek renk/pin bilgisini işle.

### T-Plug özel notu

T-Plug lehiminde konnektörün karşı eşini ısı emici/mekanik hizalama için tak; polariteyi lehimden önce ve sonra iki kez ölç. Açıkta iletken bırakma. Batarya hücresine doğrudan lehim yapma; hazır pigtail/konnektörlü paket kullan.

## 8. Enerji vermeden önce kontrol listesi

- [ ] Excel/BOM model numaraları fiziksel etiketlerle karşılaştırıldı.
- [ ] E-Stop iki bağımsız NC kanal üzerinden güvenlik rölesine gidiyor.
- [ ] Kontaktör EDM geri bildirimi bağlı; kaynaklanmış kontak simülasyonu reset'i engelliyor.
- [ ] PE sürekliliği PSU kasası, pano ve metal şasede ölçüldü.
- [ ] L-N, L-PE ve N-PE arasında istenmeyen kısa devre yok.
- [ ] 24 V, 5 V ve airsoft 7,4 V hatları galvanik/topolojik olarak doğru ayrıldı.
- [ ] Her güç dalında ayrı ve etiketli sigorta var.
- [ ] CAN-H/CAN-L enerjisiz direnç yaklaşık 60 Ω; yıldız topoloji yok.
- [ ] Pico GPIO'larına 3,3 V üstü doğrudan sinyal gelmiyor.
- [ ] DM542 faz çiftleri ohmmetreyle belirlendi; motor enerjiliyken sökülmeyecek.
- [ ] Airsoft kuru kontak çıkışı batarya/motor hattıyla elektriksel olarak birleşmiyor.
- [ ] Airsoft fiziksel selector `SAFE` ve testler için sonra `SEMI`; otomatik mod kullanılmıyor.
- [ ] Batarya/şarj cihazı kimyası ve 2S balans bağlantısı doğrulandı.
- [ ] Kablo etiketleri ve `as-built` pin tablosu tamamlandı.

## 9. Aşamalı kabul planı

| Kapı | Kurulum | Başarı ölçütü | Henüz kanıtlamadığı şey |
|---|---|---|---|
| A — Enerjisiz | Multimetre/süreklilik | Kısa devre yok, PE ve E-Stop kanalları doğru | Gerilim/akım altında davranış |
| B — Kontrol gücü | Pi/Pico, aktüatörsüz | Boot, CAN heartbeat, status/ACK, fault telemetry | Motor/airsoft çıkışı |
| C — Yapay yük | Motor yerine uygun test yükü, airsoft yerine lamba | E-Stop ve watchdog çıkışı fiziksel kesiyor; 120 ms ateş üst sınırı | Gerçek mekanik hareket/atış |
| D — Motor HIL | Düşük hız, mekanik alan boş | Limit, yön, enkoder, sapma ve E-Stop testleri | Hedefleme doğruluğu |
| E — Airsoft boş HIL | Şarjör/BB yok, güvenli yön | Tek kuru-kontak darbesi, feedback, takılı röle fault'u | BB enerjisi/isabet |
| F — Kontrollü saha | Yetkili alan, kronograf, bariyer, gözlük | Tek atış, E-Stop ateş kesme, yanlış hedef engeli | Yarışma nihai kabulü |
| G — Yarışma provası | Gerçek kamera/LiDAR/parkur | 5/10/15 m görev ve kanıt kaydı | Hakem kabulü; ayrıca yapılır |

## 10. Yazılım/firmware eşlemesi

- Backend zinciri: `FireIntent → Safety Gate → CanMcuAdapter`.
- `CanMcuAdapter`, FIRE göndermeden önce taze Pico status, `ARMED`, `fireReady`, `encoderOk`, E-Stop pasif ve fault=0 arar.
- Pico güvenlik çekirdeği interlock açıkken ARM/FIRE'ı reddeder; ateş çıkışını 120 ms sonunda otomatik kapatır.
- E-Stop, heartbeat kaybı, enkoder fault'u, interlock kopması veya takılı feedback çıkışı anında kapatıp `FAULT` durumuna geçirir.
- Gerçek `pico_main.cpp` pin haritası ve CAN controller sürücüsü kart revizyonu onaylanana kadar fiziksel aktüatör çıkışı üretmez. Bu kasıtlı bir fail-closed imalat kapısıdır.

## 11. İmalat ekibinin dolduracağı as-built kayıt

| Revizyon | Tarih | Kart/pano revizyonu | Pico pin haritası dosyası | CAN arabirimi | Enkoder modeli | Güvenlik rölesi | Kontrol eden |
|---|---|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Her değişiklikte bu tablo, tel listesi ve fiziksel fotoğraflar birlikte sürümlenmelidir. Ölçülmemiş değer, tamamlanmış kabul veya doğrulanmış donanım gibi yazılmamalıdır.
