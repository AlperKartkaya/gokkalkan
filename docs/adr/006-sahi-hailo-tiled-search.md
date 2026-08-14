# ADR-006 — Hailo-8 Üzerinde SAHI Tabanlı Arama ve Kare ROI Takibi

- **Durum:** Kabul edildi
- **Tarih:** 15 Ağustos 2026
- **İlgili iş paketi:** WP-02 Otonom Tespit ve Takip, WP-03 Dost-Düşman + Menzil
- **Donanım:** Raspberry Pi 5 + Raspberry Pi AI HAT+ 26 TOPS / Hailo-8
- **Kamera:** Raspberry Pi Camera Module 3 Standard
- **Model girdisi:** `640×640`

## Bağlam

Camera Module 3 Standard'ın nominal `66°` yatay görüşünde `1280×720` tam
görüntünün `640×640` modele letterbox edilmesi yalnız `640×360` aktif görüntü
alanı bırakır. CAD ölçüleriyle yapılan izdüşüm hesabında 15 m'deki hedefler bu
yolda yaklaşık şu büyüklüklere düşer:

| Hedef | Merkez rota | Yaklaşık 3 m yan ofset |
| --- | ---: | ---: |
| F16 | `9.9×6.8 px` | `12.7×6.7 px` |
| Helikopter | `12.9×8.5 px` | `16.1×8.3 px` |
| Drone | `9.4×8.1 px` | `11.5×7.9 px` |
| Füze | `3.5×17.3 px` | `4.7×16.9 px` |

Bu değerler mesh sınır kutusundan hesaplanan iyimser yaklaşık değerlerdir;
gerçek silüet, hareket bulanıklığı ve kamera işleme zinciri görünür bilgiyi daha
da azaltabilir. İlk tespitin bu tek küçültülmüş görüntüye bağlı olması kabul
edilmez. ROI takip hattı ilk tespit olmadan devreye giremediği için bu yalnız
model doğruluğu değil, sistem mimarisi problemidir.

AI HAT+ 26 TOPS, Hailo-8 kullanır ve Raspberry Pi tarafından daha büyük ağlar,
yüksek throughput ve paralel iş yükleri için sunulur. Hailo Model Zoo'nun ham
Hailo-8 ölçümleri `640×640` YOLOv8n ve YOLOv8s için tile tabanlı aramayı makul
bir aday yapar; ancak bu ölçümler Pi kamera, PCIe, kopyalama ve postprocess
maliyetini kapsayan uygulama FPS'i değildir. Nihai frekans gerçek Pi üzerinde
ölçülmeden doğrulanmış sayılmaz.

SAHI, yüksek çözünürlüklü görüntüyü örtüşmeli parçalara ayırma, tahminleri tam
görüntü koordinatına taşıma ve NMS/NMM ile birleştirme işlerini hazır sağlar.
SAHI'nin resmî Hailo modeli yoktur; Hailo HEF çağrısı için repo-yerel bir adapter
gereklidir.

## Karar

### 1. Birincil arama yolu

Tam görüntüyü tek seferde `640×360` aktif alana küçültmek birincil arama yolu
olmayacaktır.

```text
Camera Module 3 main: 2304×1296
  → SAHI: 768×768 kare tile, %25 yatay/dikey overlap
  → 8 tile / sweep
  → her tile 640×640'a INTER_AREA ile küçültme
  → Hailo-8 batch/asenkron inference
  → tam görüntü koordinatına geri dönüş
  → sınıf-duyarlı cross-tile birleştirme
```

SAHI'nin kenara hizalama davranışıyla nominal tile başlangıçları:

```text
x = [0, 576, 1152, 1536]
y = [0, 528]
```

Son yatay ve dikey overlap, görüntü sınırına hizalama nedeniyle nominal `%25`
değerinden büyük olabilir. Tile listesi elle sabitlenmeyecek; SAHI
`get_slice_bboxes` çıktısı manifestte saklanacaktır.

`768→640` ölçeği `0.8333`'tür. 15 m yan rota örneğinde modele ulaşan yaklaşık
boyutlar:

| Hedef | `768→640` tile içindeki yaklaşık boyut |
| --- | ---: |
| F16 | `37.9×20.1 px` |
| Helikopter | `48.3×24.9 px` |
| Drone | `34.3×23.8 px` |
| Füze | `14.1×50.8 px` |

Bu büyüklükler tek full-frame letterbox yolundan belirgin biçimde daha uygundur.

### 2. SAHI başlangıç parametreleri

```text
slice_height                 = 768
slice_width                  = 768
overlap_height_ratio         = 0.25
overlap_width_ratio          = 0.25
perform_standard_pred        = false
postprocess_type             = GREEDYNMM
postprocess_match_metric     = IOS
postprocess_match_threshold  = 0.50
postprocess_class_agnostic   = false
batch_size                   = 8
```

- `perform_standard_pred=false`: Dokuzuncu, küçültülmüş full-frame inference
  runtime doğruluk yolu değildir. Yalnız ablation/teşhis profilinde açılabilir.
- `GREEDYNMM + IOS`: Tile sınırındaki kısmi ve tam kutuların birleştirilmesi için
  başlangıç varsayılanıdır.
- `NMS + IOU` aynı sabit replay setinde zorunlu ablation'dır; gerçek veri daha
  iyi sonuç gösterirse yapılandırma ile seçilebilir.
- Birleştirme sınıf-duyarlıdır. Aynı fiziksel bölgede dost ve düşman sınıfları
  çakışırsa sonuçlardan biri sessizce silinmez; track `AMBIGUOUS_CLASS` olur ve
  atış adayı üretemez.

### 3. Arama frekansı ve latest-wins zamanlayıcı

- Başlangıç hedefi: `10 tam sweep/s = 80 tile inference/s`.
- Kabul alt sınırı: `8 tam sweep/s = 64 tile inference/s`.
- Araştırma üst hedefi: `12 tam sweep/s = 96 tile inference/s`.
- Kamera `30 FPS` kalabilir; her kamera karesi tam SAHI sweep'e girmez.
- Zamanlayıcı yalnız en yeni tamamlanmış main kareyi seçer. Eski frame'ler
  kuyrukta birikmez; geç kalan arama sonucu güncel nişan girdisi yapılmaz.
- Hedef `1 m/s` ve 15 m örneğinde main görüntüde yaklaşık `118 px/s` ilerler.
  `10 Hz` sweep aralığında bu yaklaşık `12 px`, `8 Hz` aralığında yaklaşık
  `15 px` hareket demektir.

Gerçek Hailo kabulünde yalnız NPU süresi değil şu süreler ayrı ölçülür:

```text
capture → tile view/copy → resize → Hailo queue → inference
→ Hailo NMS decode → SAHI merge → temporal confirmation
```

### 4. Motion ve HSV'nin rolü

Motion detection ve mevcut HSV renk adayları **birincil doğruluk kapısı değildir**.
SAHI sweep hareketsiz, başlangıçta kadrajda bulunan veya renk eşiği dışında kalan
hedefi de aramaya devam eder.

Motion/HSV yalnız hızlı yol üretir:

```text
lores 1280×720 @ 30 FPS
  → motion OR HSV proposal
  → main 2304×1296 koordinatına 1.8× dönüşüm
  → proposal merkezli 768×768 kare crop
  → sıradaki normal sweep'i beklemeden öncelikli Hailo inference
```

Ardışık tek kare `absdiff` yeterli kabul edilmez. Başlangıç araştırması:

- `t` ile `t-3` / `t-5` farkı;
- MOG2/KNN background subtraction;
- taret hareket ederken encoder bilgisiyle proposal bastırma veya görüntü
  hareketi telafisi;
- adayın kısa süreli temporal persistence kaydı.

Motion veya HSV sonucu doğrudan hedef, dost/düşman ya da atış kararı değildir.

### 5. Temporal ilk tespit

Başlangıç search confidence eşiği araştırmada `0.20–0.25` aralığında denenir.
Düşük eşikli tek kutu track başlatmaz.

Başlangıç doğrulama sözleşmesi:

- son üç tam sweep'in en az ikisinde uzamsal olarak tutarlı detection;
- sınıf bilgisi gereken aşamada sınıf tutarlılığı;
- çakışan dost/düşman sonucu varsa `AMBIGUOUS_CLASS`;
- eski frame sonucu yaş sınırını aşıyorsa atılır;
- yalnız doğrulanmış detection track durum makinesine geçer.

### 6. Takip yolu

SAHI aramasından sonra hedefi yeniden `1152×648 → 640×360` gibi daha küçük
temsile düşürmek yasaktır. Aramada büyütülen hedef track moduna geçince
küçülmemelidir.

Varsayılan takip crop'u modelle aynı oranlı kare bölgedir:

```text
main 2304×1296
  → predicted target merkezi çevresinde 768×768 kare ROI
  → 640×640 model girdisi
  → tam görüntü koordinatına geri dönüş
```

Takip politikası:

- normal: `768×768`;
- ilk kayıp veya bbox'ın ROI'nin `%50`'sini aşması: `960×960`;
- ikinci kayıp: `1152×1152`;
- tekrar bulunursa kademeli olarak `768×768`;
- belirlenen stale sınırında tekrar SAHI search;
- ROI kaynak boyutu `640×640` altına düşmez; model öncesi upsample yapılmaz.

Tracking sırasında hesap bütçesi uygunsa round-robin global yeniden arama
sürdürülür. Başlangıç adayı her iki track karesinde bir tile'dır; böylece sekiz
tile yaklaşık `0.53 s` içinde yeniden taranır.

### 7. Hailo ve SAHI entegrasyon sınırı

SAHI `0.11.36`, mevcut YOLO eğitim kilidindeki OpenCV `4.11` ile uyumlu offline
referans/eğitim bağımlılığı olarak `requirements/training-dev.lock` içinde
sabitlenmiştir. SAHI `0.12.x`, pip üzerinden OpenCV `>=4.12` ve Python 3.11'de
NumPy 2.x zinciri getirdiği için Pi'nin apt tabanlı Picamera2/OpenCV ortamına
doğrudan kurulmaz.

Pi runtime'ında Ultralytics `.pt` inference çalıştırılmayacaktır. Akış:

```text
SAHI offline slicing/postprocess referansı
  ↕ parity testli repo-yerel tile/merge sözleşmesi
HailoSahiAdapter / HailoRT HEF batch inference
```

Adapter sorumlulukları:

- `768×768` NumPy tile'ı `640×640` model tensörüne dönüştürmek;
- batch/asenkron Hailo çağrısı;
- HEF NMS çıktısını repo `Detection` sözleşmesine normalize etmek;
- label map ve confidence filtresini tek yerde uygulamak;
- tile başlangıç koordinatını iki kez uygulamamak;
- model hash'i, HailoRT sürümü ve batch ölçümlerini health/telemetriye yazmak.

Stock `get_sliced_prediction` eğitim makinesinde doğruluk referansı olarak
kullanılır. Canlı akışta `sahi_geometry.py`, SAHI ile aynı boundary-aligned tile
koordinatlarını ve GREEDYNMM/IOS sözleşmesini dependency-light olarak çalıştırır;
`sahi_search.py` generic dosya-I/O/PIL yoluna girmeden NumPy batch scheduler'ını
işletir. Böylece Pi'de ikinci bir pip OpenCV kurulmaz.

### 8. Model adayları

26 TOPS Hailo-8 nedeniyle tek zorunlu aday YOLOv8n değildir:

1. **Birincil doğruluk adayı:** YOLOv8s, `640×640`, SAHI tile eğitimi.
2. **Throughput fallback:** YOLOv8n, aynı veri/split/preprocess.

İki model aynı world-group split ve real-only validation üzerinde
karşılaştırılır. YOLOv8s `10 Hz` sweep kapısını sağlarsa daha yüksek doğruluk
adayı olarak kalır. Sağlamazsa önce batch/kopya/pipeline iyileştirilir; yine
sağlamazsa YOLOv8n seçilir. Model değişikliği tile ve koordinat sözleşmesini
değiştirmez.

## Sentetik veri kararı

### 1. Fiziksel işlem sırası

Kamera etkileri tile başına bağımsız uygulanmayacaktır:

```text
ideal 2304×1296 CAD render
→ lens/sensör/ISP araştırma profili
→ hareket blur'u ve exposure etkisi
→ runtime main-frame temsili
→ SAHI search tile veya track ROI crop
→ 640×640 resize
→ annotation dönüşümü
```

Önce tile üretip sonra her tile'a ayrı rastgele blur/noise uygulamak aynı kamera
karesinde fiziksel olarak tutarsız sonuç doğurur.

### 2. Dataset görünüm aileleri

Her temel CAD dünya için türevler aynı `worldId/groupId/split` içinde kalır.

#### `SEARCH_SAHI_TILE_768`

- SAHI ile üretilen sekiz tile;
- `768×768 → 640×640`;
- bbox/mask tile sınırında kırpılır;
- `visibleFraction`, `edgeDistancePx` ve `truncatedBySlice` kaydedilir;
- hedef içeren bütün tile'lar korunur;
- sınırda kesilen hedef tile'ları zorunlu hard-case'tir;
- bütün hard-negative tile'lar korunur;
- her frame'deki kolay boş tile'lardan deterministik en fazla iki tanesi tutulur.

#### `TRACK_SQUARE_ROI`

- `768×768` normal takip crop'u;
- predicted center gecikmesi ve bounded center jitter;
- kayıp kurtarma için `960×960` ve `1152×1152` alt kümeleri;
- önceki kare merkezi, bir kare gecikme ve hız tahminli merkez ayrı bucket;
- hedefin ROI kenarına yaklaşması ve kısmi truncation örnekleri.

#### `FULL_FRAME_LEGACY_ABLATION`

- Mevcut `1280×720 → 640×360 letterbox` örnekleri yalnız karşılaştırma ve teşhis
  alt kümesinde korunur;
- runtime birincil search datası değildir;
- tam sentetik veri hacmini gereksiz büyütmez.

#### `MOTION_SEQUENCE`

- Kamera kaydı `30 FPS` zaman tabanında üretilir;
- search sweep örnekleri her üç karede bir (`10 Hz`) işaretlenir;
- track ROI örnekleri `30 Hz` türetilir;
- `1 m/s` üst tasarım örneği dahil farklı hız bucket'ları taşınır;
- motion proposal ground truth'u, YOLO class ground truth'undan ayrı tutulur.

### 3. Slicing-aided fine-tuning

Model yalnız full-frame renderlarla eğitilip runtime'da tile görmeyecektir.
SAHI makalesindeki slicing-aided fine-tuning yaklaşımı uygulanır:

- eğitim ve validation annotation'ları aynı `768/%25` sözleşmesiyle slice edilir;
- tile sınırı ve negatif oranı kontrol edilir;
- tile ve track ROI aileleri birlikte eğitime girer;
- aynı base world'ün tile'ları farklı split'e gidemez;
- sentetik test seti oluşturulmaz; bağımsız gerçek test kapısı korunur.

### 4. Zorunlu metadata

Her türev en az şu alanları taşır:

```text
viewFamily
sourceFrameId / worldId / groupId / split
sourceResolution
sliceRectFullFramePx / roiRectFullFramePx
sliceIndex / sweepId / sweepTimestamp
overlapHeightRatio / overlapWidthRatio
resizeScale
bboxFullFramePx / bboxCropPx / bboxModelPx
visibleFraction / truncatedBySlice / edgeDistancePx
distanceM / viewYawDeg / topSurfaceViewDeg
cameraProfileId / degradationProfileId
```

## Bütünlüklü fallback yolları

### Yol A — Varsayılan

```text
YOLOv8s + 8×768 SAHI + batch 8 + 10 Hz sweep
motion/HSV fast path + 768 kare track ROI
```

Bu yol doğruluk ve Hailo kapasitesini birlikte kullanır.

### Yol B — Aynı geometri, hafif model

```text
YOLOv8n + 8×768 SAHI + batch 8 + 10–12 Hz sweep
```

YOLOv8s end-to-end `10 Hz` kapısını sağlayamazsa ilk model fallback'idir.
Dataset, SAHI ve takip kodu değişmez.

### Yol C — Daha az tile

```text
6×960 SAHI + %25 overlap + 960→640
```

15 m yan rota yaklaşık model boyutları:

| Hedef | `960→640` yaklaşık boyut |
| --- | ---: |
| F16 | `30.3×16.1 px` |
| Helikopter | `38.6×19.9 px` |
| Drone | `27.5×19.0 px` |
| Füze | `11.3×40.7 px` |

Bu yol `8×768` kadar ayrıntı korumaz, fakat tek full-frame letterbox'tan hâlâ
belirgin biçimde iyidir. Pi kopya/preprocess sınırı nedeniyle sekiz tile kabul
frekansına ulaşamazsa ikinci geometri fallback'idir.

Saf motion/HSV proposal yolu ayrı bir fallback değildir; hareketsiz veya yanlış
renkli hedefe kör olabileceği için periyodik deterministik SAHI sweep her zaman
kalır.

## Kabul metrikleri

Karar yalnız mAP veya NPU FPS ile verilmez:

- sınıf ve mesafe bazında first-detection recall;
- 15 m recall;
- `time-to-first-detection` p50/p95;
- tam sweep p50/p95 ve en eski sonuç yaşı;
- tile sınırındaki hedef recall'u;
- stationary-at-start recall;
- motion/HSV proposal false-positive/dakika;
- dost→düşman kritik karışıklık;
- cross-class ambiguity sayısı;
- track'e geçişte bbox/model-piksel sürekliliği;
- track kaybından yeniden yakalama süresi;
- CPU, bellek, sıcaklık ve dropped-frame oranı.

Fiziksel başlangıç kapıları:

- YOLOv8s Yol A: tam sweep p95 `≤100 ms`;
- kabul alt sınırı: tam sweep p95 `≤125 ms`;
- stale frame kuyruğu: `0`, latest-wins;
- track ROI: hedeflenen `30 FPS` veya ölçülmüş gerekçeli alt sınır;
- friendly-linked balloon fire candidate: `0`;
- fiziksel 15 m recall: mevcut implementasyon planındaki real-only kabul
  kapısını karşılar.

Bu değerler sentetik smoke ile fiziksel olarak doğrulanmış sayılmaz.

## Uygulama sırası

1. **Sözleşme ve bağımlılık**
   - Offline eğitim ortamına `sahi==0.11.36` exact lock'unu ekle.
   - `config/perception/search.toml` içinde tile, overlap, sweep ve postprocess
     alanlarını doğrulanan şemayla tanımla.
   - Elle yazılmış tile koordinatı değil SAHI çıktısı kullanıldığını test et.
2. **Sentetik slicing**
   - `apply_camera_pipeline.py` hattına `SEARCH_SAHI_TILE_768` ve
     `TRACK_SQUARE_ROI` türevlerini ekle.
   - Maske/bbox dönüşümü, boundary truncation, easy-negative örneklemesi ve
     group-split değişmezliğini test et.
3. **Offline detector referansı**
   - Eğitim makinesinde SAHI + Ultralytics ile sliced inference replay oluştur.
   - `GREEDYNMM/IOS` ve `NMS/IOU` sonuçlarını sabit manifestte karşılaştır.
4. **Model deneyi**
   - Aynı sliced train/val setinde YOLOv8s ve YOLOv8n eğit.
   - 5/10/15 m, tile-boundary ve class-conflict metriklerini raporla.
5. **Hailo adapter**
   - `perception/src/hailo_sahi_adapter.py` ile HEF batch çıktısını SAHI
     tahminlerine dönüştür.
   - Fake/injected batch runner ile Pi olmadan koordinat ve hata testlerini yaz.
6. **Arama scheduler**
   - `perception/src/sahi_search.py` içinde latest-wins sweep, batch 8,
     timestamp yaş kapısı ve cross-tile merge uygula.
   - `2-of-3` temporal confirmation ve `AMBIGUOUS_CLASS` kapısını ekle.
7. **Takip durumu**
   - `zoom_controller.py` içindeki legacy state'leri kare ROI state'leriyle
     değiştir; regresyon fixture'larını koru.
   - Full-frame koordinat geri dönüşünü tracker/backend bridge'e bağla.
8. **Motion/HSV hızlı yolu**
   - Önce deterministik SAHI yolu çalıştıktan sonra proposal önceliklendirmesini
     ekle. Bu sıra, motion başarısızlığının arama doğruluğunu bloke etmesini önler.
9. **Fiziksel benchmark — AR-10**
   - Yol A/B/C'yi gerçek Pi 5 + AI HAT+ 26 TOPS üzerinde ölç.
   - Kazananı yalnız full-sweep p95, first-detection recall ve track latency
     kapıları birlikte sağlandığında runtime default'u yap.

## Sonuçlar

- Küçük hedef ilk tespiti artık tek küçültülmüş full-frame inference'a bağlı
  değildir.
- Model tensörünün tamamı arama tile'ı ve track ROI'de aktif kullanılır.
- Hesap maliyeti tile sayısıyla artar; AI HAT+ kapasitesi bunun için kullanılır.
- SAHI offline eğitim/referans bağımlılığı ve parity-testli Hailo adapter işi getirir.
- Motion/HSV optimizasyon sağlar ama doğruluk kapısı olmaz.
- Eski `SEARCH_FULL_FRAME → 1.5×/2× ROI` durumu bu ADR ile geçersizdir.
- Fiziksel Hailo benchmark'ı Yol A/B/C arasındaki son runtime seçimini yapar;
  tek full-frame küçültme otomatik fallback değildir.

## Referanslar

- [SAHI dokümantasyonu — sliced inference](https://obss.github.io/sahi/guides/sliced-inference/)
- [SAHI model entegrasyonları](https://obss.github.io/sahi/guides/models/)
- [SAHI 0.11.36 — PyPI](https://pypi.org/project/sahi/0.11.36/)
- [Slicing Aided Hyper Inference and Fine-tuning for Small Object Detection](https://arxiv.org/abs/2202.06934)
- [Raspberry Pi AI HAT+ dokümantasyonu](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html)
- [Hailo Model Zoo — Hailo-8 object detection modelleri](https://github.com/hailo-ai/hailo_model_zoo/blob/master/docs/public_models/HAILO8/HAILO8_object_detection.rst)
