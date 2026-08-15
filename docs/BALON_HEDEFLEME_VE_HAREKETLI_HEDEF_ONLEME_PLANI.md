# Balon Hedefleme ve Hareketli Hedef Önleme Planı

## 1. Karar özeti

Mevcut yazılım **henüz balon merkezini zorunlu nişan noktası olarak kullanmıyor** ve hareketli hedef için hesaplanan gelecekteki kesişim noktasını otonom ateş döngüsüne bağlamıyor.

Nihai yaklaşım üç katmanlı olacaktır:

1. **Algı:** hedef maketi ile kırmızı balonu ayrı nesneler olarak bul ve birbirine ilişkilendir.
2. **Takip:** balonun görüntü düzlemindeki hızını ve hedefin parkur üzerindeki durumunu zamana göre filtrele.
3. **Nişan:** LiDAR mesafesi, toplam sistem gecikmesi ve hedef hareketinden ateş anındaki balon konumunu tahmin et; yalnız güvenilir ilişki ve emniyet kapıları varsa ateşe izin ver.

Statik aşamada doğrudan balon merkezine nişan alınır. Hareketli aşamada rota tabanlı tahmin ana yöntem, görüntü düzlemi hız tahmini ise yedek ve düzeltme yöntemi olur.

## 2. Şartname açısından hedef nedir?

İmha başarısı hedef maketinin gövdesine değil, üzerindeki kırmızı balona bağlıdır. Balon çapı yaklaşık **12–16 cm** kabul edilir. Bu nedenle “hedef maketini tespit ettim” tek başına ateş izni değildir; bağlı balonun merkezi ve güvenilirliği de bilinmelidir.

## 3. Mevcut kodun durumu

### Hazır olanlar

- `perception/src/frame_processor.py`
  - Kırmızı/dairesel balon adaylarını ayırt edebilen şekil kontrolü var.
  - Basit izleyici `velocity_x_px_s` ve `velocity_y_px_s` üretiyor.
- `perception/src/detection_tracks.py`
  - Model tespitlerini kararlı track kayıtlarına dönüştürüyor.
- `perception/src/aim_alignment.py`
  - Bir görüntü noktasını yaw/pitch hatasına çevirebiliyor.
- `backend/src/gokkalkan_backend/course_geometry.py`
  - Parkur durumu ve `predict_intercept(...)` kesişim hesabı mevcut.
- `backend/src/gokkalkan_backend/operator_api.py`
  - Parkur gözlemlerini `CourseTrackEstimator` içine aktarıyor.
- `backend/src/gokkalkan_backend/autonomous_controller.py`
  - Hedef seçme, hizalama, settle ve ateş durum makinesi mevcut.

### Eksik veya yanlış bağlananlar

- HSV yolunda balona benzeyen kırmızı bölge şu anda hedef maket tespitinden çıkarılıyor; balon ayrı bir **nişan nesnesi** olarak yayınlanmıyor.
- YOLO `balloon` tespiti ayrı bir track olabilir; hangi makete ait olduğu belirtilmiyor.
- Track sözleşmesinde `balloonCenterPx`, `parentTargetTrackId`, ilişki güveni ve tahmini nişan noktası yok.
- `aim_alignment.py` mevcut kutu merkezini kullanıyor; balon merkezi veya gelecekteki nokta verilemiyor.
- `course_geometry.py::predict_intercept(...)` testlerde kullanılıyor fakat otonom ateş yolunda çağrılmıyor.
- `autonomous_controller.py` güncel `yawErrorDeg/pitchErrorDeg` ile ateş ediyor; bağlı balon ve geçerli lead çözümü şart değil.
- Varsayılan `aim_tolerance_deg=0.5`, 15 m'deki balon için fiziksel olarak fazla geniş olabilir.

## 4. Geometrik hassasiyet

Balon yarıçapı `r = 0.06–0.08 m`, mesafe `R` ise balonun yaklaşık açısal yarıçapı:

```text
theta_balloon = atan(r / R)
```

15 m'de:

```text
atan(0.06 / 15) = 0.229 derece
atan(0.08 / 15) = 0.306 derece
```

Bu değer yalnız balon kenarına kadar geometrik paydır. Kamera–namlu boresight hatası, taret boşluğu, saçılma ve gecikme de aynı hata bütçesini tüketir. Bu yüzden `0.5°` sabit toleransla gerçek atış yetkilendirilmeyecek; tolerans mesafe ve fiziksel saçılma ölçümünden üretilecektir.

## 5. Balon–maket ilişkilendirmesi

Her frame için:

1. Maket tespitlerini (`f16`, `helicopter`, `missile`, `drone`) ve `balloon` tespitlerini ayrı listelere ayır.
2. Her maket kutusunu aşağı ve yanlara kontrollü oranla genişlet; balon merkezinin bu ilişki bölgesinde olup olmadığını kontrol et.
3. Aday çiftleri şu maliyetle puanla:
   - balon merkezinin beklenen alt bölgeye uzaklığı,
   - maket ve balon hareket vektörlerinin benzerliği,
   - önceki frame'deki ilişkinin devamlılığı,
   - balon kutusunun beklenen fiziksel boyut/mesafe tutarlılığı.
4. En düşük maliyetli bire bir eşleşmeyi seç; bir balonu iki makete bağlama.
5. İlişki birkaç frame boyunca kararlı değilse `fireCandidate=false` tut.
6. Dost/düşman aşamasında balon, bağlı olduğu maketin kimliğini devralır. Dost hedefe bağlı veya ilişkisiz balon ateş adayı olamaz.

Önerilen track alanları:

```json
{
  "aimObjectRole": "balloon",
  "parentTargetTrackId": "T-17",
  "balloonBBoxPx": [x, y, w, h],
  "balloonCenterPx": [cx, cy],
  "balloonVelocityPxSec": [vx, vy],
  "balloonAssociationConfidence": 0.93,
  "fireCandidate": true
}
```

## 6. Hareketli hedef için gereken süre modeli

“Az sonra” tek bir sabit sayı değildir. Toplam önleme süresi:

```text
t_lead = t_capture
       + t_detection
       + t_queue
       + t_control
       + t_turret_settle
       + t_trigger
       + t_projectile(range)
```

- `t_capture`: pozlama ve frame teslim süresi
- `t_detection`: Hailo/YOLO çıkarım süresi
- `t_queue`: thread/IPC/USB ve komut kuyruğu gecikmesi
- `t_control`: Pico komutunu uygulayana kadar geçen süre
- `t_turret_settle`: taretin hedef açıya gelip kabul bandında kalma süresi
- `t_trigger`: komuttan BB'nin namluyu terk etmesine kadar süre
- `t_projectile(range)`: BB uçuş süresi

Başlangıç yaklaşımı `range / muzzle_speed` olabilir; airsoft BB'si sürükleme nedeniyle sabit hızla uçmadığından canlı kullanımda mesafeye göre ölçülmüş uçuş süresi tablosu kullanılmalıdır.

## 7. Çözüm seçenekleri

### Seçenek A — Yalnız balon merkezine nişan

**Kullanım:** statik aşama ve ilk HIL kabulü.

```text
aim_px = balloon_center_px
```

Artısı basit ve doğrulanabilir olmasıdır. Hareketli hedefte toplam gecikme arttıkça geride kalır; nihai çözüm değildir.

### Seçenek B — Görüntü düzleminde kısa vadeli önleme

```text
future_px = current_px + filtered_velocity_px_s * t_lead
```

Balon merkez/hızını alpha-beta veya sabit hızlı Kalman filtresiyle yumuşatır. Rota bilinmediğinde iyi yedektir. Perspektif, kıvrımlı rota ve kameranın kendi hareketi nedeniyle uzun tahminlerde hata büyür; tahmin ufku sınırlandırılmalıdır.

### Seçenek C — Önerilen hibrit rota tabanlı önleme

1. LiDAR mesafesi ve görüntü açısıyla hedefi parkur koordinatına yerleştir.
2. `CourseTrackEstimator` ile rota, yön ve hızı kestir.
3. `predict_intercept(...)` ile BB uçuşu + sistem gecikmesini içeren kesişimi bul.
4. Kesişim noktasını kamera nişan açısına dönüştür.
5. Balon track'inin kısa vadeli görüntü hatasını küçük bir residual düzeltme olarak ekle.
6. Rota çözümü geçersizse Seçenek B'ye düş; iki çözüm de geçersizse ateşi bloke et.

Bu yöntem Rota 1/2/3 geometrisini kullanır, yakın hedefte büyüyen yaw değişimini doğal olarak kapsar ve mevcut `course_geometry.py` yatırımını değerlendirir.

## 8. Uygulama sırası ve dosya değişiklikleri

### Faz 1 — Veri sözleşmesi ve ilişkilendirme

- Yeni: `perception/src/balloon_association.py`
  - bire bir maket–balon eşleştirme,
  - zaman sürekliliği,
  - güven puanı ve red nedenleri.
- Değiştir: `perception/src/detection_tracks.py`
  - sınıf rolünü koru,
  - kutu merkezi ve hızını yayınla,
  - ilişki alanlarını track payload'ına ekle.
- Değiştir: `perception/src/frame_processor.py`
  - muhtemel balonu sessizce atmak yerine ayrı `balloon` adayı olarak yayınla,
  - HSV yolunda da aynı ilişkilendirme sözleşmesini kullan.
- Test: `tests/test_balloon_association.py`
  - tek hedef/tek balon,
  - iki hedef/iki balon,
  - ilişkisiz balon,
  - dost hedefe bağlı balon,
  - kısa süreli kapanma ve yeniden ilişki.

**Çıkış kapısı:** track çıktısında doğru makete bağlı, kararlı balon merkezi görülür; ilişkisiz balon ateş adayı değildir.

### Faz 2 — Statik balon nişanı

- Değiştir: `perception/src/aim_alignment.py`
  - bbox yerine açık `aim_point_px` kabul et,
  - boresight ofsetini ve mesafeye bağlı toleransı uygula.
- Değiştir: `backend/src/gokkalkan_backend/operator_api.py`
  - yeni alanları kaybetmeden backend track sözleşmesine taşı,
  - LiDAR mesafesini balonun bağlı olduğu ana hedefe iliştir.
- Değiştir: `backend/src/gokkalkan_backend/autonomous_controller.py`
  - `fireCandidate`, balon ilişkisi, dost/düşman ve veri tazeliğini zorunlu yap,
  - nişan hatasını balon merkezinden al.

**Çıkış kapısı:** simülasyonda maket merkezi değil balon merkezi takip edilir; balon kaybolursa FIRE iptal edilir.

### Faz 3 — Gecikme ve hareket telemetrisi

- Her frame'e capture timestamp ve her aşamaya monotonic timestamp ekle.
- Pico ACK/uygulama zamanını telemetriye taşı.
- `backend/src/gokkalkan_backend/telemetry.py` üzerinden gecikme bileşenlerini kaydet.
- Yeni yapılandırma: `config/perception/lead.toml`
  - maksimum tahmin ufku,
  - minimum ilişki güveni,
  - tazelik sınırı,
  - ölçülmemiş değerlerde `fire_allowed=false`.

**Çıkış kapısı:** loglardan p50/p95 capture→aim ve aim→trigger süreleri hesaplanabilir.

### Faz 4 — Görüntü düzlemi yedek önleme

- Yeni: `perception/src/lead_estimator.py`
  - alpha-beta/Kalman filtre,
  - zaman damgalı hız,
  - sınırlı `future_px`,
  - güven ve red nedeni.
- Kamera/taret hareketini ayırmak için encoder kaynaklı görüntü hareketi telafisi ekle.
- Tahmin görüntü sınırı dışına, yaşlı track'e veya aşırı ivmeye giderse ateşi bloke et.

**Çıkış kapısı:** kayıtlı/sentetik hareket dizilerinde gelecekteki balon merkezi hatası ölçülür.

### Faz 5 — Rota tabanlı kesişimi çalışma zamanına bağla

- Değiştir: `backend/src/gokkalkan_backend/operator_api.py`
  - taze LiDAR + rota çözümü geldiğinde `CourseTrackEstimator.predict_intercept(...)` çağır,
  - sonucu `predictedAimBearingDeg`, `predictedAimElevationDeg`, `interceptTimeSec`, `leadSource` olarak yayınla.
- Değiştir: `backend/src/gokkalkan_backend/course_geometry.py`
  - sabit mermi hızı yerine `time_of_flight(range)` sağlayıcısı kabul et,
  - çözümsüz/geçersiz durumda açık hata nedeni döndür.
- Değiştir: `backend/src/gokkalkan_backend/autonomous_controller.py`
  - `leadValid=true` ve yaş sınırı içinde değilse hareketli aşamada ateş etme,
  - ilişki/rota değişince settle sayacını sıfırla,
  - öngörülen hata bandı içinde ardışık örnek şartı koy.
- Testleri genişlet:
  - `tests/test_course_runtime.py`,
  - `tests/test_autonomous_controller.py`,
  - sentetik replay benchmark.

**Çıkış kapısı:** Rota 1/2/3 ve iki yön için taret mevcut konuma değil hesaplanan kesişim noktasına yönelir.

### Faz 6 — Fiziksel kalibrasyon ve canlı kabul

Bu faz CAD/sentetik çalışma ile tamamlanamaz.

Gerekli ölçümler:

1. 0,25 g BB ile kronograf hız dağılımı.
2. 5–17 m mesafelerde gerçek uçuş süresi veya yüksek FPS video ölçümü.
3. Komut→BB çıkışı tetik gecikmesi.
4. Kamera–namlu boresight ofseti ve mesafeye göre sapma.
5. Pan/tilt settle süresi ve backlash.
6. Her mesafede atış dağılımı; balon içinde kalma olasılığı.

Ölçümlerden:

- `config/calibration/airsoft_ballistics.toml`
- `config/calibration/camera_boresight.toml`
- `config/calibration/turret_latency.toml`

üretilir. Dosya yoksa veya seri numarası/tarih uyuşmuyorsa canlı otomatik atış fail-closed kalır.

## 9. Ateş yetkilendirme kapıları

Hareketli hedefte FIRE yalnız aşağıdakilerin tamamında açılır:

- E-Stop ve donanımsal izin aktif,
- ana hedef düşman,
- bağlı balon mevcut ve ilişki güveni eşik üstü,
- görüntü, LiDAR ve encoder verileri taze,
- rota/lead çözümü geçerli,
- tahmin ufku sınır içinde,
- boresight ve balistik kalibrasyon geçerli,
- öngörülen balon merkezi güvenli ateş alanında,
- hata toleransı mesafe-bağımlı sınır içinde ve settle süresi dolu,
- dost hedef, yasak alan veya ilişki değişimi yok.

Bir kapı düşerse atış kuyruğu temizlenir ve yeniden settle gerekir.

## 10. Başarı ölçütleri

- **Algı:** balon–maket ilişki precision/recall; dost hedefe yanlış ilişki sıfır olmalı.
- **Tahmin:** `prediction_horizon` sonunda piksel ve açısal merkez hatası.
- **Kontrol:** p95 toplam gecikme ve settle süresi.
- **Atış:** mesafe/rota/hıza göre balon içinde isabet oranı ve güven aralığı.
- **Emniyet:** eski/stale veri, ilişki değişimi, LiDAR kaybı ve E-Stop halinde yanlış FIRE sayısı sıfır.

## 11. İlk uygulanacak iş paketi

Fiziksel kalibrasyon beklenmeden Faz 1–5 kodlanabilir ve sentetik/replay verisiyle doğrulanabilir. Ancak `t_projectile`, boresight ve saçılma fiziksel ölçülene kadar bu çıktı **canlı atış yetkisi değildir**. İlk kod değişikliği balon ilişkilendirme sözleşmesi olmalıdır; aksi halde sonraki lead hesabı yanlış nesnenin merkezini geleceğe taşır.
