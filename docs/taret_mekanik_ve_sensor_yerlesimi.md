# Taret Mekaniği, Kamera/LiDAR Yerleşimi ve Yazılım Referansı

Bu belge, imalat sonrası entegrasyonda kodlama ajanlarının ve ekip üyelerinin
aynı fiziksel modeli kullanması için **kanonik mekanik-yazılım referansıdır**.
Sayısal imalat resmi değildir. Kullanıcı tarafından kesinleştirilen tasarım
kararlarını, CAD görsellerinden güvenle çıkarılabilen kinematik ilişkileri ve
imalattan sonra ölçülmesi gereken değerleri birbirinden ayırır.

## 1. Kaynaklar ve kanıt seviyesi

| Kaynak | Kullanım | SHA-256 |
| --- | --- | --- |
| [`gokkalkan_izometrik_cizim.png`](images/gokkalkan_izometrik_cizim.png) | Temel taret, iki eksen ve taşıyıcı yapı | `7745dac963b2387e9ce69b0506c90db946e331c6c3032c8f5edddec775c81db3` |
| [`version_final_kamera_ve_lidarın_konumu.jpeg`](images/version_final_kamera_ve_lidarın_konumu.jpeg) | Nihai kamera/LiDAR köprüsü ve 700 mm referansı | `8a1dd6505c985738bd15bcd3539f1d95f8c0011b1a77f749da5322d70a18082d` |
| [`sartname_v4.pdf`](sartname_v4.pdf) §4.1 ve §4.4.2 | 100 cm teknik sınırı ve ebat puanı | Nihai yarışma otoritesi |

**Kanıt sınıfları:**

- **Kesinleşmiş karar:** ekip tarafından bu belge için açıkça belirtilen bilgi.
- **CAD çıkarımı:** görselden anlaşılan fakat ölçülü imalat resmiyle henüz
  doğrulanmamış yapı.
- **İmalat sonrası ölçüm:** yazılıma sayı olarak girilmeden önce fiziksel
  sistemde ölçülmesi zorunlu değer.

Görsel üzerindeki `700 mm` işareti piksel ölçeğinden hesaplanmış değildir;
ekibin kesinleştirdiği tasarım ölçüsüdür.

## 2. Kesinleşmiş fiziksel model

1. Taret iki hareketli eksene sahiptir:
   - **yaw/pan:** sağ-sol yönelim;
   - **pitch/tilt:** silah/atış ekseninin yukarı-aşağı yönelimi.
2. İki eksen ayrı dişli/motor aktarımıyla hareket eder. CAD’de taban altındaki
   aktarım yaw tablasını, yan taşıyıcıdaki aktarım pitch milini sürüyor olarak
   yorumlanır; motor/dişli oranları henüz yazılım sabiti değildir.
3. Kamera ve TFA50-L LiDAR, kırmızıyla gösterilen ayarlanabilir köprü/profile
   bağlanır. Köprü `turret_yaw` ile birlikte sağa-sola döner fakat
   `weapon_pitch` ile yukarı-aşağı dönmez.
4. LiDAR optik merkezinin sistemin **en alt fiziksel noktasından düşey
   yüksekliği 700 mm (0,700 m)** olacak şekilde profil ayarlanır ve mekanik
   olarak kilitlenir. Hedeflerin beklenen geliş yüksekliği de 700 mm’dir.
5. Kamera LiDAR ile aynı sensör köprüsündedir ve hedefleri karşıdan görecek
   biçimde hizalanır. Görselde `L` üstte, `C` altta gösterilmiştir; aralarındaki
   kesin düşey/yatay mesafe görselden uydurulmaz.
6. Profil çalışma zamanı aktüatörü değildir. Yükseklik değişikliği yalnız
   güvenli kurulum/kalibrasyon sırasında elle yapılır.
7. Kamera kararı **tek Raspberry Pi Camera Module 3 Standard**'dır. Wide/NoIR
   veya silaha bağlı ikinci nişan kamerası aktif tasarımın parçası değildir.
8. Hızlandırıcı kararı **Raspberry Pi AI HAT+ 26 TOPS / Hailo-8**'dir.

## 3. Kinematik zincir ve koordinat çerçeveleri

```text
base
└── turret_yaw                  (base +Z etrafında sağ-sol)
    ├── sensor_bridge           (elle yüksekliği ayarlanır, çalışma anında rijit)
    │   ├── camera_main         (tek Camera Module 3 Standard)
    │   └── lidar_tfa50         (optik merkez z = 0,700 m)
    └── weapon_pitch            (yatay mafsal etrafında yukarı-aşağı)
        └── weapon_bore         (namlu/mermi başlangıç doğrultusu)
```

Kanonik eksen tanımı:

| Çerçeve | Tanım |
| --- | --- |
| `base` | Orijin yaw merkezinin taban izdüşümü; `+X` ileri/hedef, `+Y` sol, `+Z` yukarı |
| `turret_yaw` | `base` üzerinde `+Z` etrafında dönen tabla, dış plakalar ve sensör köprüsü |
| `sensor_bridge` | Yaw'ı izleyen, silah pitch'ini izlemeyen, kurulumda yüksekliği ayarlanabilir rijit profil |
| `camera_main` | Tek ana kamera; yatay bearing, tespit, tip ve gerektiğinde dost/düşman girdisi |
| `lidar_tfa50` | Tek nokta menzil doğrultusu; optik merkez yüksekliği 0,700 m; pitch bağımsız |
| `weapon_pitch` | Yaw gövdesine bağlı yukarı-aşağı dönen silah gövdesi |
| `weapon_bore` | Atış ekseni; kamera/LiDAR ekseniyle özdeş olduğu varsayılmaz |

Önemli sonuç: yaw komutu sensörlerin baktığı azimutu değiştirir; pitch komutu
sensör görüntüsünü değiştirmez. Bu nedenle kameranın merkez pikseli doğrudan
“merminin gideceği nokta” sayılamaz. `camera_main → weapon_bore` extrinsic
dönüşümü ile menzile bağlı balistik elevasyon birlikte kalibre edilmelidir.

## 4. Yazılıma girilecek sabitler ve ölçümler

### 4.1. İmalat öncesi bilinenler

| Alan | Değer | Güven |
| --- | --- | --- |
| `camera.count` | `1` | Kesinleşmiş karar |
| `camera.model` | `Raspberry Pi Camera Module 3 Standard` | Kesinleşmiş karar |
| `camera.horizontal_fov_deg` | `66.0` üretici nominali | Üretici verisi; kamera kalibrasyonu bunun yerini alır |
| `lidar.mount_height_m` | `0.700` | Kesinleşmiş tasarım hedefi |
| `camera.follows_yaw` / `lidar.follows_yaw` | `true` | Kesinleşmiş kinematik |
| `camera.follows_weapon_pitch` / `lidar.follows_weapon_pitch` | `false` | Kesinleşmiş kinematik |
| `accelerator.model` | `Raspberry Pi AI HAT+ 26 TOPS` | Kesinleşmiş karar |
| `accelerator.chip` | `Hailo-8` | Üretici/ürün bilgisi |
| `target_speed_prior_mps` | `0.4` | Komite kaynaklı geçici bilgi; şartname değeri değil |

`0,4 m/s` yalnız başlangıç prior'ıdır. Ortam/config üzerinden değiştirilebilir
kalmalı; aynı hedefin rota üzerindeki ardışık `s` gözlemlerinden kestirilen hız
yeterli örnek oluştuğunda prior'ın yerini almalıdır.

### 4.2. İmalat sonrası ölçülmeden uydurulmayacaklar

- `camera_main` ve `lidar_tfa50` için `translation_m=[x,y,z]` ile
  `rotation_deg=[yaw,pitch,roll]`;
- sensörler arasındaki baz mesafe ve optik eksen farkı;
- `weapon_bore` ile kamera/LiDAR arasındaki yaw/pitch ofseti;
- yaw ve pitch dişli oranı, işaret yönü, backlash, mekanik limit ve encoder
  sıfırları;
- profil kilitleme yöntemi, kablo hareket payı ve titreşim davranışı;
- gerçek kamera intrinsics/distortion matrisi ve etkin görüntü kırpması;
- 5/10/15 m LiDAR tekrar edilebilirliği;
- menzil-elevasyon balistik tablosu, tetik/yerleşme gecikmesi ve mermi hızı.

Profil yüksekliği veya sensör bağlantısı değiştiğinde mount revision/hash
değiştirilmeli; eski extrinsic ve balistik kalibrasyon `UNVERIFIED` olmalı ve
LIVE arm fail-closed kapanmalıdır.

## 5. Tek kamera ile görev akışı

1. **Yaw taraması:** silah ve sensör köprüsü birlikte sağa-sola taranır. Kamera
   tüm hedef adaylarını bulur; encoder yaw'ı ile piksel bearing'i birleştirilir.
2. **İlk kimliklendirme:** hedef tipi belirlenir. Aşama gerektiriyorsa
   kırmızı/mavi bilgisiyle dost-düşman ayrımı ayrıca yapılır.
3. **Rota eşleme:** kamera bearing'i ve LiDAR menzili, hedefi kanonik
   `POLIGON_ROUTE_1..3` eğrilerinden birine ve rota yay uzunluğu `s`'ye yansıtır.
4. **Önceliklendirme:** Mission Core aşama kuralına göre hedefi seçer. Kamera
   yalnız seçilen hedefe kanalize olur; tip/dost-düşman ve güvenlik kararı UI'da
   verilmez.
5. **Hız kestirimi:** ardışık `s/t` gözlemlerinden aynı rota yönündeki hız
   kestirilir. İlk yeterli gözleme kadar değiştirilebilir `0,4 m/s` prior'ı
   yalnız yönelim/reacquisition desteği olarak kullanılabilir.
6. **Sonraki hedefi yeniden edinme:** seçili hedefle ilgilenilirken görüş dışında
   kalan hedefin son `s`, rota, hız ve geçen süre bilgisiyle yeni `s` tahmin
   edilir; taret tahmini bearing'e döner ve kamera ölçümüyle yeniden kilitlenir.
7. **Kesişim tahmini:** yalnız güncel kamera+LiDAR ölçümü, geçerli rota, ölçülmüş
   hız ve fiziksel atış parametreleri varken `s_hit = s_now + v × t_flight`
   çözülür. Eğriler düz çizgiye indirgenmez; `point_at_s` rota yay uzunluğunu
   takip eder.
8. **Poligon sınırı:** dış dönüş modellenmez ve ateş tahmini için kullanılmaz.
   Hedef poligondan çıktığında prediction kapanır; batı girişinden yeniden
   görüldüğünde yeni geçiş başlar.

Bu rota/hız/kesişim altyapısı
[`backend/src/gokkalkan_backend/course_geometry.py`](../backend/src/gokkalkan_backend/course_geometry.py)
içindeki `CourseTrackEstimator` ve `predict_intercept()` ile zaten uygulanmıştır.
Yeni kod bu algoritmayı kopyalamamalı; sensör füzyonundan güvenilir menzil ve
base-frame bearing sağlamalıdır.

Backend `/state` çıktısındaki `coursePredictions`, görüş dışındaki hedefler için
yalnız `CAMERA_REACQUISITION_ONLY` amaçlıdır ve `fireAuthoritative=false` taşır.
`speedSource=PRIOR` olan durumlarda kesişim/atış tahmini üretilmez; bunun için
aynı hedefin en az iki fiziksel rota gözleminden `speedSource=MEASURED` elde
edilmesi gerekir. Böylece komite kaynaklı hız önbilgisi taretin bir sonraki
bakış yönünü hızlandırır, fakat Safety Gate'i veya ölçüm zincirini ikame etmez.

## 6. AI HAT+ kullanım sınırı

AI HAT+ aşağıdaki yerel görüntü işlerinde kullanılabilir:

- hedef adayı tespiti;
- hedef tipi sınıflandırması;
- birden fazla hedef için görünüş/track özelliği üretimi.

Renk tabanlı dost-düşman kuralı, rota geometrisi, Safety Gate ve atış yetkisi
NPU modeline devredilmez. Model ağırlığı/HEF artefaktı henüz seçilip gerçek ve
sentetik CAD veri setiyle doğrulanmadığı için mevcut yazılım tip sınıfını
`Bilinmeyen` bırakır; sahte bir “Mini/Micro İHA” sonucu üretmez.

[`perception/src/accelerator.py`](../perception/src/accelerator.py), Hailo-8
donanımı ile model artefaktı hazırlığını ayrı health alanları olarak sunar.
`hailortcli fw-control identify` 26 TOPS Hailo-8 yerine 13 TOPS Hailo-8L
gösterirse entegrasyon kabul edilmez. NPU yokluğu, Pi systemd profilinde
perception heartbeat'ini sağlıksız yapar; fiziksel çıkışa sessiz CPU fallback'i
yapılmaz.

## 7. Ebat etkisi

Şartname §4.1 her en/boy/yükseklik değerini 100 cm'den küçük tutar. §4.4.2 ise
en uzun boyut `≤60 cm` ise 20 puan, `60 cm < boyut < 100 cm` ise 0 puan verir.
LiDAR merkezinin en alt noktadan 700 mm yukarıda olması en uzun boyutu zaten
60 cm üzerine çıkarır. Tasarım kararı bu 20 puandan vazgeçmektedir:

- teorik toplam tavan: `500 → 480`;
- kayıp: `20/500 = %4`;
- bu durum tek başına görev puanlarını düşürmez veya diskalifiye yaratmaz;
- nihai üst sensör/profil yüksekliği yine **100 cm'den küçük** ölçülmelidir.

## 8. İmalat sonrası kabul kontrol listesi

- [ ] LiDAR optik merkezi en alt fiziksel noktadan `700 ± mekanik tolerans` mm
  ölçülüp kayıt altına alındı.
- [ ] Toplam en/boy/yükseklik ayrı ayrı `<1000 mm` ölçüldü.
- [ ] Profil kilitli; elle yük altında kayma ve titreşim yok.
- [ ] Kablolar tam yaw hareketinde gerilmiyor ve pitch aktarımına girmiyor.
- [ ] Kamera/LiDAR yaw'ı izliyor, silah pitch hareketinde sensör görüntüsü sabit.
- [ ] Yaw/pitch işaretleri, dişli oranları, backlash ve limitler kalibre edildi.
- [ ] Kamera intrinsics ve `camera_main → weapon_bore` extrinsic ölçüldü.
- [ ] TFA50-L 5/10/15 m hedef yüzeyinde doğrulandı.
- [ ] AI HAT+ `hailortcli` çıktısında Hailo-8 olarak görüldü.
- [ ] Seçilen HEF modelinin hash'i, sınıfları, precision/recall ve gecikmesi
  release/session manifestine kaydedildi.
- [ ] `SIM → HIL → LIVE` geçişinde sensör/accelerator health kaybının arm'ı
  kapattığı doğrulandı.
