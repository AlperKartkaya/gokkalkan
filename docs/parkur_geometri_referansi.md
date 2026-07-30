# Parkur Geometrisi Kanonik Referansı

## 1. Karar ve kapsam

[`Celikkubbe_Hava_Savunma_Sistemleri_Parkur_Cizim.pdf`](Celikkubbe_Hava_Savunma_Sistemleri_Parkur_Cizim.pdf)
yarışma öncesi parkur geometrisinin **kanonik kaynağıdır**. Gerçek parkurda
ölçüm veya çizime göre yeniden kalibrasyon yapılmayacaktır. Organizasyon yeni
bir teknik çizim yayımlamadıkça sensör gözlemleri geometrinin kendisini
değiştirmez; hedefin hangi rotada ve rotanın neresinde bulunduğunu belirler.

Çalışma zamanı tahmini için yalnız rotaların **poligon sınırları içinde kalan
kesintisiz parçaları** kullanılır:

- üç rota da poligonun batı sınırından girer;
- poligon içindeki dalgalı eğri ve doğudaki U-dönüşü korunur;
- Poligon Rotası 1 kuzey sınırında, Poligon Rotası 2 ve 3 güney sınırında biter;
- çıkıştan sonraki poligon dışı geri dönüşler waypoint veri setine alınmaz;
- hedef yeniden batı sınırından girdiğinde yeni geçiş başlatılır ve yay
  koordinatı `s=0` yapılır.

Çizimde görülen kapalı ray döngüsü ile çalışma zamanında kullanılan etkin rota
aynı şey değildir. `14151` ve `15381` mm gibi kapalı döngü açıklıkları, etkin
eğrinin yay uzunluğu olarak kullanılamaz.

Hesaplamaya uygun eşlenik:

- [`config/course/plg26_a_001_002_r1.json`](../config/course/plg26_a_001_002_r1.json)

JSON; yazılı ölçüleri, bunların neyi ölçtüğünü, toleransları, datumları,
poligon içine kırpılmış üç eğriyi, yay uzunluğu `s` değerlerini, eğri
teğetlerini ve sistem referansına göre yatay menzil/açıları içerir. Çalışma
zamanında PDF tekrar okunmaz; PDF yalnız kaynak denetiminde veya yeni revizyon
yayımlandığında açılır.

## 2. Kaynak hiyerarşisi

| Öncelik | Kaynak | Yetki alanı |
| --- | --- | --- |
| 1 | Parkur teknik çizimindeki yazılı ölçüler | Dış yerleşim, poligon, kapalı döngü, ofset ve varsayılan toleranslar |
| 2 | Yazılı ölçülerden cebirsel türetilen datumlar | Kanonik koordinat sistemindeki nominal konumlar |
| 3 | Teknik çizimin üst görünüşündeki rota izi | Analitik denklemi verilmeyen poligon içi eğri biçimi ve sistem referansı |
| 4 | [`sartname_v4.pdf`](sartname_v4.pdf) | A→B görev yönü, üç hedef/rota, aşamalar ve güvenlik kuralları |
| 5 | Simülasyon/kalibrasyon girdisi | Kaynaklarda bulunmayan hız, gecikme ve balistik değerler |

Çelişkide yazılı ölçü rasterdan türetilen değeri geçersiz kılar. Şartname görev
davranışında, teknik çizim geometrik ölçülerde yetkilidir. Raster yalnız
yazılı koordinatı bulunmayan eğri biçimini ve sınır kesişimlerini sayısallaştırır.

## 3. Kaynak kimliği

| Alan | Değer |
| --- | --- |
| Dosya | `docs/Celikkubbe_Hava_Savunma_Sistemleri_Parkur_Cizim.pdf` |
| SHA-256 | `466ef675555aace404e1e52902a12c01a92bae616418cc3f34f1330e43f2755e` |
| PDF metadata başlığı | `PLG26-A-001-002-01` |
| Antet çizim numarası | `PLG26-A-001-002-00` |
| Revizyon | `1` |
| Başlık | `Parkur ve Poligon Yerleşimi` |
| Tasarım tarihi | `07.03.2026` |
| Çizim / son kayıt tarihi | `11.03.2026` |
| Ölçek | `1:200` |
| Sayfa | `1`, A3 yatay |
| Üretici | SOLIDWORKS 2024 SP5.0 |
| Antet uyarısı | `DO NOT SCALE DRAWING` |
| Uzunluk birimi | milimetre |

Metadata başlığının son eki `-01`, antet çizim numarasının son eki `-00`’dır.
Veri seti kimliği antet numarası ve Rev 1 kullanılarak
`PLG26-A-001-002-00-R1` olarak saklanır.

`DO NOT SCALE DRAWING` nedeniyle yazılı ölçüler rasterdan yeniden ölçülmez.
Yalnız analitik koordinatı bulunmayan rota merkez çizgisinin eğri biçimi,
poligonla kesişimi ve sistem yaw referansı `RASTER_TRACE` kökeniyle çıkarılır.
Bu türevler yazılı ölçü toleransı iddiası taşımaz.

## 4. Yazılı ölçülerin yeniden sınıflandırılması

### 4.1. Üst görünüş - plan

| Kimlik | Ölçü (mm) | Adet | Sınıf | Tam olarak neyi ölçüyor? | Etkin rota kullanımındaki rolü |
| --- | ---: | ---: | --- | --- | --- |
| `outer_layout_width` | 18000 | 1 | Dış yerleşim boyutu | Dış batı-doğu sınırları | Poligon X datumunu türetir; rota uzunluğu değildir |
| `outer_layout_height` | 14000 | 1 | Dış yerleşim boyutu | Dış güney-kuzey sınırları | Poligon Y datumunu türetir; rota uzunluğu değildir |
| `poligon_width` | 16000 | 1 | Poligon boyutu | Poligon batı-doğu sınırları | Etkin tahmin bölgesinin genişliği |
| `poligon_height` | 10000 | 1 | Poligon boyutu | Poligon güney-kuzey sınırları | Etkin tahmin bölgesinin yüksekliği |
| `north_closed_loop_horizontal_span` | 14151 | 1 | Kapalı döngü açıklığı | Kuzey kapalı döngünün batı-doğu ekstremi | Rota 1 doğu U-dönüşü için datum; eğri yay uzunluğu değildir |
| `north_and_south_inner_loops_east_to_poligon_east` | 2715 | 2 | Döngü-poligon ofseti | Kuzey ve güney iç döngülerin doğu ekstremi ile poligon doğu sınırı | Rota 1 ve 3 doğu U-dönüşü X datumu |
| `north_and_south_inner_loops_west_to_poligon_west` | 866 | 2 | Döngü-poligon ofseti | Kuzey ve güney iç döngülerin batı ekstremi ile poligon batı sınırı | Poligon dışı dönüş; etkin rotaya alınmaz |
| `poligon_grid_west_interval` | 5000 | 1 | Poligon menzil ızgarası | Poligon batı sınırı-ilk düşey çizgi | 15 m-10 m datum aralığı; rota uzunluğu değildir |
| `poligon_grid_east_interval` | 5000 | 1 | Poligon menzil ızgarası | Birinci-ikinci düşey çizgi | 10 m-5 m datum aralığı; rota uzunluğu değildir |
| `outer_north_to_north_loop_return` | 705 | 1 | Dış dönüş-dış sınır ofseti | Dış kuzey sınırı-kuzey döngünün üst dönüş segmenti | Poligon kuzey datum zinciri; rota tahmininde kullanılmaz |
| `north_loop_return_to_poligon_north` | 645 | 1 | Dış dönüş-poligon ofseti | Kuzey döngünün üst dönüş segmenti-poligon kuzey sınırı | Poligon kuzey datum zinciri; dış dönüş etkin rotaya alınmaz |
| `central_outer_closed_loop_horizontal_span` | 15381 | 1 | Kapalı döngü açıklığı | Merkez dış kapalı döngünün batı-doğu ekstremi | Rota 2 doğu U-dönüşü için datum; eğri yay uzunluğu değildir |
| `route_2_marked_curve_to_poligon_south` | 4711 | 1 | Etkin eğri-poligon ofseti | Rota 2 dalgalı eğrisinin işaretli datumu-poligon güney sınırı | Rota 2 eğrisinin Y ankrajı |
| `route_3_marked_curve_to_poligon_south` | 2133 | 1 | Etkin eğri-poligon ofseti | Rota 3 dalgalı eğrisinin işaretli datumu-poligon güney sınırı | Rota 3 eğrisinin Y ankrajı |
| `poligon_south_to_south_inner_loop_return` | 645 | 1 | Dış dönüş-poligon ofseti | Poligon güney sınırı-güney iç döngünün alt dönüş segmenti | Poligon dışı dönüş; etkin rotaya alınmaz |
| `poligon_south_to_central_outer_loop_return` | 1756 | 1 | Dış dönüş-poligon ofseti | Poligon güney sınırı-merkez dış döngünün alt dönüş segmenti | Poligon dışı dönüş; etkin rotaya alınmaz |
| `central_outer_loop_east_to_poligon_east` | 2105 | 1 | Döngü-poligon ofseti | Merkez dış döngü doğu ekstremi-poligon doğu sınırı | Rota 2 doğu U-dönüşü X datumu |
| `central_outer_loop_west_to_poligon_west` | 1487 | 1 | Döngü-poligon ofseti | Merkez dış döngü batı ekstremi-poligon batı sınırı | Poligon dışı dönüş; etkin rotaya alınmaz |
| `outer_west_to_central_outer_loop_west` | 517 | 1 | Dış dönüş-dış sınır ofseti | Dış batı sınırı-merkez dış döngü batı ekstremi | Poligon dışı dönüş; etkin rotaya alınmaz |
| `central_outer_loop_return_to_outer_south` | 894 | 1 | Dış dönüş-dış sınır ofseti | Merkez dış döngü alt dönüş segmenti-dış güney sınırı | Poligon dışı dönüş; etkin rotaya alınmaz |

Özellikle iki farklı `645` mm ölçü birbirine karıştırılmamalıdır: üstteki değer
kuzey döngünün dış dönüşü ile poligon kuzeyi arasındadır; alttaki değer güney
iç döngünün dış dönüşü ile poligon güneyi arasındadır. `4711` ve `2133` mm ise
bir rota uzunluğu değil, sırasıyla Poligon Rotası 2 ve 3 üzerindeki işaretli
eğri datumlarının poligon güney sınırına düşey uzaklığıdır.

### 4.2. Yan görünüş

| Kimlik | Ölçü (mm) | Tam olarak neyi ölçüyor? |
| --- | ---: | --- |
| `structure_max_height` | 2950 | Zemin-üst örtü tepe datumu |
| `side_height_datum_1300` | 1300 | Zemin-çizimdeki 1300 mm yan görünüş datumu |
| `track_height_datum` | 193 | Zemin-ray/taşıyıcı düşük datumu |
| `side_height_datum_1000` | 1000 | Zemin-çizimdeki 1000 mm yan görünüş datumu |

`1300` ve `1000` mm değerleri hedef merkez yüksekliği olarak etiketlenmemiştir;
balistik düşey hedef koordinatı olarak kullanılmaz. Toplam **26 ölçü oku**
korunmuştur. `866` ve `2715` değerleri iki kapalı döngü için ikişer kez
gösterildiğinden tek kimlik altında `Adet = 2` tutulur.

## 5. Antetteki varsayılan toleranslar

Aralıklar antetteki `From` ve `Up To` satırlarından aktarılmıştır.

### 5.1. Uzunluk

| From (mm) | Up To (mm) | Tolerans (mm) |
| ---: | ---: | ---: |
| 0,5 | 6 | ±0,1 |
| 6 | 30 | ±0,2 |
| 30 | 120 | ±0,3 |
| 120 | 400 | ±0,5 |
| 400 | 1000 | ±0,8 |
| 1000 | 2000 | ±1,2 |
| 2000 | 4000 | ±2 |

### 5.2. Radyüs / pah

| From (mm) | Up To (mm) | Tolerans (mm) |
| ---: | ---: | ---: |
| 0,5 | 3 | ±0,2 |
| 3 | 6 | ±0,5 |
| 6 | 4000 | ±1 |

### 5.3. Açı

| From (mm) | Up To (mm) | Tolerans (°) |
| ---: | ---: | ---: |
| 0,5 | 6 | ±1 |
| 6 | 30 | ±0,5 |
| 30 | 120 | ±0,3 |
| 120 | 400 | ±0,2 |
| 400 | 4000 | ±0,1 |

Antet ayrıca diş standardı olarak ISO 261’i, yüzey kalitesi olarak ISO 1302’yi
belirtir ve keskin köşelerin kırılmasını ister.

**Kritik sınır:** tolerans tablosu 4000 mm’de biter. `4711`, `5000`, `10000`,
`14000`, `14151`, `15381`, `16000` ve `18000` mm ölçüler için antette
varsayılan tolerans verilmez. Son satırdaki ±2 mm bu değerlere ekstrapole
edilmez. Rasterdan çıkarılan eğri waypoint’lerine de bu tolerans tablosu
uygulanmaz.

## 6. Kanonik koordinat sistemi ve datumlar

`course` çerçevesi sağ ellidir:

- orijin: dış yerleşim dikdörtgeninin güneybatı köşesi;
- `+X`: çizimde sağa/doğuya;
- `+Y`: çizimde yukarı/kuzeye;
- `+Z`: yukarı.

Çalışma zamanı koordinatları metredir; doğrudan ölçüler JSON’da milimetre
olarak korunur.

| Datum | X (mm) | Y (mm) | Türetim / anlam |
| --- | ---: | ---: | --- |
| Dış güneybatı | 0 | 0 | Orijin |
| Dış kuzeydoğu | 18000 | 14000 | Dış yerleşim toplam ölçüleri |
| Poligon güneybatı | 2000 | 2650 | `18000-16000`; `14000-(705+645)-10000` |
| Poligon kuzeydoğu | 18000 | 12650 | `14000-(705+645)` |
| 15 m çizgisi | 2000 | - | Şartname şekli + poligon batı datumu |
| 10 m çizgisi | 7000 | - | `2000+5000` |
| 5 m çizgisi | 12000 | - | `2000+5000+5000` |
| Kuzey kapalı döngü batı ekstremi | 1134 | - | `2000-866`; poligon dışı |
| Kuzey kapalı döngü doğu ekstremi | 15285 | - | `18000-2715`; Rota 1 U-dönüşü ankrajı |
| Kuzey kapalı döngü üst dönüşü | - | 13295 | `14000-705`; poligon dışı |
| Güney iç döngü doğu ekstremi | 15285 | - | `18000-2715`; Rota 3 U-dönüşü ankrajı |
| Poligon Rotası 3 işaretli eğri datumu | - | 4783 | `2650+2133` |
| Güney iç döngü alt dönüşü | - | 2005 | `2650-645`; poligon dışı |
| Merkez dış döngü doğu ekstremi | 15895 | - | `18000-2105`; Rota 2 U-dönüşü ankrajı |
| Poligon Rotası 2 işaretli eğri datumu | - | 7361 | `2650+4711` |
| Merkez dış döngü alt dönüşü | - | 894 | `2650-1756`; poligon dışı |

Kuzey ve güney iç döngülerde `866` ve `2715` ofsetleri iki kez gösterilir.
`14151` mm yazısı kuzey döngünün yatay açıklığıdır; güney iç döngüde aynı
açıklık, tekrarlanan ofsetlerden `15285-1134=14151` olarak türetilir.

Merkez dış döngünün batı ekstremi üç ölçü zincirinde `513`, `514` ve `517` mm
sonuçlarını verir:

- `2000-1487 = 513`;
- `18000-2105-15381 = 514`;
- dış batı sınırından doğrudan ölçü `517`.

JSON nominali `514` mm seçer; çünkü `15381` mm kapalı-döngü açıklığını ve
`2105` mm doğu ofsetini birlikte kapatır. Diğer iki sonuç kapanış kontrolü
olarak saklanır. Bu 3-4 mm fark rasterla düzeltilmez ve etkin rota başlangıcı
zaten poligon batı sınırı `x=2000` mm olduğundan tahmine taşınmaz.

## 7. Poligon içindeki üç eğri rota

`Üst / Orta / Alt` ifadeleri kalıcı rota adı değildir. JSON’daki adlar,
poligonun **batı sınırındaki girişlerin kuzeyden güneye iç sırasını** anlatan,
resmî olmayan kararlı kimliklerdir:

1. `POLIGON_ROUTE_1`: batı sınırındaki en kuzey giriş; kuzey sınırından çıkış;
2. `POLIGON_ROUTE_2`: batı sınırındaki orta giriş; güney sınırından çıkış;
3. `POLIGON_ROUTE_3`: batı sınırındaki en güney giriş; güney sınırından çıkış.

Üç rotada da poligon içindeki dalgalı yaklaşım ve sisteme en yakın doğu
U-dönüşü korunur. Poligon dışındaki üst/alt düz dönüş segmentleri ile batıdaki
geri dönüşler çıkarılır.

| Kimlik | Giriş `(x,y)` m | Çıkış `(x,y)` m | Çıkış sınırı | Eğri yay uzunluğu (m) | Giriş-çıkış kirişi (m) | Eğrinin kirişe ek mesafesi (m) | Kirişten en büyük sapma (m) | Nokta |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| `POLIGON_ROUTE_1` | `(2,0000; 10,2582)` | `(15,2160; 12,6500)` | Kuzey | 16,3831 | 13,4307 | 2,9524 | 2,2442 | 60 |
| `POLIGON_ROUTE_2` | `(2,0000; 7,2013)` | `(15,8950; 2,6500)` | Güney | 22,8850 | 14,6214 | 8,2636 | 4,2662 | 72 |
| `POLIGON_ROUTE_3` | `(2,0000; 4,7937)` | `(15,2160; 2,6500)` | Güney | 15,9319 | 13,3887 | 2,5432 | 2,0222 | 70 |

Yay uzunluğunun kirişten `2,54-8,26` m fazla ve geometrinin kirişten
`2,02-4,27` m sapıyor olması, rotaların düz doğru kabul edilemeyeceğini
nicel olarak gösterir. Bunlar raster eğri türevleridir; doğrudan ölçü ve
varsayılan tolerans değildir.

Rota merkez çizgileri teknik çizimdeki 948×737 px üst görünüşten çıkarılmış,
küçük raster kopuklukları enterpole edilmiş ve yaklaşık 1,2 px RDP
toleransıyla sadeleştirilmiştir. Poligon sınır merkez çizgileri
`u=[127,905]`, `v=[94,579]` px olarak doğrulanmış; her iz batıdaki ilk giriş ile
kuzey/güneydeki ilk çıkış arasında kırpılmıştır. Eğri biçimi rasterdan gelir,
koordinatlar yazılı poligon ve rota datumlarına oturtulur.

Her `poligon_waypoints` noktası şunları içerir:

- `s_m`: poligon girişinden itibaren kümülatif **eğri yay uzunluğu**;
- `x_m`, `y_m`: `course` koordinatı;
- `tangent_course_deg`: eğrinin o noktadaki yerel hareket doğrultusu;
- `range_m`: türetilen sistem yaw referansına yatay mesafe;
- `bearing_base_deg`: `base +X` yönüne göre yatay açı;
- `source_px`: denetim için kaynak raster koordinatı.

Menzil aralıkları sırasıyla `3,9671-16,0099`, `2,0855-15,8004` ve
`4,1047-16,0487` m’dir. Bunlar yalnız yatay düzlemde, doğrudan
ölçülendirilmemiş sistem yaw merkezine göredir; LiDAR eğik menzili veya 3B
namlu-hedef mesafesi değildir.

## 8. Eğriyi kullanan kestirim modeli

Parkur geometrisi görüntü sınıflandırma modeline gömülen bir ezber değil,
kamera/LiDAR ölçümlerini sınırlandıran ayrı bir **yapısal öncül** olmalıdır.
Her etkin track için önerilen durum:

```text
state = [route_id, pass_index, s, v]

route_id   : üç poligon rotasından biri
pass_index : batı sınırından her yeniden girişte artan geçiş sayacı
s          : poligon girişinden itibaren eğri yay uzunluğu
v          : eğri boyunca ds/dt hedef hızı
```

### 8.1. Rota eşleme

1. Kamera hedef bearing’ini ve sınıf/dost-düşman bilgisini üretir.
2. LiDAR aynı zamana ve bearing’e bağlanan menzili üretir.
3. Ölçüm, her `poligon_waypoints` polilinesine izdüşürülür.
4. Beklenen `(menzil, bearing)` ile sensör hatası ve önceki `s,v` sürekliliği
   birlikte değerlendirilir.
5. Tek kareyle rota değiştirilmez; olasılık ardışık gözlemlerle güncellenir.
6. Ham sensör konumu, rota üzerine izdüşürülmüş konum, artık hata, `route_id`,
   `pass_index` ve `s` birlikte loglanır.

Geometrinin doğru kabul edilmesi sensör yokken hedef varmış gibi davranmak
değildir. Harita hedefin nerede **bulunabileceğini** sınırlar; anlık varlık ve
konumu kamera/LiDAR belirler.

### 8.2. Kiriş değil, yay koordinatıyla ileri kestirim

İleri kestirim giriş-çıkış arasındaki düz kirişte yapılmaz:

```text
s_hit = s_now + v_est * tau_total
p_hit = route_polyline(route_id, s_hit)
t_hit = route_tangent(route_id, s_hit)
```

`route_polyline`, `s` değerini çevreleyen iki waypoint’i bulup yalnız o kısa
eğri segmentinde enterpolasyon yapar. Rotanın ilk ve son noktası arasında tek
bir doğrusal enterpolasyon yapılmaz. Hız da `dx/dt` değil, eğri boyunca `ds/dt`
olarak kestirilir; böylece U-dönüşündeki yön değişimi doğal olarak modele girer.

Toplam önleme süresi:

```text
tau_total =
    algılama_zaman_damgası_gecikmesi
  + karar_ve_komut_gecikmesi
  + taret_yerleşme_süresi
  + tetik_mekanik_gecikmesi
  + uçuş_süresi(menzil(p_hit))
```

`p_hit` menzili uçuş süresini, uçuş süresi de `p_hit` konumunu değiştirdiği için
iki-üç sabit nokta iterasyonu yapılabilir. `menzil/namlu_hızı` yalnız başlangıç
yaklaşımıdır; menzil-uçuş süresi tablosu güvenli kontrollü testten gelmelidir.
Hedef hızı kaynaklarda sayısal verilmediği için önceden bilinen geometri
parametresi değildir; yarışmada ardışık `s` ölçümlerinden kestirilir.

### 8.3. Poligon çıkışı ve yeniden giriş

Önerilen yaşam döngüsü:

```text
OUTSIDE -> ENTRY_CANDIDATE -> ACTIVE_IN_POLIGON -> EXITED_OUTSIDE -> OUTSIDE
```

- batı sınırında doğrulanan girişte `s=0` ve `pass_index += 1`;
- kuzey/güney çıkışında rota-tabanlı ileri atış noktası geçersizleştirilir;
- `s_hit`, rota yay uzunluğunu aşıyorsa değer mod alınarak döngüye sarılmaz;
- dış dönüş için hayalet hedef konumu veya ateş çözümü üretilmez;
- yeniden giriş yeni sensör gözlemiyle doğrulanır; önceki geçişin `s` değeri
  kullanılmaz.

### 8.4. Emniyet sınırı

- Rota kestirimi tek başına ateş izni üretmez.
- Kamera track’i veya LiDAR ölçümü stale ise ileri kestirim geçersizdir.
- Dost hedef, menzil penceresi, forbidden-fire alanı, Acil Durdur ve LIVE arm
  kontrolleri backend Safety Gate içinde kalır.
- `s_hit` poligon dışına taşıyorsa veya çıkıştan sonraya denk geliyorsa ateş
  çözümü fail-closed reddedilir.
- Sensör-harita artık hatası kalıcı ve büyükse geometri otomatik eğilip
  bükülmez; sensör, ekstrinsik veya zaman senkronizasyon arızası raporlanır.

## 9. Kaynaklarda bulunmayan değerler

Aşağıdakiler parkur PDF’sinden çıkarılamaz ve geometri JSON’una varsayım olarak
yazılmaz:

- hedef hızı ve hız profili;
- airsoft namlu çıkış hızı, sürükleme ve menzile bağlı uçuş süresi;
- kamera, LiDAR, encoder, karar, taret ve tetik gecikmeleri;
- hedef merkez yüksekliği ve hedef gerçek ölçüleri;
- kamera/LiDAR/taret extrinsic kalibrasyonu;
- sistem yaw merkezinin doğrudan ölçülendirilmiş `course` koordinatı;
- CAD spline kontrol noktaları veya analitik rota denklemleri.

## 10. Sürüm ve çalışma zamanı kuralları

1. Yazılım açılışında PDF hash’i veya veri seti kimliği doğrulanır.
2. Beklenen kimlik `PLG26-A-001-002-00-R1` değilse LIVE arm kapalı kalır.
3. Organizasyon yeni çizim yayımlarsa eski JSON üzerine yazılmaz; yeni revizyon
   kimliğiyle ayrı veri seti üretilir.
4. Doğrudan ölçü, tolerans, datum, poligon sınırı ve eğri farkları revizyonlar
   arasında raporlanır.
5. Frontend eğitim geometrisi ve backend rota kestirimi aynı kanonik JSON’dan
   beslenir; koordinatlar iki yerde elle tutulmaz.
6. Çalışma zamanı sensör verisi `s` ve `v` durumunu günceller fakat kanonik
   waypoint’leri yeniden kalibre etmez.

## 11. Uygulama durumu ve sıradaki işler

1. **Tamamlandı:** ölçü anlamları yeniden sınıflandırılmış, poligon içi eğri
   waypoint’leri ve toleransları içeren kanonik Markdown + JSON.
2. **Tamamlandı:** `frontend/src/competitionCourse.ts`, elle tutulan düz/seyrek
   rota kopyası yerine JSON’daki 202 `poligon_waypoints` noktasını kullanır;
   çizim koordinatlarını ekrana dönüştürür, hareketi `s` yay uzunluğuyla
   enterpole eder ve nominal menzil/açıyı aynı sistem referansından hesaplar.
3. **Tamamlandı:** `backend/src/gokkalkan_backend/course_geometry.py`, veri
   seti kimliğini ve poligon kapsamını açılışta doğrular; sensör menzil/açısını
   eğrilere izdüşürerek `[route_id, pass_index, s, v]` üretir. `/tracks/update`
   sonucu `courseState` alanında rota, geçiş, yay konumu, hız, teğet ve artık
   hatayı yayımlar.
4. **Tamamlandı:** haritalanmış hedef poligon dışında ise `predictionValid`
   kapanır ve backend Safety Gate `FireIntent` isteğini
   `BLOCKED_TARGET_GATE` ile reddeder. Harita menzili LiDAR sağlık girdisinin
   veya ölçülmüş menzilin yerine geçmez.
5. **Tamamlandı:** `CourseTrackEstimator.predict_intercept`, ölçülmüş namlu
   hızı ve sabit gecikme açıkça verildiğinde sabit nokta iterasyonuyla eğri
   üzerindeki buluşma noktasını hesaplar; sonuç rota çıkışını aşarsa `None`
   döndürür. Çizimde bulunmayan bir namlu hızı varsayılanı tanımlanmamıştır.
6. Sentetik kamera/LiDAR replay’lerinde rota seçimi, eğri boyunca hız ve ileri
   konum hatasını ölç; ayrıca düz-kiriş yaklaşımıyla farkını raporla.
7. Fiziksel entegrasyonda airsoft menzil-uçuş süresi ve toplam sistem gecikme
   tablosunu geometri dosyasından ayrı kalibre et; bu ölçüm tamamlanana kadar
   kestirimi doğrudan fiziksel atış komutuna bağlama.
