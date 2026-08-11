# Gökkalkan İmalat Elektrik, Kablolama ve Ek Malzeme Kılavuzu

> **Hedef kitle:** Elektrik/elektronik ve mekanik imalat ekibi
> **Kaynaklar:** `Gökkalkan Malzeme Listesi - Güncel Kablolama.xlsx`, `docs/MALZEME_LISTESI.md`, `docs/usb_serial_mcu_protocol.md`, `docs/adr/005-pi-pico-usb-serial.md`, `docs/adr/003-camera-lidar-placement.md`, `docs/tech_stack.md` ve `docs/sartname_v4.txt`
> **Durum:** Tasarım ve masaüstü/SIM doğrulama kılavuzu. Nihai kablo kesiti, sigorta, pin numarası ve konnektör seçimi fiziksel ürün etiketi/veri sayfası ile imalat sorumlusu tarafından onaylanmadan enerji verilmez.

> **11 Ağustos 2026 haberleşme kararı:** Yeni satın alma listesi Pi 5 ↔ Pico fiziksel hattını kısa, veri destekli USB-A → Micro-USB kablosu olarak belirler; CAN arabirimi, CAN kablosu ve sonlandırma direnci satın alınmayacaktır. Backend USB adapter, COBS+CRC16 taşıması, heartbeat/ACK ve Pico USB CDC firmware yolu uygulanmıştır; ADR-005 aktiftir. Bununla birlikte fiziksel USB/EMI/HIL kabulü yapılmadan kablo canlı aktüatör yetkisi vermez.

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
  ├─ Ayrı 24 VDC DIN kontrol güç kaynağı
  │    └─ İki kanallı Acil Durdur güvenlik rölesi
  │         └─ 24 VDC bobinli ana kontaktör
  │
  └─ Ana kontaktör güç kontağı
       └─ Mean Well RSP-500-24 (24 VDC tehlikeli-yük barası)
                 ├─ Sigorta F1/F2 → DM542 #1/#2 → NEMA23 pan/tilt
                 ├─ Sigorta F3 → 24→5 V DC-DC → Raspberry Pi 5
                 ├─ Sigorta F4 → 24→5 V DC-DC → Pico
                 ├─ Sigorta F5 → 24 V fanlar
                 └─ Ayrı yardımcı dal → röle/arayüz

Raspberry Pi 5 ── kısa, veri destekli USB-A→Micro-USB ── Raspberry Pi Pico
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
| Kritik | Siemens emniyet rölesi | 1 | 3SK1111-1AB30, 24 V AC/DC; iki kanal E-Stop, manuel reset ve EDM zinciri | [Yapı Otomasyon](https://www.yapotomasyon.com/urun/siemens-3sk1111-1ab30-standart-emniyet) |
| Kritik | İkinci kanal stop kontağı | 1 | Gwest 6102, 1NK; mevcut butona ikinci bağımsız NK kanal olarak takılır | [KRC Elektromarket](https://www.krcelektromarket.com/gwest-6102-stop-kontak-1-nk) |
| Kritik | Schneider kontaktör | 1 | LP1K1201BD, 24 VDC bobin, 3NA+1NK; emniyet rölesiyle birlikte | [Anel Elektromarket](https://anelelektromarket.com/schneider-lp1k1201bd-55-kw-3na1nk-24-vdc-kontaktor) |
| Kritik | Manuel reset butonu | 1 | Anlık basmalı, 1NA; E-Stop bırakılınca otomatik yeniden başlatmayı engeller | [Merter Elektronik](https://www.merterelektronik.com/reset-butonu-220-v-10-amper-mr1) |
| Kritik | Kontaktör bobin bastırma modülü | 1 | Schneider LA4KE1B, TeSys K varistör | [Endüstriyel Market](https://www.endustriyelmarket.com/schneider-electric-la4ke1b-tesys-k-supresor-modulu-varistor-12) |
| Kritik | Ana kaçak akım koruması + 2 kutuplu otomatik sigorta | 1 set | Saha panosuna ve yük hesabına uygun; değer elektrik sorumlusu tarafından seçilir | [Schneider Acti9 ürün ailesi](https://www.se.com/tr/tr/product-range/7559-acti9/) |
| Kritik | 6 yollu baralı sigorta kutusu | 1 | 12/24 V ATO/ATC, negatif baralı; her 24 V dalını ayrı korur | [Karavan Malzemecim](https://www.karavanmalzemecim.com/pro-dc-barali-sigorta-kutusu-6li-12v24v-191) |
| Kritik | Ana sigorta yuvası | 1 | Motoraid MT-SY25, 2,5 mm² kablolu ve kapaklı; dağıtım kutusundan önce | [Adam Oto](https://www.adamoto.com.tr/urun/standart-bicak-sigorta-yuvasi-2-5mm-kablolu-kapakli-ic-mekan) |
| Kritik | Karışık bıçak sigorta seti | 1 | Standart/mini 1–40 A; nihai değer akım/kablo ölçümüyle seçilir | [Adam Oto](https://www.adamoto.com.tr/urun/100-adet-mini-ve-standart-super-karisik-oto-bicak-sigorta-seti-1a-3a-5a-7-5a-10a-15a-20a-25a-30a-40a) |
| Kritik | USB-A → Micro-USB veri kablosu | 1 | Kısa ve veri destekli; yalnız şarj kablosu kabul edilmez | Yerel satıcıda veri aktarımı doğrulanmış ürün |
| Kritik | İzole kuru kontak röle/PhotoMOS arayüzü | 1 + 1 yedek | Pico 3,3 V ile sürülen, normalde açık kuru kontak; yalnız stok tetik girişine paralel | [PhotoMOS röle araması](https://www.direnc.net/arama?q=photomos) |
| Kritik | Tetik rölesi geri bildirim kontağı | 1 | Zorlamalı kontaklı ara röle veya ayrı yardımcı kontak; yapışma/takılı kalma algısı | [Phoenix Contact röle modülleri](https://www.phoenixcontact.com/tr-tr/products/relay-modules) |
| Kritik | DM542 lojik sürücü katı | 2 kanal × 3 sinyal | Pico GPIO’yu PUL/DIR/ENA optik girişlerinden ayıran open-collector/line-driver; GPIO doğrudan bağlanmaz | [ULN2803A araması](https://www.direnc.net/arama?q=ULN2803A) |
| Kritik | Enkoder giriş izolasyonu/seviye çevirici | 2 | Kesin enkoder modelinin A/B/Z çıkışına uygun hızlı optokuplör veya diferansiyel receiver | [6N137 hızlı optokuplör araması](https://www.direnc.net/arama?q=6N137) |
| Kritik | 5 V dağıtım sigortaları | 2–3 | Pi ve Pico dalları ayrı; DC-DC gerçek sürekli akımına göre seçilir | [Otomotiv bıçak sigorta yuvası araması](https://www.motorobit.com/arama?q=sigorta%20yuvas%C4%B1) |
| Kritik | 3 × 1,0 veya 3 × 1,5 mm² esnek şebeke kablosu | Gereken uzunluk | L/N/PE; eski 2×0,75 mm² TTR kullanılmaz | [3×1,5 kablo araması](https://www.elektrikmarket.com.tr/arama?q=3x1.5%20kablo) |
| Kritik | 2 × 2,5 mm² DC güç kablosu | Gereken uzunluk | 24 V motor/güç dalları; nihai kesit akım, uzunluk ve gerilim düşümüne göre hesaplanır | [2×2,5 kablo araması](https://www.elektrikmarket.com.tr/arama?q=2x2.5%20kablo) |
| Kritik | 4 × 0,75 mm² kontrol kablosu | Gereken uzunluk | E-Stop iki kanal ve düşük akım kontrol; güç kablosundan ayrı güzergâh | [4×0,75 kontrol kablosu araması](https://www.elektrikmarket.com.tr/arama?q=4x0.75%20kontrol%20kablosu) |
| Gerekli | 2 × 0,22–0,34 mm² bükümlü sinyal kablosu | Gereken uzunluk | STEP/DIR, UART ve düşük seviye sinyaller; motor kablosundan ayrı | [LIYCY sinyal kablosu araması](https://www.elektrikmarket.com.tr/arama?q=LIYCY%20kablo) |
| Gerekli | Kablo yüksüğü seti | 1 set | 0,25–2,5 mm² izoleli ferrül; vidalı klemense çıplak çok telli kablo sokulmaz | [Kablo yüksüğü araması](https://www.direnc.net/arama?q=kablo%20y%C3%BCks%C3%BC%C4%9F%C3%BC) |
| Gerekli | Ratchet ferrül/faston krimp pensesi | 1 | Ferrül ve faston için uygun kalıp; pense ile ezme/lehimleme yapılmaz | [Krimp pensesi araması](https://www.direnc.net/arama?q=krimp%20pensesi) |
| Gerekli | 6,3 mm erkek faston + izole kılıf | 1 set | BOM’daki dişi fastonların eşleri; kablo kesitine uygun renk/sınıf | [Erkek faston araması](https://www.direnc.net/arama?q=6.3mm%20erkek%20faston) |
| Gerekli | Kablolu T-Plug erkek/dişi uzatma | 1 | 14 AWG; airsoft stok kablosunu kesmeden güvenlik kesme arayüzü ekler | [Robotistan](https://www.robotistan.com/lipo-tplug-erkek-disi-konnektor-14awg) |
| Gerekli | Kablolu XT60 erkek/dişi pigtail | 2 takım | 14 AWG; üst-alt gövdeyi bakım için ayırır | [Hiber](https://www.hiber.com.tr/xt60-pigtail-erkek-disi-konnektor-kablosu) |
| Gerekli | 4×1,0 mm² LIYCY motor kablosu | 2 × 3 m | İki NEMA23 için toplam 6 m | [KRC Elektromarket](https://www.krcelektromarket.com/erse-4x1mm-liycy-sinyal-kablosu-blendajli-m3) |
| Gerekli | WAGO 221-415 | 4 | Orijinal, beş iletkenli; eski 10 adet kararı iptal | [WAGO](https://www.wago.com/global/installation-terminal-blocks-and-connectors/5-wire-splicing-connector/p/221-415) |
| Gerekli | DIN ray PE/toprak klemensi | 3 | 4 mm²; şebeke PE, Mean Well PE ve metal şasi | [Endüstri Pazar](https://www.endustripazar.com/urun/4mm2-mtk-serisi-vida-baglantili-topraklama-ray-klemens-1010220-onka) |
| Gerekli | 10 mm PET kablo çorabı | 2 × 1 m | Yalnız üç kısa hareketli/sürtünen kablo grubu | [Maasco](https://www.maascoelektrik.com/urun/kablo-toplama-corap-cesitleri-1-metre-10mm-1-metre) |
| Gerekli | 22-pin → 15-pin kamera kablosu | 1 | 200/300/en fazla 500 mm; 5 m kullanılmaz | [Raspberry Pi](https://www.raspberrypi.com/products/camera-cable/?variant=camera-cable-std-mini-500) |
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
| Kontaktör | Eski üst tabloda LP1K1210BD | Yeni seçim LP1K1201BD; 1NK yardımcı kontak EDM için kullanılır, LA4KE1B bobine takılır |
| Pi ↔ Pico haberleşmesi | USB CDC Serial adapter ve runtime profilleri uygulandı | Fiziksel kablo, EMI, reconnect ve safe-load HIL kanıtı tamamlanana kadar LIVE açılmaz |
| Pico firmware | USB stdio/CDC taşıması, framing, heartbeat ve status/ACK yolu uygulandı | Kart pin haritası ve fiziksel aktüatör HIL kabulü tamamlanmadan çıkışlar firmware içinde kapalıdır |
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
| 5P-MCU/5N-MCU | 5 V DC-DC → Pico güç girişi | 0,5–0,75 mm² | Kırmızı/siyah | Besleme topolojisi USB ile çift besleme oluşturmayacak şekilde kesinleştirilir; Pico 3V3 pinine 5 V verilmez |
| USB-DATA | Pi 5 USB-A → Pico Micro-USB | Kısa, veri destekli USB kablosu | Standart kablo | Şarj-only kablo kabul edilmez; fiziksel USB/EMI/HIL kabulü tamamlanana kadar LIVE kullanılmaz |
| PT-PUL/DIR/ENA | Pico sürücü kartı → DM542 #1/#2 | 0,22–0,34 mm² | Numaralı | Her sinyal dönüşüyle bükümlü |
| ENC-A/B/Z | Enkoder → izolasyon → Pico | Ekranlı 4–6 damarlı | Numaralı | Kesin modele göre pinlenir |
| LID-TX/RX/GND | TFA50-L → Pi UART | Kilitli 3/4 damar | Numaralı | TX↔RX çapraz; lojik seviye doğrula |
| FIRE-COM/NO | İzole kuru kontak → stok tetik iki ucu | 0,22–0,34 mm² | Mor çift | Batarya/motor akımı taşımaz |
| FIRE-FB | Röle yardımcı kontak → Pico giriş | 0,22–0,34 mm² | Gri | Takılı röle/tetik geri bildirimi |

## 6. Alt sistem bağlantıları

### 6.1 Şebeke, koruyucu toprak ve 24 V dağıtım

1. IEC/fiş girişindeki L ve N önce iki kutuplu ana şalter/koruma üzerinden geçirilir.
2. 3SK1111-1AB30 emniyet rölesi ile LP1K1201BD bobininin 24 V kontrol beslemesi, kontaktörün kendi kestiği taraftan alınmaz. Güncel BOM ayrı kontrol güç kaynağı içermediği için kontrol beslemesinin kesin kaynağı ve kontaktörün AC/DC kesme konumu onaylı elektrik şemasında çözülmeden enerji verilmez.
3. E-Stop emniyet rölesinin güvenli çıkışı LP1K1201BD kontaktör bobinini sürer; manuel reset ve 1NK EDM geri bildirimi emniyet rölesine döner. Yazılım kontaktörü doğrudan enerjileyemez.
4. Kontaktör ana kontağı, tehlikeli hareket enerjisini kesen tarafta konumlandırılır. LP1K'nin 7,4 V airsoft bataryasını güvenle keseceği varsayılmaz; bu hat için ölçülen stall akımına ve DC kesmeye uygun ayrı eleman gerekir. Raspberry Pi'nin kontrollü kapanması gerekiyorsa bilgisayar beslemesi ayrı “kontrol gücü” dalında tutulabilir; bu karar risk analizine yazılır.
5. PE kablosu önce PE barasına, oradan yıldız topolojiyle RSP-500 kasasına, metal elektrik panosuna ve metal şaseye gider.
6. RSP-500 `V+`/`V-` çıkışları doğrudan çoklu kablo altında sıkıştırılmaz; DIN klemens/sigortalı dağıtım üzerinden dallanır.
7. Her dal ilk enerjide laboratuvar kaynağı veya akım sınırlayıcı ile denenir; boşta gerilim ve yükte gerilim düşümü kaydedilir.

### 6.2 Raspberry Pi 5, AI HAT+ ve Camera Module 3

1. AI HAT+ Raspberry Pi 5 PCIe FFC kablosu ve mekanik standoff'larla üretici yönüne göre takılır.
2. Camera Module 3, Pi 5'in 22-pin CAM/DISP portuna uygun 22-pin→15-pin kamera kablosuyla bağlanır. FFC kilidi açıkken kablo takılır; mavi takviye yüzünün yönü Pi/kamera kılavuzuna göre kontrol edilir.
3. Kamera ve PCIe FFC kablolarında lehim yapılmaz, uzatma/ek yapılmaz.
4. 5 V regülatörün gerçek 5 A sürekli kapasitesi doğrulanmadan Pi 5 bu hatta bağlanmaz. İlk açılışta Pi tarafında düşük gerilim uyarısı ve regülatör sıcaklığı izlenir.

### 6.3 Raspberry Pi 5 ↔ Pico USB hattı

1. Pi 5'in USB-A portu ile Pico'nun Micro-USB portu arasına kısa ve veri destekli kablo takılır. Yalnız güç damarları bulunan “şarj kablosu” kabul edilmez.
2. Kablo bilgisayarda veri aygıtı olarak sınanır; Pico'nun USB cihazı/seri portu olarak numaralandığı görülmeden kablo “uygun” işaretlenmez.
3. Pico harici 5 V DC-DC ile ayrıca besleniyorsa USB üzerinden oluşabilecek çift besleme/backfeed riski çözülmeden iki kaynak aynı anda bağlanmaz. Nihai besleme şekli revizyonlu şemada gösterilir.
4. USB kablosu motor faz kablosundan uzak tutulur, konnektörlerde strain relief uygulanır ve hareketli eksende sert kıvrım oluşturulmaz.
5. Backend ve Pico USB CDC taşıması uygulanmıştır. `/dev/serial/by-id/` kimliği, motor EMI testi, kablo çekme ve reconnect safe-load HIL kanıtı tamamlanana kadar fiziksel kablo motor veya airsoft kontrolünde kullanılmaz.

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

- Pico arayüz kartındaki pin header ve düşük akım sinyal konnektörleri.
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
- [ ] Pi–Pico kablosu veri destekli; Pico USB aygıtı olarak numaralanıyor; çift besleme/backfeed yok.
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
| B — Kontrol gücü | Pi/Pico, aktüatörsüz | Bugün: USB framing ve host test kanıtı. Sahada: enumeration, heartbeat, status/ACK, disconnect ve reconnect safe-load HIL kanıtı | Motor/airsoft çıkışı |
| C — Yapay yük | Motor yerine uygun test yükü, airsoft yerine lamba | E-Stop ve watchdog çıkışı fiziksel kesiyor; 120 ms ateş üst sınırı | Gerçek mekanik hareket/atış |
| D — Motor HIL | Düşük hız, mekanik alan boş | Limit, yön, enkoder, sapma ve E-Stop testleri | Hedefleme doğruluğu |
| E — Airsoft boş HIL | Şarjör/BB yok, güvenli yön | Tek kuru-kontak darbesi, feedback, takılı röle fault'u | BB enerjisi/isabet |
| F — Kontrollü saha | Yetkili alan, kronograf, bariyer, gözlük | Tek atış, E-Stop ateş kesme, yanlış hedef engeli | Yarışma nihai kabulü |
| G — Yarışma provası | Gerçek kamera/LiDAR/parkur | 5/10/15 m görev ve kanıt kaydı | Hakem kabulü; ayrıca yapılır |

## 10. Yazılım/firmware eşlemesi

- Aktif backend zinciri: `FireIntent → Safety Gate → UsbSerialMcuAdapter`.
- `UsbSerialMcuAdapter`, FIRE göndermeden önce taze Pico status, `ARMED`, `fireReady`, `encoderOk`, E-Stop pasif ve fault=0 arar; runtime profilleri `[mcu]` USB ayarlarını kullanır.
- Pico güvenlik çekirdeği interlock açıkken ARM/FIRE'ı reddeder; ateş çıkışını 120 ms sonunda otomatik kapatır.
- E-Stop, heartbeat kaybı, enkoder fault'u, interlock kopması veya takılı feedback çıkışı anında kapatıp `FAULT` durumuna geçirir.
- USB taşıması `UsbSerialMcuAdapter`, Pico USB CDC firmware yolu ve COBS+CRC16 framing ile uygulanmıştır. Tarihsel `CanMcuAdapter` test/geriye dönük referans olarak tutulur; fiziksel disconnect/EMI/HIL testleri yeşil olmadan LIVE çıkışı açılmaz.

## 11. İmalat ekibinin dolduracağı as-built kayıt

| Revizyon | Tarih | Kart/pano revizyonu | Pico pin haritası dosyası | Pi–Pico haberleşmesi | Enkoder modeli | Güvenlik rölesi | Kontrol eden |
|---|---|---|---|---|---|---|---|
| TBD | TBD | TBD | TBD | TBD | TBD | TBD | TBD |

Her değişiklikte bu tablo, tel listesi ve fiziksel fotoğraflar birlikte sürümlenmelidir. Ölçülmemiş değer, tamamlanmış kabul veya doğrulanmış donanım gibi yazılmamalıdır.
