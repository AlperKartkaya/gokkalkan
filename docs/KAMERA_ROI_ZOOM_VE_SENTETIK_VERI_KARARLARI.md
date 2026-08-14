# Kamera ROI, Zoom ve Sentetik Veri Kararları

> **Durum:** CAD/sentetik implementasyon için kesin karar; fiziksel performans
> ölçümleri daha sonra doğrulanacak
> **Kamera:** Raspberry Pi Camera Module 3 Standard / Sony IMX708
> **Model girdisi:** `640×640`, en-boy oranı korunmuş letterbox
> **Güvenlik:** Zoom yalnız algı girdisini değiştirir; hareket veya atış yetkisi vermez.

## 1. Kısa cevap

Evet, iki farklı görüntü ailesi üretmeliyiz:

1. **Tam görüş arama görüntüsü:** Parkurun tamamı görülür. Yüksek çözünürlüklü
   sensör görünüşü önce `1280×720` arama akışına, sonra en-boy oranı bozulmadan
   `640×640` YOLO tensoruna letterbox edilir.
2. **Yüksek çözünürlüklü ROI görüntüsü:** Kararlı track oluştuktan sonra aynı
   sensör karesinin yüksek çözünürlüklü `2304×1296` akışından hedef çevresi
   `1.5×` veya `2×` görüş faktörüyle kırpılır. Crop doğrudan `640×640`
   letterbox aşamasına gider; önce `1280×720`'ye küçültülüp tekrar büyütülmez.

İlk runtime tasarımında Picamera2 `ScalerCrop` kullanmak yerine aynı kamera
isteğinden iki tam-FoV akış alınacaktır:

```text
IMX708 / aynı capture request
├─ main  : 2304×1296 RGB  → dinamik yüksek çözünürlüklü ROI
└─ lores : 1280×720       → tam görüş arama/takip
```

Bu karar, ROI açıkken tam parkur görüşünü kaybetmemizi önler. `ScalerCrop` ve
düşük çözünürlüklü uygulama crop'u yalnız karşılaştırma profili olarak tutulur.

## 2. Camera Module 3 açısından bildiğimiz fiziksel sınırlar

Üretici verisine göre standart Camera Module 3:

- Sony IMX708, `4608×2592`, yaklaşık `11.9 MP`;
- `1.4 µm × 1.4 µm` piksel;
- standart modelde yaklaşık `66°` yatay görüş;
- PDAF otomatik odaklama;
- RAW10 sensör çıkışı;
- HDR açıkken en fazla `2304×1296`, HDR kapalıyken `4608×2592` çıkış.

Kaynaklar:

- [Raspberry Pi Camera Module 3 ürün sayfası](https://www.raspberrypi.com/products/camera-module-3/)
- [Camera Module 3 product brief](https://datasheets.raspberrypi.com/camera/camera-module-3-product-brief.pdf)
- [Picamera2 kullanım kılavuzu](https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf)
- [Raspberry Pi kamera yazılımı dokümantasyonu](https://www.raspberrypi.com/documentation/computers/camera_software.html)

`2304×1296 @ 30 FPS main + 1280×720 lores` performansı şu an **tasarım
adayıdır**. Pi üzerinde ölçülmeden gerçek FPS/latency kabulü sayılmaz.

## 3. Crop gerçekten çözünürlüğü korur mu?

Crop yeni optik detay üretmez; fakat mevcut sensör detayının erken aşamada
atılmasını önleyebilir.

Örnek, `2304×1296` yüksek çözünürlüklü kare ve `2×` ROI:

```text
yüksek çözünürlüklü crop = 1152×648
model içindeki 16:9 içerik = 640×360
```

Bu işlem hâlâ küçültmedir; yapay piksel üretmez. Buna karşılık önce tüm kareyi
`1280×720`'ye küçültüp sonra `640×360` parçasını tekrar büyütmek, ilk küçültmede
kaybedilen ayrıntıyı geri getiremez.

Dolayısıyla doğru sıra:

```text
yüksek çözünürlüklü kare → ROI crop → model letterbox
```

Yanlış/fallback sıra:

```text
yüksek çözünürlüklü kare → 1280×720 → küçük crop → tekrar büyütme → model
```

## 4. “120×120 veya 160×160 crop zaten 640×640 olacak” sorusu

Burada iki farklı ölçüyü ayırmak gerekir:

- **Crop penceresinin boyutu:** Kameradan hangi görüş alanını seçtiğimiz.
- **Crop içindeki hedefin piksel boyutu:** Hedefin sensörde gerçekten kaç piksel
  ayrıntıya sahip olduğu.

`120×120` crop'u `640×640` yapmak hedefi büyütür ama yeni ayrıntı üretmez;
yaklaşık `5.3×` yapay upsample olur. Bu yüzden crop penceresini hedef bbox'ına
eşitlemeyeceğiz.

ROI penceresi:

- daima `16:9` kalacak;
- `2304×1296` main akışına göre `1.5×`, `2×`; yalnız araştırmada `3×` olacak;
- `3×` durumunda bile `768×432` kalacak ve `640×360` model içeriğine
  küçültülecek; model öncesi upsample yapılmayacak;
- hedef bbox'ı çevresinde bağlam payı bırakacak;
- tracker'ın bir önceki karedeki/predicted merkeziyle hareket edecek;
- ekran kenarında ölçüsü değişmeden clamp edilecek.

Hedefin `640×640` tensor içinde farklı büyüklükte görünmesi hata değildir. Zoom'un
amacı zaten aynı fiziksel hedefi daha fazla model pikseliyle temsil etmektir.
Model hem arama ölçeklerini hem ROI ölçeklerini eğitimde görmelidir.

## 5. Neden 640×640 içinde 640×360 aktif görüntü var?

Kamera ve seçtiğimiz ROI `16:9`, model tensörü karedir. Görüntüyü kareye
esnetmeyeceğiz; aksi halde hedef geometrisi bozulur. `1280×720` veya herhangi bir
`16:9` ROI şu şekilde letterbox edilir:

```text
640×640 tensor
├─ üst padding: 140 px
├─ görüntü     : 640×360 px
└─ alt padding: 140 px
```

Bu padding, arama ve ROI yollarında aynıdır. İleride `640×384` model mimarisi
ayrı bir performans deneyi olabilir; mevcut YOLO/Hailo sözleşmesi değiştirilmez.

## 6. Dinamik ROI çalışma akışı

```text
SEARCH_FULL_FRAME
  lores 1280×720 → letterbox 640×640 → YOLO
        ↓ kararlı track (en az 3 kare)
TRACK_ROI
  model merkezi → letterbox ters dönüşümü → lores koordinatı
  lores koordinatı → main 2304×1296 koordinatı
  önceki/predicted merkez → 16:9 ROI crop
  crop → letterbox 640×640 → aynı YOLO
        ↓ track stale / düşük güven / crop dışı
FULL_FRAME_FAILBACK
```

İki YOLO yolu aynı ağırlıkları kullanabilir. Her detection şu alanlarla taşınır:

- `frameMode`: `FULL_FRAME` veya `HIGH_RES_ROI`;
- `cropRectHighResPx`;
- `zoomFactor`;
- `modelContentRectPx` ve padding;
- model bbox'ının tam görüş/main koordinatına geri dönüşümü;
- capture sequence/timestamp;
- uygulanan gerçek `ScalerCrop`, exposure, gain, lens position ve focus metadata.

ROI detection koordinatı tam kamera koordinatına geri çevrilmeden pan/tilt nişan
hatasında kullanılamaz.

## 7. Sentetik veri aileleri

Her temel CAD dünyası dört kat körlemesine çoğaltılmayacak. Seçimli üretim:

### A. Tam görüş — zorunlu

- Tüm pilot dünyalar.
- Kaynak render `2304×1296`.
- Tam FoV → `1280×720` arama görünüşü → `640×640` letterbox.
- Arama, ilk tespit, çok küçük hedef ve false-positive davranışı için.

### B. Yüksek çözünürlüklü ROI — zorunlu alt küme

- Pilot dünyaların dengeli `%40` alt kümesi: `1.5×` ve `2×`.
- Uzak/küçük hedef ağırlıklı `%10` hard-case: ayrıca `3×`.
- Crop merkezi kusursuz değildir; tracker gecikmesi ve bounded merkez hatası vardır.
- Model öncesi upsample yasaktır.

### C. `ScalerCrop` proxy — araştırma alt kümesi

- Aynı sensör-koordinatlı crop'un ISP tarafından `1280×720` çıkışa ölçeklenmesini
  yaklaşıklar.
- Fiziksel Pi testi kazanç gösterirse runtime adayı olur.

### D. Düşük çözünürlüklü application crop — negatif baseline

- Önce `1280×720`, sonra crop ve büyütme.
- Runtime varsayılanı değildir; yüksek çözünürlüklü ROI'nin gerçekten faydalı
  olup olmadığını ölçmek için tutulur.

Tüm türevler aynı `worldId/groupId/split` içinde kalır. Böylece aynı CAD dünyası
train ve validation arasında sızmaz.

## 8. Kamera bozulma zinciri

“Rastgele blur/noise/JPEG” Camera Module 3 simülasyonu değildir. Doğru katmanlar:

```text
ideal optik sahne
→ lens distortion + vignetting
→ odak/PSF ve hareket blur'u
→ sensör örnekleme
→ exposure/analogue gain kaynaklı shot/read noise
→ demosaic
→ lens shading correction
→ AWB + colour correction
→ denoise/sharpen/tonemap
→ crop + scaler
→ yalnız gerçekten kullanılıyorsa codec
→ YOLO letterbox
```

İlk sentetik turda:

- geometrik kamera modeli ve crop/resize sırası kesin uygulanır;
- ideal, nominal, hafif karanlık/aydınlık araştırma profilleri ayrı kimlikle tutulur;
- parametreler Camera Module 3 ölçümüymüş gibi adlandırılmaz;
- RGB888 inference yolunda JPEG/H.264 olmadığı için codec bozulması varsayılan
  olarak uygulanmaz;
- eski rastgele JPEG/blur hattı yalnız `synthetic_seed_2d` smoke verisidir;
- fiziksel metadata gelince exposure/gain/lens/focus bucket'ları gerçek dağılıma
  göre yeniden ağırlıklandırılır.

## 9. Gerçek kamera verisi geldiğinde uygulanacak işlem

Her capture request için eşzamanlı olarak:

1. `lores` tam görüş karesi kaydedilir.
2. Gerekiyorsa `main` yüksek çözünürlüklü kare kaydedilir.
3. Aynı sequence/timestamp altında track merkezinden ROI türetilir.
4. Full-frame ve ROI inference girdileri birlikte saklanır.
5. Picamera2 metadata'sından en az şu alanlar alınır:
   `ScalerCrop`, `SensorTimestamp`, `ExposureTime`, `AnalogueGain`,
   `DigitalGain`, `ColourGains`, `ColourTemperature`, `LensPosition`,
   `FocusFoM` ve mümkünse frame duration.
6. Gerçek görüntüye sentetik blur/noise tekrar uygulanmaz. Yalnız modelin gerçek
   runtime preprocess'i uygulanır.
7. Train/validation/test ayrımı kare bazında değil capture session bazında yapılır.

## 10. Kesin implementasyon kararı

1. Varsayılan runtime yolu: `FULL_FOV_LORES + HIGH_RES_MAIN_SOFTWARE_ROI`.
2. `ScalerCrop`: fiziksel benchmark sonrası seçilebilecek alternatif.
3. `application_crop`: yalnız ablation baseline.
4. `1.5×/2×`: runtime adayları; `3×`: araştırma/hard-case.
5. Her yol `16:9` korunarak `640×640` letterbox edilir; stretch yoktur.
6. ROI crop boyutu bbox boyutu değildir; zoom faktöründen hesaplanan guard-band'li
   sabit oranlı penceredir.
7. Codec artefaktı yalnız gerçek runtime codec kullanırsa veri reçetesine girer.
8. Sentetik ve fiziksel veri aynı koordinat dönüşümü ve preprocess sözleşmesini
   kullanır.
9. ROI tespiti tam görüş koordinatına geri çevrilmeden nişan girdisi olamaz.
10. Bu hattın başarısı fiziksel Camera Module 3/Pi FPS, latency ve focus ölçümü
    olmadan doğrulanmış sayılmaz.

## 11. Sonraki kod sırası

1. Sentetik full-frame ve `high_res_roi` varyantlarını batch üretecek runner.
2. ROI/full-frame paired manifest ve koordinat geri-dönüş testleri.
3. Aynı sentetik sahnede full-frame ↔ ROI detector replay.
4. Pilot render ve B1/B4 karşılaştırması.
5. Fiziksel kamera geldiğinde dual-stream capture ve metadata kaydı.
6. Pi üzerinde main/lores FPS, bellek, latency ve dropped-frame ölçümü.
7. Gerekirse `ScalerCrop` ile aynı benchmark'ın tekrarı.
