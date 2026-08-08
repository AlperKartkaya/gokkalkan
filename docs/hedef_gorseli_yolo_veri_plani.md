# Temsili Hedef Görselleri — Veri Seti, YOLO ve Hailo-8 Planı

Bu belge, Görev Kabiliyeti Gösterimi Videosu için maket yerine basılı hedef
görselleri kullanılacağı kararını yazılım/veri toplama planına dönüştürür.
Kanonik seed dosyaları
[`perception/assets/target_prints/`](../perception/assets/target_prints/)
altındadır.

## 1. Ana sonuç

Altı sunum görselini augmentation ile çoğaltıp rastgele train/test ayırmak yeterli
değildir. Böyle bir deney aynı dört kaynağın neredeyse kopyalarını iki tarafa
da dağıtır ve gerçekte olmayan yüksek doğruluk üretir. Doğru sıra şöyledir:

1. baskı hedefinin fiziksel ölçüsü, malzemesi ve hedeflenen vurma noktası
   kesinleştirilir;
2. hedefler gerçek Camera Module 3 Standard ile farklı koşullarda kaydedilir;
3. capture session'ları train/validation/test olarak **grup bazlı** ayrılır;
4. augmentation yalnız train grubuna uygulanır;
5. model önce masaüstünde, sonra ONNX/quantized modelde, en son Hailo-8 HEF
   üzerinde aynı sabit test setiyle ölçülür.

## 2. Bu altı sunum varlığının rolü

Şartname sayfa 14 geometrisinden üretilen dört tip ve altı renk/tip varyantı:

- baskı prototipi;
- sentetik kompozisyon için seed;
- sınıf kimliği ve dosya sözleşmesi;
- ilk HSV/şekil/YOLO fizibilite deneyi

olarak kullanılabilir. Ancak PDF içindeki JPEG şerit de nihai eğitim master'ı değildir. Nihai basılı örneğin gerçek kamera kayıtları ana veri kaynağı yapılmalıdır; `manifest.json` kaynak sayfasını, renkleri ve hash'leri sabitler.

## 3. Önerilen algı mimarisi

### 3.1. Hızlı ve düşük riskli başlangıç

1. Mevcut HSV adayı çıkarımı kırmızı/camgöbeği bölgeyi ve merkezini bulmaya devam
   eder. Siyah baskı zemini bu klasik yöntemi kolaylaştırabilir.
2. Küçük bir **YOLOv8n dört sınıflı detector** `F16`, `Helikopter`,
   `Balistik Füze`, `Mini/Micro İHA` tipini ve bounding box'ı üretir.
3. Takipçi ardışık karelerde kimliği sabitler; tek karelik sonuç angajman kararı
   olmaz.
4. Dost/düşman rengi ayrı HSV/renk kapısından gelir. YOLO tip çıktısı renk
   kararının yerine geçmez.

YOLOv8n burada nihai mimari değil, Hailo-8 için resmi Model Zoo v2.x hattında
hazır karşılığı bulunan ölçülebilir bir başlangıçtır. “En yeni YOLO” sürümü
yalnız masaüstünde çalışıyor diye seçilmemeli; ONNX → quantization → HEF zinciri
önce doğrulanmalıdır.

### 3.2. YOLO zorunlu mu?

Hayır. Hedefler hep bu dört sabit baskı olacaksa şu baseline da ölçülmelidir:

- HSV ile renk maskesi ve connected component;
- kontur/Hu moment veya normalize template benzerliği ile tip;
- centroid/optical flow ile takip.

Bu baseline daha az veriyle çalışabilir ve YOLO için karşılaştırma/fallback
sağlar. Kabul ölçütlerini geçen en basit çözüm tercih edilmelidir.

### 3.3. Maket merkezi atış noktası değildir

Maket yalnız teşhis içindir; değerlendirme maketin altındaki yaklaşık `12–16 cm` kırmızı balonun patlatılması üzerinden yapılır. Bu nedenle veri etiketi en az üç ayrı kavram tutmalıdır:

- `target_bbox`: maket algılama/takip alanı;
- `balloon_bbox` veya `balloon_center`: fiziksel imha noktası;
- `target_balloon_link`: balonun hangi makete ait olduğu.

Aşama 3'te dost maketin balonu da kırmızıdır. `friendFoe`, maket renginden çıkarılır ve ilişkili balona miras edilir; yalnız kırmızı balon tespiti ateş yetkisi vermez. İlişkilendirme güveni yoksa Safety Gate fail-closed kalır. Balon merkezi, kamera→namlu extrinsic ve menzile bağlı balistik düzeltmeden sonra taret komutuna dönüşür.

## 4. Gerçek veri toplama matrisi

Her kayıt oturumu aşağıdaki metadata'yı taşımalıdır:

- hedef tipi ve baskı rengi;
- baskı sürümü/hash'i, fiziksel genişlik/yükseklik, yazıcı ve malzeme;
- Camera Module 3 çözünürlüğü, crop, exposure, gain, white balance ve autofocus;
- hedef mesafesi, yatay/düşey bakış açısı ve taret yaw hızı;
- iç/dış ortam, aydınlatma, parlama ve arka plan kimliği;
- capture session/video/frame kimliği.

Başlangıç kapsama matrisi:

- menzil: yakın örnekler ile birlikte özellikle `5 / 10 / 15 m`;
- yatay açı: `0°, ±10°, ±20°, ±30°`;
- yükseklik/perspektif: beklenen montaj sapmalarını kapsayan en az üç seviye;
- hareket: durağan, yavaş yaw ve yarışmadaki en yüksek beklenen yaw;
- ışık: homojen, düşük ışık, yandan ışık/parlama;
- negatifler: boş parkur, stand, kablo, insan, kırmızı/camgöbeği ilgisiz nesne,
  kısmi hedef ve kadraj dışı hedef.

Video kareleri ardışık biçimde topluca kullanılmamalıdır. Örneğin 30 FPS
kaydın her karesi veri sayısını büyütür fakat yeni bilgi eklemez; zaman aralıklı
örnekleme ve blur/poz değişimi seçimi yapılmalıdır.

## 5. Split stratejisi

Önerilen başlangıç oranı `70/15/15` olabilir, fakat ayırma birimi görüntü değil
`capture_session_id + print_instance_id + background_id` grubudur.

- Aynı videonun veya aynı sentetik kompozisyonun varyantları yalnız tek split'te
  kalır.
- Test setine augmentation uygulanmaz.
- En az bir aydınlatma/arka plan oturumu yalnız test için saklanır.
- Her sınıf ve renk varyantı validation/test içinde bulunur.
- Split manifesti seed ve dosya hash'leriyle sürümlenir.

## 6. Augmentation: yapılacaklar ve yapılmayacaklar

### Uygun augmentation'lar

- fiziksel baskı düzlemini temsil eden sınırlı homography/perspective;
- gerçek mesafe→piksel büyüklüğüne göre scale ve translation;
- exposure, gamma, contrast, white balance ve siyah baskı parlaklığı;
- sensor noise, JPEG/video compression, defocus ve ölçülmüş motion blur;
- kısmi örtülme, baskı eğilmesi ve kontrollü glare;
- bütün sınıflar için ayrı, kontrollü kırmızı/camgöbeği baskı varyantları.

### Kaçınılacak augmentation'lar

- rastgele hue kaydırarak dost/düşman rengini bozmak;
- yarışmada oluşmayacak vertical flip veya aşırı perspective/shear;
- yalnız dört seed'i tekrar tekrar kullanan agresif mosaic/mixup;
- split öncesi augmentation;
- hedefi gerçek baskıda olmayacağı şekilde arka plandan kesip “uçan 3B nesne”
  gibi kompoze etmek.

Ultralytics küçük veri setlerinde mosaic'in aynı görüntüyü bir kompozisyonda
birden fazla kez seçebileceğini belirtmektedir. Bu nedenle başlangıçta mosaic ve
mixup kapalı/düşük tutulmalı, katkıları ayrı ablation ile ölçülmelidir.

## 7. Renk, tip ve balon ayrımı

Kanonik sunum sınıfları altı adet olsa da çalışma zamanı sözleşmesi iki ekseni ayrı tutar:

- `targetType`: F16 / Helikopter / Balistik Füze / Mini-Micro İHA;
- `friendFoe`: kırmızı maket=Düşman, camgöbeği maket=Dost;
- `objectRole`: maket veya balon.

Pratik bir YOLO başlangıcı altı maket sunum sınıfına ek bir `balloon` sınıfı kullanabilir. Post-process, altı sınıfı mevcut `targetType + friendFoe` sözleşmesine dönüştürür. Test seti mutlaka camgöbeği dost maketin altındaki kırmızı balonu içerir; bu balonun bağımsız düşman izine dönüşmesi kritik hata sayılır.

## 8. Baskı ve optik çözünürlük

Nihai baskı genişliği bilinmeden `imgsz=640 yeterlidir` denemez. Yaklaşık hedef
genişliği piksel cinsinden şu ilişkiyle önceden kontrol edilmelidir:

```text
target_px ≈ frame_width_px × target_width_m
            / (2 × distance_m × tan(horizontal_fov / 2))
```

Camera Module 3 Standard için nominal yatay FoV `66°` olsa da son karar gerçek
intrinsics/crop ile verilmelidir. 15 m görüntüsünde hedef çok küçük kalıyorsa
daha büyük modelden önce yüksek çözünürlüklü capture, ROI/crop veya iki aşamalı
arama değerlendirilmelidir.

Siyah baskı için mat yüzey tercih edilmesi, toner/mürekkep parlama deneyi ve
gerçek baskının kamera altında renk kalibrasyonu gerekir. Ekran görüntüsünü
yazılımla büyütmek baskı ayrıntısını artırmaz.

## 9. Eğitim ve Hailo-8 kabul kapıları

1. Pretrained küçük detector ile transfer learning baseline.
2. FP32/PyTorch test seti sonucu.
3. ONNX sonucu ve FP32'ye göre fark.
4. Temsili **gerçek kamera kareleriyle** quantization calibration.
5. Hailo Model Zoo `v2.x` + uyumlu Dataflow Compiler `v3.x` ile Hailo-8 HEF.
6. Aynı test setinde HEF doğruluğu ve gerçek Pi 5 + AI HAT+ gecikmesi.
7. Uzun süreli camera→Hailo→track→backend soak testi.

Model kabulü yalnız mAP ile yapılmaz. En az şu metrikler kaydedilir:

- sınıf başına precision/recall ve özellikle 15 m recall;
- negatif videoda false positive/dakika;
- track kaybı ve yeniden edinme süresi;
- `aimPoint` piksel/açı hatası;
- uçtan uca p50/p95 gecikme ve FPS;
- FP32→ONNX→HEF accuracy düşüşü;
- düşük ışık, blur, glare ve kısmi görünürlük sonuçları.

## 10. Güvenlik sınırı

YOLO/Hailo çıktısı hiçbir zaman tek başına ateş yetkisi değildir. Güncel fiziksel
kamera ölçümü, güvenilir track, geçerli LiDAR menzili, ölçülmüş hız gerekiyorsa
rota kestirimi, taret kalibrasyonu, balistik çözüm ve backend Safety Gate birlikte
geçmeden fiziksel atış yapılmaz. `Bilinmeyen` veya düşük güvenli sınıf fail-closed
kalır.

## 11. Bir sonraki uygulanabilir paket

1. Altı kanonik varyantın fiziksel baskı ölçüsü ve malzemesini kilitle.
2. Maket bbox, balon merkezi ve maket→balon ilişki etiketini tanımla.
3. Gerçek Camera Module 3 capture protokolü ve metadata manifestini ekle.
4. Grup bazlı split üreten, seed'i sabitleyen dataset builder yaz.
5. Klasik HSV/template baseline ile YOLOv8n baseline'ı aynı testte karşılaştır.
6. Kazanan modeli ONNX→HEF hattına al ve AI HAT+ üzerinde kabul et.

## 12. Resmî teknik referanslar

- Ultralytics YOLO dataset biçimi ve split alanları:
  <https://docs.ultralytics.com/datasets/detect/>
- Ultralytics augmentation davranışları:
  <https://docs.ultralytics.com/guides/yolo-data-augmentation/>
- Hailo Model Zoo ve Hailo-8 sürüm uyumluluğu:
  <https://github.com/hailo-ai/hailo_model_zoo>
- Raspberry Pi AI HAT+ kamera entegrasyonu:
  <https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html>
- Picamera2 Hailo/HEF kullanım sınırı:
  <https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf>
