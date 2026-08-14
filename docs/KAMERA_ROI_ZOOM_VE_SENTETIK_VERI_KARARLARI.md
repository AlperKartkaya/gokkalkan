# Kamera ROI, Zoom ve Sentetik Veri Kararları

> **Durum:** 15 Ağustos 2026 tarihinde arama/takip bölümü ADR-006 ile güncellendi;
> fiziksel performans ölçümleri daha sonra doğrulanacak
> **Kamera:** Raspberry Pi Camera Module 3 Standard / Sony IMX708
> **Model girdisi:** `640×640`; kare tile/ROI'de padding yok, legacy full-frame'de letterbox
> **Bağlayıcı arama kararı:** [`adr/006-sahi-hailo-tiled-search.md`](adr/006-sahi-hailo-tiled-search.md)
> **Güvenlik:** Zoom yalnız algı girdisini değiştirir; hareket veya atış yetkisi vermez.

## 1. Kısa cevap

Üç farklı görüntü ailesi üretmeliyiz:

1. **SAHI arama tile'ı:** `2304×1296` main görüntü `%25` örtüşmeli sekiz
   `768×768` kare tile'a ayrılır; her tile `640×640` modele gider.
2. **Kare takip ROI'si:** Kararlı ilk tespitten sonra hedef çevresindeki
   `768×768` main-stream crop'u `640×640` modele gider. Kayıpta `960×960` ve
   `1152×1152` kurtarma pencereleri kullanılır.
3. **Tam görüş legacy baseline:** `1280×720 → 640×360 letterbox` yalnız
   ablation/teşhis için tutulur; ilk tespitin doğruluk kapısı değildir.

İlk runtime tasarımında Picamera2 `ScalerCrop` kullanmak yerine aynı kamera
isteğinden iki tam-FoV akış alınacaktır:

```text
IMX708 / aynı capture request
├─ main  : 2304×1296 RGB  → SAHI arama tile'ları + kare takip ROI'si
└─ lores : 1280×720       → UI + motion/HSV hızlı adayları
```

Bu karar, ROI açıkken tam parkur görüşünü kaybetmemizi önler. Motion/HSV yalnız
öncelikli aday üretir; periyodik SAHI sweep'in yerini almaz. `ScalerCrop`, eski
full-frame letterbox ve düşük çözünürlüklü uygulama crop'u yalnız karşılaştırma
profili olarak tutulur.

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
yüksek çözünürlüklü kare → kare ROI crop → 640×640 uniform resize
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

- modelle aynı oranlı kare olacak;
- normal takipte `768×768`, kayıp kurtarmada `960×960` ve `1152×1152` olacak;
- `640×640` model girdisine yalnız küçültülecek; model öncesi upsample yapılmayacak;
- hedef bbox'ı çevresinde bağlam payı bırakacak;
- tracker'ın bir önceki karedeki/predicted merkeziyle hareket edecek;
- ekran kenarında ölçüsü değişmeden clamp edilecek.

Hedefin `640×640` tensor içinde farklı büyüklükte görünmesi hata değildir. Zoom'un
amacı zaten aynı fiziksel hedefi daha fazla model pikseliyle temsil etmektir.
Model hem arama ölçeklerini hem ROI ölçeklerini eğitimde görmelidir.

## 5. Tam görüntü baseline'ında neden yalnız 640×360 aktif alan var?

Kamera tam görüntüsü `16:9`, model tensörü karedir. Görüntüyü kareye esnetmek
geometriyi bozar. Bu nedenle legacy `1280×720` full-frame baseline şu şekilde
letterbox edilir:

```text
640×640 tensor
├─ üst padding: 140 px
├─ görüntü     : 640×360 px
└─ alt padding: 140 px
```

SAHI arama tile'ı ve kare track ROI'si doğal olarak karedir; bu yollarda padding
yoktur ve `640×640` tensörün tamamı görüntü taşır. Full-frame baseline yalnız
ablation/teşhis içindir.

## 6. Dinamik ROI çalışma akışı

```text
SEARCH_SAHI_SWEEP
  main 2304×1296 → 8× 768×768 overlap tile → 640×640 YOLO batch
  tile sonuçları → main koordinatı → cross-tile merge
        ↓ son 3 sweep'in en az 2'sinde tutarlı detection
TRACK_SQUARE_ROI
  önceki/predicted merkez → 768×768 kare crop → 640×640 YOLO
        ↓ tek/çift kayıp
TRACK_EXPANDED_ROI
  960×960 → 1152×1152 kurtarma crop'u
        ↓ stale / düşük güven / crop dışı
SEARCH_SAHI_SWEEP
```

İki YOLO yolu aynı ağırlıkları kullanabilir. Her detection şu alanlarla taşınır:

- `frameMode`: `SEARCH_SAHI_TILE`, `TRACK_SQUARE_ROI` veya `FULL_FRAME_LEGACY`;
- `sliceIndex`, `sweepId` ve `sliceRectFullFramePx`;
- `cropRectHighResPx`;
- `roiSourceSizePx`;
- `modelContentRectPx` ve padding;
- model bbox'ının tam görüş/main koordinatına geri dönüşümü;
- capture sequence/timestamp;
- uygulanan gerçek `ScalerCrop`, exposure, gain, lens position ve focus metadata.

ROI detection koordinatı tam kamera koordinatına geri çevrilmeden pan/tilt nişan
hatasında kullanılamaz.

## 7. Sentetik veri aileleri

Her temel CAD dünyası dört kat körlemesine çoğaltılmayacak. Seçimli üretim:

### A. SAHI arama tile'ı — zorunlu

- Tüm pilot dünyalar.
- Kaynak render `2304×1296`.
- Kamera etkileri full frame'e uygulandıktan sonra `%25` overlap ile sekiz
  `768×768` tile.
- Tile → `640×640`; padding yok.
- Tile sınırı, kırpılmış annotation ve boş/hard-negative davranışı için.

### B. Kare takip ROI'si — zorunlu

- Normal `768×768`; kurtarma alt kümeleri `960×960` ve `1152×1152`.
- Crop merkezi kusursuz değildir; tracker gecikmesi ve bounded merkez hatası vardır.
- Model öncesi upsample yasaktır.

### C. Tam görüş letterbox — legacy ablation

- `1280×720 → 640×360` aktif alan.
- Birincil arama datası değildir; küçük hedef kaybını ölçen baseline'dır.

### D. `ScalerCrop` proxy — araştırma alt kümesi

- Aynı sensör-koordinatlı crop'un ISP tarafından `1280×720` çıkışa ölçeklenmesini
  yaklaşıklar.
- Fiziksel Pi testi kazanç gösterirse runtime adayı olur.

### E. Düşük çözünürlüklü application crop — negatif baseline

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
→ model preprocess'i: kare tile/ROI için uniform resize, legacy 16:9 için letterbox
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
3. Aynı sequence/timestamp altında SAHI tile'ları ve track merkezinden kare ROI türetilir.
4. Tile, full-frame legacy ve ROI inference girdileri birlikte saklanır.
5. Picamera2 metadata'sından en az şu alanlar alınır:
   `ScalerCrop`, `SensorTimestamp`, `ExposureTime`, `AnalogueGain`,
   `DigitalGain`, `ColourGains`, `ColourTemperature`, `LensPosition`,
   `FocusFoM` ve mümkünse frame duration.
6. Gerçek görüntüye sentetik blur/noise tekrar uygulanmaz. Yalnız modelin gerçek
   runtime preprocess'i uygulanır.
7. Train/validation/test ayrımı kare bazında değil capture session bazında yapılır.

## 10. Kesin implementasyon kararı

1. Varsayılan arama yolu: `2304×1296 MAIN + 8×768 SAHI SEARCH`.
2. Varsayılan takip yolu: `768×768 SQUARE TRACK ROI`; kayıpta `960/1152`.
3. Motion/HSV yalnız öncelikli aday üretir; SAHI sweep'i devre dışı bırakamaz.
4. Full-frame letterbox, `ScalerCrop` ve `application_crop` yalnız ablation baseline'dır.
5. Kare tile/ROI `640×640` tensörün tamamını kullanır; stretch ve upsample yoktur.
6. ROI crop boyutu bbox boyutu değildir; hedef çevresinde takip bağlamı bırakır.
7. Codec artefaktı yalnız gerçek runtime codec kullanırsa veri reçetesine girer.
8. Sentetik ve fiziksel veri aynı koordinat dönüşümü ve preprocess sözleşmesini
   kullanır.
9. ROI tespiti tam görüş koordinatına geri çevrilmeden nişan girdisi olamaz.
10. Bu hattın başarısı fiziksel Camera Module 3/Pi FPS, latency ve focus ölçümü
    olmadan doğrulanmış sayılmaz.

## 11. Sonraki kod sırası

1. ✅ SAHI `0.11.36` offline exact lock ve dependency-light Hailo runtime adapterı.
2. ✅ Sentetik `SEARCH_SAHI_TILE_768` ve `TRACK_SQUARE_ROI` runner'ı.
3. ✅ Tile/ROI koordinat dönüşümü, padding ve upsample regresyon testleri.
4. ✅ Cross-tile GREEDYNMM/IOS ve temporal `2-of-3` confirmation testleri.
5. ✅ HSV konturundan bağımsız model izi, kararlı `MODEL-*` kimliği ve LiDAR
   gelene kadar fail-closed `rangeM=0` taşıma sözleşmesi.
6. ⏳ Aynı sentetik sahnede legacy full-frame ↔ SAHI ↔ ROI detector replay.
7. ⏳ YOLOv8s ↔ YOLOv8n ve GREEDYNMM/IOS ↔ NMS/IOU ablation'ı.
8. ✅ Picamera2 main/lores dual-stream capture ve metadata sözleşmesi.
9. ⏳ Pi üzerinde main/lores FPS, bellek, latency ve dropped-frame ölçümü.
10. ⏳ Gerekirse `ScalerCrop` ile aynı benchmark'ın tekrarı.
