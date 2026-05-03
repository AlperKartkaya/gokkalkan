# Gökkalkan Teknik Yönelim ve Yazılım Mimarisi

Bu doküman, Gökkalkan yazılımının teknik yönünü `docs/sartname_v5.pdf` şartnamesine göre belirler. Şartname ile bu doküman arasında çelişki olursa şartname geçerlidir. PDF’in metin kopyası `docs/sartname_v5.txt` dosyasında tutulur.

## 1. Şartnameye Göre Sistem Hedefi

Gökkalkan, TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması için geliştirilen; kullanıcı denetimli manuel mod, otonom hedef tespit/takip, dost-düşman ayrımı, güvenli atış izni, acil durdurma ve görev kaydı özelliklerini birleştiren bir sistemdir.

Yazılım tasarımı öncelikle şu yarışma gerçeklerine göre optimize edilmelidir:

- Sistem her boyutta `100 cm` sınırının altında kalmalıdır; en uzun boyut `60 cm` veya altındaysa ebat puanı alınır.
- Hedefler yarışmada yaklaşık `5 m`, `10 m` ve `15 m` menzillerde değerlendirilir.
- Sistem manuel ve otonom modları desteklemelidir; mod geçişleri kullanıcı denetiminde olmalıdır.
- Hareket ve atış için ayrı yasak bölgeler tanımlanmalıdır: `harekete yasak alan` ve `atışa yasak alan`.
- Sistemde güvenli konumda, dışarıya çıkan kabloyla erişilebilen fiziksel `Acil Durdur` butonu zorunludur.
- Patlayıcı hedef imha çözümü yasaktır.
- Açıkta kablo, uygunsuz elektriksel bağlantı ve keskin gövde noktaları kabul edilmez.

## 2. Yarışma Aşamaları ve Yazılım Gereksinimleri

### 2.1. Aşama 1 — Farklı Menzillerde Duran Hedef İmhası

Bu aşama tamamen manuel modda yapılır. Kullanıcı arayüzü üzerinden yönlendirme ve ateş emri verilir; her atıştan sonra yeni hedefe yönelme ve yeniden ateşleme kullanıcı komutuyla başlatılır.

Yazılım gereksinimleri:
- Hassas pan/tilt yönlendirme ve kullanıcı komutu ile atış izni.
- Yarışma öncesi verilen hedef sırasını operatöre açık gösterebilme.
- Yanlış hedef/sıra riskini azaltan arayüz uyarıları.
- `5 dakika` görev süresi ve kalan süreyi kayıt altına alma.
- Aşama geçiş eşiği: en az `30 puan`.

### 2.2. Aşama 2 — Sürü Saldırısı ve Hedeflerin İmhası

Bu aşama otonom modda yapılır. Sistem açıldıktan sonra kullanıcı sistemi otonom moda alır; otomatik hedef tespit, takip ve imha görevleri çalışır. Şartname bu aşamada hedef tipi sınıflandırması beklemez.

Yazılım gereksinimleri:
- Üç koldan yaklaşan hedefleri tespit ve takip etme.
- Her turda parkurdaki hedefleri tur tamamlanmadan imha etmeye yönelik önceliklendirme.
- Hedef vuramama durumlarını kaydetme; 3 tur boyunca hedef vuramama başarısızlık sebebidir.
- Aşama geçiş eşiği: en az `20 puan`.

### 2.3. Aşama 3 — Farklı Katmanlardaki Hareketli Hedeflerin İmhası

Bu aşama otonom modda dost-düşman ayrımı gerektirir. Her turda 1 düşman hedef ve 2 dost unsur yaklaşır; sistem düşman hedefi tespit edip hedef tipine göre uygun menzilde imha etmelidir.

Yazılım gereksinimleri:
- Dost hedefi vurmamak için hedef tipi, renk/şekil ve görev bağlamını birlikte değerlendirme.
- Hedef tipine göre menzil kapısı uygulama:
  - F16: `10–15 m` aralığında imha puanlanır.
  - Helikopter ve Balistik Füze: `5–15 m` aralığında imha puanlanır.
  - Mini/Micro İHA: `0–15 m` aralığında imha puanlanır.
- Dost hedef vurma ve düşman hedef vuramama durumlarını ceza olarak kaydetme.
- 3 ardışık tur boyunca düşman hedef vuramama başarısızlık sebebidir.
- Başarı eşiği ve ödül sıralamasına girebilme koşulu: Aşama 3’ten en az `10 puan`.

## 3. Görev Kabiliyeti Videosu İçin Yazılım Kanıtları

KTR aşamasını geçen ekiplerden tek YouTube videosu ile görev kabiliyeti gösterimi beklenir. Video `720p+`, `2–5 dakika`, tek link ve şartnamedeki yetenek sırasına uygun olmalıdır. Yazılım, bu video için aşağıdaki kanıtları üretmeyi kolaylaştırmalıdır:

1. Kullanıcı arayüzü, joystick veya klavye gibi komut arayüzlerinin tüm fonksiyonları.
2. Durağan sistemle `15 m` mesafedeki balonu patlatabilme.
3. Yan ve yükseliş eksenlerinde hareket ederken `Acil Durdur` ile hareketin durması.
4. Ateşleme sırasında `Acil Durdur` ile ateşin kesilmesi.
5. Yan ve yükseliş ekseninde hareket eden hedefi takip edebilme.
6. Opsiyonel: `5 m`, `10 m`, `15 m` menzillerde farklı hedef tiplerini tespit ve sınıflandırma.

## 4. Yazılım Mimarisi

### 4.1. `backend/` — Görev Çekirdeği ve Donanım Denetimi

`backend/` sistemin güvenlik-kritik karar katmanıdır. Burada mod yönetimi, görev durum makinesi, atış izni, hareket sınırları, acil durdurma, donanım haberleşmesi ve telemetri üretimi yer almalıdır.

Temel alt bileşenler:
- **Mode Manager:** Manuel/otonom mod geçişlerini kullanıcı denetimine bağlar.
- **Mission State Machine:** Aşama 1, Aşama 2, Aşama 3 ve video görevlerini ayrı senaryolar olarak yönetir.
- **Safety Gate:** Harekete yasak alan, atışa yasak alan, acil durdurma, kablo/enerji/hakem onayı gibi koşullar sağlanmadan hareket veya atış komutu üretmez.
- **Fire Control Adapter:** İmha mekanizmasına yalnızca güvenlik kapısından geçmiş komut gönderir.
- **Hardware Interface:** Pan/tilt MCU, sensörler ve güvenlik girişleriyle haberleşir.
- **Telemetry Logger:** Zaman damgalı mod, hedef, komut, güvenlik ve atış kayıtları üretir.

### 4.2. `backend/hardware_mock/` — Donanım Simülasyonu

Gerçek donanım bağlanmadan önce pan/tilt hareketi, acil durdurma, atış izni, hedef menzili ve görev senaryoları mock üzerinden denenmelidir. Güvenlik ve görev mantığı önce burada doğrulanmalıdır.

### 4.3. `perception/` — Algı, Takip ve Sınıflandırma

`perception/` kamera verisinden hedef adaylarını üretir. Şartname hedeflerin maket, renk/şekil ve balonla temsil edileceğini söylediği için ilk tercih basit, açıklanabilir ve test edilebilir görüntü işleme olmalıdır; yapay zekâ modeli ancak gerçek hedef görselleri ve saha testleri bunu gerektirirse eklenmelidir.

Önerilen öncelik:
1. Kamera kalibrasyonu, görüntü sabitleme ve gecikme ölçümü.
2. Renk/şekil tabanlı hedef aday çıkarımı.
3. Basit takip: merkez noktası, hız tahmini, hedef geçmişi.
4. Aşama 2 için sınıflandırmasız takip ve önceliklendirme.
5. Aşama 3 için dost-düşman ayrımı, hedef tipi ve menzil kapısı.
6. Gerekiyorsa YOLO/DeepSORT/Hailo gibi model tabanlı yaklaşım.

### 4.4. `frontend/` — Operatör Arayüzü

Arayüz yarışma ve rapor diliyle uyumlu Türkçe olmalıdır. Manuel modda tüm fonksiyonlar kullanıcı girdisiyle yapılacağından arayüz sadece izleme ekranı değil, görev kontrol ekranıdır.

Arayüzde en az şu bilgiler hedeflenmelidir:
- Manuel/otonom mod seçimi ve aktif mod göstergesi.
- Pan/tilt komutları, atış izni durumu ve güvenlik kilidi nedeni.
- Canlı görüntü, hedef kutusu/etiketi ve takip durumu.
- Aşama, tur, süre, hedef sırası ve menzil bilgisi.
- Acil durdurma, harekete yasak alan ve atışa yasak alan durumu.
- Telemetri/log kaydı ve video kanıtı için görev olayları.

### 4.5. `tests/` — Senaryo ve Regresyon Testleri

Testler şartname senaryolarına göre yazılmalıdır. Öncelik, güvenlik kapısının asla yanlışlıkla açılmaması ve görev durum makinelerinin beklenen aşama kurallarını uygulamasıdır.

Örnek test sınıfları:
- Manuel modda kullanıcı komutu olmadan ateş emri çıkmaması.
- Acil durdurma aktifken hareket ve atış komutlarının kesilmesi.
- Atışa yasak alanda hedef olsa bile ateş izni verilmemesi.
- Aşama 2’de sınıflandırma zorunlu değilken takip/imha akışının çalışması.
- Aşama 3’te dost hedefin vurulmaması ve menzil kapısının uygulanması.

## 5. Teknoloji Seçimi

Şartname belirli bir programlama dili veya yapay zekâ modeli zorunlu kılmaz. Bu repo için teknik yön, düşük gecikmeli, test edilebilir ve yarışma sahasında hızlı teşhis edilebilir bir Python ağırlıklı mimaridir.

Önerilen temel yığın:
- **Dil:** Python 3.x.
- **Operatör arayüzü:** PySide6 / Qt for Python.
- **Görüntü işleme:** OpenCV; gerçek hedef görselleri netleşirse model tabanlı algı eklenebilir.
- **Kamera:** Raspberry Pi uyumlu kamera hattı için Picamera2 değerlendirilebilir.
- **Donanım haberleşmesi:** pySerial ve/veya python-can; kesin seçim MCU arayüzüne göre yapılmalıdır.
- **Test:** pytest.
- **Log formatı:** Geliştirme sırasında JSONL veya CSV olabilir; üretilen log/telemetri dosyaları git’e eklenmemelidir.

ROS2, Hailo veya derin öğrenme tabanlı algı bu aşamada çekirdek zorunluluk değildir. Bu teknolojiler yalnızca gecikme, doğruluk veya entegrasyon testleri açıkça ihtiyaç gösterirse eklenmelidir.

## 6. İş Paketi Eşlemesi

- **WP-01 Manuel Mod:** Aşama 1, kullanıcı arayüzü, manuel pan/tilt ve kullanıcı komutlu ateş.
- **WP-02 Otonom Tespit ve Takip:** Aşama 2, hareketli hedef tespiti, takip ve tur içinde imha kararı.
- **WP-03 Dost-Düşman + Menzil:** Aşama 3, dost-düşman ayrımı, hedef tipi ve menzil kapısı.
- **WP-04 Güvenlik Katmanı:** Acil durdurma, harekete yasak alan, atışa yasak alan, güvenli varsayılan durum.
- **WP-05 Log/Telemetri:** Görev olayları, video kanıtı, rapor kanıtları, hata ayıklama ve tekrar oynatma kayıtları.

## 7. Doğrulama Önceliği

Kod eklendiğinde doğrulama sırası şu olmalıdır:

1. Güvenlik kapısı ve acil durdurma birim testleri.
2. Mock donanımla manuel mod ve otonom mod senaryo testleri.
3. Kamera/perception kayıtlarıyla algı ve takip tekrar testleri.
4. Operatör arayüzünde gerçek görev akışı denemesi.
5. Gerçek donanımda düşük güç/güvenli koşul testi.
6. Şartnamedeki video yetenek sırasına göre uçtan uca prova.

Her teknik karar, şartnamedeki görev başarısı ve güvenlik kurallarıyla gerekçelendirilebilmelidir.
