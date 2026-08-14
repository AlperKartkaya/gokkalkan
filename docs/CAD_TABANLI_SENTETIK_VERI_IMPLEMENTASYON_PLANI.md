# CAD Tabanlı Sentetik Veri — Adım Adım İmplementasyon Planı

> **Durum:** Uygulamaya hazır teknik plan
> **Tarih:** 14 Ağustos 2026
> **Ana roadmap:** [`CAD_TABANLI_SENTETIK_VERI_VE_MODEL_GELISTIRME_ROADMAP.md`](CAD_TABANLI_SENTETIK_VERI_VE_MODEL_GELISTIRME_ROADMAP.md)
> **Kamera/ROI kararı:** [`KAMERA_ROI_ZOOM_VE_SENTETIK_VERI_KARARLARI.md`](KAMERA_ROI_ZOOM_VE_SENTETIK_VERI_KARARLARI.md)
> **Kapsam:** `Modeller.3mf` → gerçekçi sentetik görüntü → zoom/degradasyon → araştırma modeli → gerçek veriyle sim-to-real → ONNX/HEF
> **Güvenlik sınırı:** Sentetik başarı fiziksel kabul veya atış yetkisi değildir. Backend Safety Gate bütün aşamalarda nihai yetki kapısıdır.

> **Uygulama ilerlemesi — 14 Ağustos 2026:** FAZ 0–5'in CAD tabanlı çekirdeği,
> FAZ 8'in araştırma-dataset ingest'i, FAZ 9'un `378` kayıtlık pilot seçici/yeniden
> başlatılabilir renderer'ı ve FAZ 10'un fail-back zoom durum makinesi tamamlandı.
> `Modeller.3mf` içindeki gerçek ölçüler `1.0` ölçekle kilitlendi. Bağımsız yaw
> bucket'ları kaldırıldı; Rota 1/2/3 görünüş açıları boylamasına ve enlemesine
> uzaklıktan `atan2` ile türetiliyor. `3–17 m`, yedi rota konumu ve on bir eğim
> bucket'ı için toplam `6.930` kayıtlık plan üretilebilir. LOD0/1/2 doğrulaması ve
> BlenderProc RGB/depth/instance/semantic smoke renderı yerelde çalışıyor.
> Fiziksel kamera ve gerçek hedef işleri bu CAD/sentetik fazının blocker'ı değildir;
> sonraki zorunlu kabul sınırı yalnız AR-09 ve AR-10'dur.
---

## 1. Bu planın kesinleştirdiği kararlar

### 1.1. Araç zinciri

| Konu | Kesin karar |
| --- | --- |
| 3MF okuma/doğrulama | Resmî `lib3mf==2.5.0` Python binding kullanılacak. ZIP/XML'i uygulama mantığı olarak elle parse etmeyeceğiz. |
| Render | `blenderproc==2.8.0` + onun desteklediği Blender `4.2.1` headless kullanılacak. |
| Görüntü sonrası işleme | OpenCV/NumPy kullanılacak. |
| Eğitim başlangıcı | Mevcut YOLOv8n araştırma baseline'ı korunacak; gerçek veri kıyası olmadan mimari değiştirilmeyecek. |
| Runtime | Blender, BlenderProc ve CAD araçları Raspberry Pi/LIVE ortamına kurulmayacak; yalnız geliştirme makinesinde çalışacak. |
| Ağır dosyalar | 3MF, türetilmiş mesh, render, ağırlık, ONNX ve HEF normal Git geçmişine eklenmeyecek. Manifest ve hash repoda tutulacak. |
| Release | `trainingAuthorized=false` ve `releaseCandidate=false`, bağımsız gerçek validation/test oturumları ve fiziksel kapılar tamamlanana kadar korunacak. |

### 1.2. Geometri ve görüş sözleşmesi

Bambu Studio sunum çerçevesi korunur: `Front` kamera yönü kaynak `-Y`, ekran
sağı `+X`, ekran yukarısı `+Z`'dir. Kamera-merkezli dünyada kamera
`[0, 0, 1.30] m`, hedef referans merkezi `1.30 m` yüksekliğindedir.

Hedefin fiziksel dönüşü yalnız burun eğimidir:

```text
R_target = Rx(topSurfaceViewDeg)
```

Sağ/sol görünüş için hedefe ikinci kez yaw rotasyonu uygulanmaz. Rota geometrisi
bu görünüşü zaten oluşturur:

```text
x = signedLateralDistanceM
y = longitudinalDistanceM
viewYawDeg = degrees(atan2(x, y))
targetPositionM = [x, y, 1.30]
distanceM = sqrt(x² + y²)
```

- Rota 1: `x = +2.75 / +2.87 / +3.00 m`;
- Rota 2: `x = 0 m`, dolayısıyla her mesafede `viewYawDeg = 0°`;
- Rota 3: `x = -2.75 / -2.87 / -3.00 m`.

İşaret, görüntünün sağ/sol tarafını; açı büyüklüğü hedefin ne kadar yandan
izlendiğini gösterir. Aynı yan ofsette boylamasına mesafe arttıkça mutlak yaw
monoton azalır. En uç örnek `3 m / 3 m` için `±45°`'dir.

Burun eğimi bucket'ları `4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28°`'dir. Gerçek
`topSurfaceViewDeg`, bucket çevresinde `±0.5°` jitter taşır. Mesafe ve enlemesine
ofset değerleri komitenin parkur varsayımını doğrudan temsil ettiği için bu
sürümde konumsal jitter `0`'dır. Her kayıt route, bucket ve gerçek sayısal
alanları ayrı taşır; kesin eğim sonradan bildirilirse renderlar
`filter_render_plan.py` ile tahribatsız seçilir.

### 1.3. Rota ve mesafe örneklemesi

- Boylamasına uzaklıklar: `3, 4, 5, …, 17 m`.
- Rota 1/3 enlemesine uzaklıkları: `2.75, 2.87, 3.00 m`.
- Rota 2 merkez ofseti: `0 m`.
- Kamera-hedef gerçek menzili `hypot(longitudinal, lateral)` olarak metadata'ya yazılır.
- Yaw bağımsız bir çarpan değildir; her rota konumu için matematiksel olarak türetilir.
- Aynı pozun görünüm varyantı deterministik atanır: nominal `%40`, hafif soluk
  `%20`, karanlık ortam `%20`, aydınlık ortam `%20`.
- `worldId/groupId` split'ten önce üretilir; aynı dünyanın türevleri train/val/test
  arasında bölünmez.

Toplam temel poz sayısı:

```text
6 sunum sınıfı × 15 boylamasına mesafe × 7 rota konumu × 11 eğim = 6.930
```

Renk/aydınlık görünüm profilleri tam Kartezyen çarpan değildir; bu 6.930 poza
oranlı ve deterministik atanır. Böylece gereksiz dört kat render artışı önlenir.

### 1.4. Zoom ve çözünürlük kaybı

Camera Module 3 üzerinde optik zoom yoktur. Varsayılan yol aynı capture request'ten
tam-FoV `1280×720 lores` ve `2304×1296 main` alıp, kararlı track sonrası yüksek
çözünürlüklü main üzerinde software ROI üretmektir:

1. **`none`** — tam görüş lores arama görüntüsü.
2. **`high_res_roi`** — `2304×1296 main` üzerinde 16:9 crop; doğrudan model
   letterbox aşamasına gider. Runtime varsayılanıdır.
3. **`scaler_crop`** — Picamera2 `ScalerCrop` araştırma proxy'si; fiziksel
   benchmark olmadan varsayılan olmaz.
4. **`application_crop`** — `1280×720` üzerinde crop+büyütme; yalnız düşük
   çözünürlüklü negatif baseline'dır.

Kesin zoom bucket'ları:

- ana veri: `1.0×`, `1.5×`, `2.0×`;
- yalnız hard-case/robustness: `3.0×`;
- model girdisi: mevcut sözleşmeye uygun `640×640` letterbox.

İşlem sırası değişmeyecek:

```text
sahne renderı
→ optik/sensör/ISP profili
→ full-frame lores VEYA high-res main ROI
→ en-boy oranı korunmuş 640×640 model letterbox
```

RGB888 inference yolunda JPEG/H.264 codec yoktur; codec artefaktı varsayılan
olarak eklenmez. Blur/noise Camera Module 3'e ait ölçüm gibi rastgele uygulanmaz;
profil kimliğiyle izlenen araştırma sweep'i olarak kalır.

Her zoom örneğinde şu metadata zorunlu olacak:

- `zoomMode`, `zoomFactor`;
- `cropRectPx`;
- `preCropResolution`, `postCropResolution`, `modelInputResolution`;
- `interpolation`;
- `targetPixelsBeforeZoom`, `targetPixelsAfterZoom`;
- `zoomCenterErrorPx`;
- `worldId`, `variantId`, `groupId`.

Zoom hedefi kusursuz ortalamayacak. Takip gecikmesini taklit etmek için crop
merkezine kontrollü hata eklenecek. Böylece model “hedef her zaman ortadadır”
kısa yolunu öğrenmeyecek.

### 1.5. Veri katmanları ve kaynak adları

Aşağıdaki `sourceKind` değerleri kullanılacak:

- `synthetic_seed_2d`: mevcut kanonik görsellerden üretilen smoke verisi;
- `synthetic_cad_pbr`: fizik tabanlı CAD renderı;
- `synthetic_cad_dr`: domain-randomized CAD renderı;
- `synthetic_cad_hybrid`: gerçek boş kamera arka planı + CAD hedef;
- `real_background_only`: hedef içermeyen gerçek kamera kaydı;
- `real_capture`: gerçek hedef kamera kaydı.

Sentetik CAD verisi train/validation araştırmasında kullanılabilir; gerçek test
split'ini hiçbir zaman dolduramaz.

---

## 2. ACTION REQUIRED blocker sözleşmesi

CAD ingest, LOD, sentetik poz, materyal, render, zoom ve eğitim araştırması fiziksel
kamera beklenmeden sürdürülebilir. Fiziksel kamera kalibrasyonu, boş arka plan,
zoom eşlemesi, imalat ve boya ölçümü bu fazın blocker'ı değildir; gerçek veri
fazına ertelenmiştir.

### AR-09 — Gerçek hedef oturumları (CAD/sentetik işler bittikten sonra)

**Ne zaman durulur:** Gerçek veri fine-tuning'i ve release metriği öncesi.
**Kullanıcı aksiyonu:** Gerçek hedefleri ayrı gün/ışık oturumlarında; rota,
mesafe, burun eğimi, zoomsuz/zoomlu ve hareketli biçimde kaydet. Aynı oturumu
train ve test için bölme.

**Beklenen çıktı:** Session bazlı ham veri ve insan gözünden geçirilmiş annotation.
**Blokladığı iş:** Real-only validation/test, releaseCandidate ve fiziksel model kabulü.
**Bloklamadığı iş:** CAD/sentetik araştırma eğitimi, replay ve deployment smoke.

### AR-10 — Hailo donanımı ve dönüşüm ortamı

**Ne zaman durulur:** HEF eşdeğerlik ve Pi latency kabulünde.
**Kullanıcı aksiyonu:** Pi 5 + AI HAT+ 26 TOPS/Hailo-8, uyumlu HailoRT ve HEF
compiler ortamını erişilebilir kıl.

**Beklenen çıktı:** Cihaz/SDK sürümü, model/HEF hash'i ve ölçüm logları.
**Blokladığı iş:** HEF/Pi canlı kabulü ve soak.
**Bloklamadığı iş:** ONNX export ve mock runner testleri.

## 3. Fazlar ve uygulanma sırası

## FAZ 0 — Sözleşme, dizin ve bağımlılık iskeleti

**Amaç:** Render kodundan önce formatları kilitlemek.

### Yapılacaklar

- [x] `perception/synthetic/README.md` oluştur.
- [x] Python `3.11` tabanlı `.venv-synthetic` oluştur.
- [x] `requirements/synthetic-render.lock` oluştur; `lib3mf==2.5.0`,
  `blenderproc==2.8.0` ve geliştirme araçlarını backend/Pi bağımlılıklarından
  ayır. BlenderProc'un indirdiği/kullandığı Blender sürümünü de batch manifestine
  `4.2.1` olarak kaydet.
- [x] Aşağıdaki şemaları ekle:
  - `perception/synthetic/schema/cad-source.schema.json`
  - `perception/synthetic/schema/cad-asset-manifest.schema.json`
  - `perception/synthetic/schema/render-batch.schema.json`
  - `perception/synthetic/schema/render-record.schema.json`
- [x] Kaynak türü enum'una Bölüm 1.5 değerlerini ekle.
- [x] Generated dizinleri `.gitignore` ile dışarıda tut:
  - `perception/synthetic/generated/normalized_assets/`
  - `perception/synthetic/generated/render_batches/`
  - `perception/synthetic/generated/contact_sheets/`
- [x] `package.json` içine çalışan `dataset:cad:inspect` komutunu ekle.
- [ ] Sonraki fazlarda araçlar eklendikçe `dataset:cad:convert`,
  `dataset:cad:render:smoke` ve `dataset:cad:validate` komutlarını ekle.

### Çıktı

Kod yazmadan önce doğrulanabilir JSON sözleşmeleri ve izole geliştirme ortamı.

### Doğrulama

```bash
.venv/bin/python -m pytest tests/test_synthetic_contracts.py
.venv/bin/python -m json.tool perception/synthetic/config/cad_asset_manifest.json >/dev/null
npm run dataset:cad:inspect -- --help
```

### Çıkış kapısı

- Şemalar geçerli.
- Pi/backend dependency lock'ları değişmeden kalmış.
- Generated/ağır varlıklar Git'e girmiyor.

---

## FAZ 1 — Deterministik 3MF inceleme

**Amaç:** Bambu Studio ekran görüntüsüne değil 3MF içeriğine dayalı asset kaydı.

### Yapılacaklar

- [x] `perception/synthetic/tools/inspect_3mf.py` oluştur.
- [x] SHA-256, 3MF unit, object/component/build item, transform, bbox ve üçgen
  sayısını JSON olarak üret.
- [x] Küçük ve repoda tutulabilir bir test 3MF fixture'ı programatik üret.
- [x] Yerel `Modeller.3mf` için rapor üret:
  `perception/synthetic/generated/inspection/modeller.report.json`.
- [x] Her obje için altı görünüş contact sheet oluştur.
- [x] Beklenen hash veya dört nesne değişirse fail et.

### Planlanan komut

```bash
npm run dataset:cad:inspect -- \
  --input Modeller.3mf \
  --expected-sha256 9f696bf7aa8c5c0dc2fa1e733266e6e9c274494bc2f210c3bc40b8975fb47028 \
  --report perception/synthetic/generated/inspection/modeller.report.json
```

### Doğrulama

```bash
.venv-synthetic/bin/python -m pytest \
  tests/test_synthetic_3mf_inspection.py
```

### Çıkış kapısı

- Füze, Helikopter, F16 ve Drone ayrı kayıtlar.
- Ölçüler millimetre ve metre olarak tutarlı.
- Aynı dosya aynı raporu üretiyor.

### Devam kararı

Bambu `Front/-Y`, ekran sağı `+X`, ekran yukarısı `+Z` sözleşmesi doğrulandı;
manuel eksen onayı beklenmeden FAZ 2'ye geçildi.

---

## FAZ 2 — Normalizasyon, ölçek ve LOD

**Amaç:** Master 3MF'yi bozmadan render varlıklarını üretmek.

### Yapılacaklar

- [x] `perception/synthetic/tools/convert_cad_assets.py` oluştur.
- [x] Her mesh'i Bambu `Front=-Y / right=+X / up=+Z` sunum çerçevesine göre
  merkezle; kaynak yönünü sessizce değiştirme.
- [x] Ölçekleri manifestten uygula; kaynak 3MF üzerinde değişiklik yapma.
- [x] `LOD0`, `LOD1`, `LOD2` üret.
- [x] Her LOD için hash, bbox, triangle count, transform ve fiziksel uzunluk yaz.
- [x] LOD siluet ve 2B bbox sapmasını altı canonical görünüşte ölç.
- [ ] Procedural balon ve ip varlığını görev ilişkileriyle birlikte FAZ 4’te üret.

### İlk ölçek katsayıları

| Varlık | 3MF mesh boyutu (mm) | En uzun eksen | Katsayı | Durum |
| --- | --- | ---: | ---: | --- |
| F16 | `300.403 × 500.000 × 139.258` | `500.000 mm` | `1.000` | doğrulandı |
| Helikopter | `392.467 × 582.673 × 178.363` | `582.673 mm` | `1.000` | doğrulandı |
| Drone | `287.452 × 374.986 × 195.076` | `374.986 mm` | `1.000` | doğrulandı |
| Füze | `105.132 × 218.899 × 500.000` | `500.000 mm` | `1.000` | doğrulandı |

### Kabul kuralı

- LOD2 siluet IoU: canonical görünüşlerde `≥ 0.98`.
- LOD2 bbox kenar farkı: en fazla `2 px` @ `1280×720` referans görünüşü.
- Bozuk/non-manifold geometri loglanır; sessiz onarım yapılmaz.

### Doğrulama

```bash
npm run dataset:cad:convert
npm run dataset:cad:lod
npm run dataset:cad:validate
.venv-synthetic/bin/python -m pytest tests/test_synthetic_asset_normalization.py
```

### Çıkış kapısı

- Dört hedef aynı koordinat sözleşmesinde.
- Ölçek ve yön manifestten okunuyor.
- LOD kabul kontrolleri geçiyor.

### Blocker

Yok. Bu fazda `Modeller.3mf` ölçüleri üretim gerçeği olarak kabul edilmiştir.

---

## FAZ 3 — Tek nesneli BlenderProc PoC

**Amaç:** Önce küçük, deterministik ve görsel olarak denetlenebilir render zinciri.

### Yapılacaklar

- [x] `perception/synthetic/tools/render_dataset.py` ile plan kaydını kimlik/indeks üzerinden render et.
- [x] F16 kırmızı ile çalışan ilk BlenderProc smoke renderını üret; camgöbeği ve tam matris sonraki turda genişletilecek.
- [x] Aynı yükseklikte `3–17 m`, yedi rota konumu ve
  `4/6/8/10/12/14/16/18/20/24/28°` `topSurfaceViewDeg` uygula; yaw'ı `atan2`
  ile rota geometrisinden türet.
- [x] Siyah arka plan, nötr zemin ve iki alan ışıklı PBR smoke sahnesi kullan.
- [x] RGB, instance mask, semantic mask, depth ve kayıt metadata’sı üret; bbox validator tam batch renderer ile eklenecek.
- [x] Aynı seed ve dünya anahtarının tam/filtreli üretimde aynı metadata vermesini test et.
- [ ] Tam pilot render tamamlanınca contact sheet'i mesafe × rota-türetilmiş yaw ×
  eğim matrisi halinde üret.

### Planlanan F16 matris hacmi

```text
2 sunum sınıfı × 15 boylamasına mesafe × 7 rota konumu × 11 eğim = 2.310 kayıt
```

Bu fazda zoom yoktur. Amaç renderer/annotation/geometriyi ayırarak doğrulamaktır.

### Doğrulama

```bash
npm run dataset:cad:render:smoke
npm run dataset:cad:validate:batch -- \
  --batch perception/synthetic/generated/render_batches/smoke
```

### Çıkış kapısı

- RGB/mask/depth aynı çözünürlükte.
- Bbox instance mask'i kapsıyor.
- 15 m hedef 10 m'den, 10 m hedef 5 m'den küçük.
- Üst yüzey tüm ana eğim bucket'larında görünür.
- Sağ/sol yaw dağılımı simetrik.
- Aynı seed tekrar üretilebilir.

---

## FAZ 4 — Tüm hedefler, balon ve görev sahnesi

**Amaç:** Yedi sınıflı mevcut model sözleşmesine uygun tam sentetik sahne.

### Yapılacaklar

- [x] Drone, Helikopter, F16 ve Füze geometrilerini ortak plan/renderer hattına ekle.
- [x] Helikopter/F16 için kırmızı düşman ve camgöbeği dost materyali üret.
- [x] Drone/Füze için yalnız izin verilen kırmızı presentation class'ları kullan.
- [x] `12–16 cm` sözleşmeli procedural kırmızı balonu renderer smoke sahnesine ekle.
- [x] Balonu `targetInstanceId` ile tam bir makete bağla.
- [ ] Hedef standı, ip, ray, siyah duvar/perde, zemin ve bariyer ekle.
- [ ] Aşama 1/2/3 sahne üreticilerini ayrı profiller yap.
- [ ] Occlusion/truncation oranını metadata'ya ekle.
- [x] Dost hedef altındaki kırmızı balonun ateş adayı olmadığını ground-truth
  ilişki kaydında açıkça tut.

### Geometri profili

```toml
cameraHeightM = 1.30
targetReferenceHeightM = 1.30
longitudinalDistanceBucketsM = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]
centerRouteLateralDistanceM = 0.0
sideRouteLateralDistanceBucketsM = [2.75, 2.87, 3.0]
yawComputation = "ATAN2_SIGNED_LATERAL_OVER_LONGITUDINAL"
topSurfaceViewBucketsDeg = [4, 6, 8, 10, 12, 14, 16, 18, 20, 24, 28]
topSurfaceViewJitterDeg = 0.5
```

### Doğrulama

- Yasak class/stage kombinasyonu üretilirse batch fail.
- `balon.targetInstanceId` yok/çoğul ise batch fail.
- Friendly-linked balloon runtime label'i `fireAuthorized=false`.
- Görünür piksel ve occlusion eşikleri manifestte.

### Çıkış kapısı

Tüm sınıflar ve görev ilişkileri görsel contact sheet + otomatik validator ile
onaylanmış.

### Açı güncelleme politikası

Komite daha sonra sayısal aralık verirse yeni render zorunlu değildir. Mevcut
batch gerçek `topSurfaceViewDeg` alanına göre tahribatsız seçim manifestiyle
filtrelenir; yalnız aralık dışında eksik bucket kalırsa ek render üretilir.

---

## FAZ 5 — Zoom, çözünürlük kaybı ve kamera kusurları

**Amaç:** 3–17 m sentetik örnekleme aralığında dijital zoom'un gerçek faydasını/zararını ölçmek; 5–15 m şartname aralığını ayrıca raporlamak.

### Yapılacaklar

- [x] `perception/synthetic/tools/apply_camera_pipeline.py` oluştur.
- [x] `high_res_roi`, `scaler_crop` ve `application_crop` yollarını işlem sırası
  farklı ayrı fonksiyonlar yap.
- [x] `1.0×`, `1.5×`, `2.0×`; hard-case için `3.0×` sözleşmesini uygula.
- [x] PoC/pilot renderer'ı `2304×1296` üretip `high_res_roi` → `640×640`
  letterbox zincirinde upsample olmadığını doğrula; kamera-doğruluk alt kümesini
  daha sonra `4608×2592` üret.
- [x] Arama ara karesini `1280×720`; yüksek çözünürlüklü main'i `2304×1296`;
  model girdisini en-boy oranı korunmuş `640×640` letterbox yap.
- [x] Crop merkezi hatası, bir kare gecikmeli merkez ve kısmi target crop desteği ekle.
- [x] Codec'i RGB888 runtime yolundan çıkar; blur/noise'u kamera gerçeği değil,
  açık kimlikli araştırma profili olarak tut. H.264/JPEG yalnız gerçek yol kullanırsa eklenir.
- [x] Her base world ve zoom türevini aynı `worldId/groupId/split` içinde tut.
- [x] Zoomsuz arama + kararlı track sonrası ROI zoom + kayıpta fail-back state machine'ini uygula.

### Kesin runtime başlangıç politikası

- Sistem hedef ararken `1.0×` tam kadraj kullanır.
- Track oluşmadan yalnız zoomlu kadraja geçmez.
- Track kararlıysa `1.5×`; uzakta hedef piksel sayısı düşükse `2.0×` denenebilir.
- Track kaybolursa tam kadraja fail-back eder.
- `3.0×` ilk runtime sürümünde etkin değildir; yalnız robustness datasıdır.
- Model/ölçüm sonucu göstermeden zoom “daha iyi” kabul edilmez.

### Metrikler

Her mesafe × yaw × eğim × zoom hücresinde:

- bbox yüksekliği/genişliği ve hedef piksel sayısı;
- recall ve confidence;
- sınıf karışıklığı;
- false positive;
- crop nedeniyle kayıp hedef oranı;
- işleme süresi.

### Çıkış kapısı

- Annotation crop/resize sonrasında doğru dönüştürülüyor.
- Zoom varyantları split sızıntısı oluşturmuyor.
- 15 m için zoomsuz, 1.5× ve 2.0× ayrı raporlanıyor.
- Runtime yöntemi sentetik ablation ile araştırılır; fiziksel runtime seçimi gerçek veri fazında kilitlenir.

---

## FAZ 6 — Camera Module 3 kalibrasyon ve yakalama araçları

**Amaç:** Varsayımsal kamera yerine gerçek kamera profilini üretmek.

### Yapılacaklar

- [ ] `perception/synthetic/tools/capture_calibration.py` oluştur.
- [ ] Checkerboard capture ve metadata dump ekle.
- [ ] `perception/synthetic/tools/calibrate_camera.py` ile OpenCV `K` ve distortion
  çıkar.
- [ ] `perception/synthetic/tools/capture_zoom_pairs.py` oluştur.
- [ ] `config/calibration/camera.toml` ile sentetik camera profile arasında açık
  converter yaz.
- [ ] `UNVERIFIED` profilin production render üretmesini engelle.
- [ ] BlenderProc K-matrix ve lens-distortion hattını gerçek profil ile besle.

### Faz sınırı

Bu faz CAD/sentetik implementasyonundan sonra ele alınır. Şimdilik blocker değildir;
fiziksel kamera geldiğinde araçlar ve kabul metrikleri gerçek oturumla doğrulanır.

### Doğrulama

- Checkerboard reprojection error raporu.
- Sentetik distortion grid ile kalibrasyon modelinin sayısal eşleşmesi.
- Gerçek/sentetik zoom pair keskinlik ve piksel-boyutu karşılaştırması.
- Kalibrasyon hash'i dataset manifestine yazılmış.

### Çıkış kapısı

`cameraProfile.status = VERIFIED_PHYSICAL` ve kaynak oturum hash'leri mevcut.

---

## FAZ 7 — Gerçek boş arka plan ve hibrit kompozisyon

**Amaç:** CAD hedefleri gerçek kamera gürültüsü ve gerçek parkur bağlamına taşımak.

### Yapılacaklar

- [ ] `perception/synthetic/tools/capture_backgrounds.py` oluştur.
- [ ] `perception/dataset/captures/backgrounds/<sessionId>/session.json`
  sözleşmesini ekle.
- [ ] Background split'ini görüntü değil `sessionId` ile yap.
- [ ] `perception/synthetic/tools/compose_hybrid.py` oluştur.
- [ ] Alpha/depth/gölge eşleşmesi ve kenar halo denetimi ekle.
- [ ] Hard-negative kayıtları hedefsiz tut; yanlışlıkla annotation üretme.
- [ ] Background kimliği ile sınıf arasında korelasyon denetimi ekle.

### Ertelenmiş fiziksel faz sınırı

Bu faz CAD/sentetik implementasyonundan sonra gerçek kamera erişimiyle yürütülür.

### Çıkış kapısı

- Aynı background session train ve val/test'e sızmıyor.
- Hedef kenarında halo/renk taşması otomatik ve görsel kontrolden geçiyor.
- Hedefsiz gerçek background'larda false positive metriği raporlanıyor.

---

## FAZ 8 — Mevcut dataset pipeline entegrasyonu

**Amaç:** Yeni renderer'ı mevcut güvenli veri sözleşmesine bağlamak.

### Yapılacaklar

- [x] `perception/tools/dataset_pipeline.py` içine HDF5 render batch ingest ekle.
- [x] Mevcut `synthetic_seed_2d` üretimini smoke amaçlı koru.
- [x] CAD geometri/materyal profillerini `perception/synthetic/config/` altında ayrı tut.
- [x] CAD kayıtlarında `worldId` tabanlı stable split uygula.
- [x] Sentetik CAD için yalnız train/val üret; gerçek test'i sentetikle doldurma.
- [x] CAD ingest için `trainingAuthorized=false` ve `releaseCandidate=false` değerlerini zorunlu tut.
- [ ] Gerçek veri geldikten sonra genel `trainingAuthorized` hesabını şu koşullara bağla:
  - bağımsız gerçek val ve test session;
  - boş review queue;
  - geçerli camera/calibration hash;
  - açık model/release sözleşmesi.
- [ ] Tam batch üretiminde renderer, BlenderProc, Blender, asset, camera, material,
  scene ve postprocess hash zincirini dataset manifestine ekle; smoke ingest HDF5 ve görüntü hash'lerini taşır.

### Regresyon testleri

```bash
.venv-perception/bin/python -m pytest \
  tests/test_dataset_pipeline.py \
  tests/test_synthetic_dataset_ingest.py \
  tests/test_synthetic_world_split.py
npm run dataset:prepare
```

### Çıkış kapısı

- Mevcut 2B smoke pipeline bozulmuyor.
- CAD kaynakları izlenebilir.
- Sentetik veri tek başına `trainingAuthorized=true` yapamıyor.

---

## FAZ 9 — Pilot dataset ve araştırma ablation'ı

**Amaç:** Büyük veri üretmeden önce en yararlı render bileşimini seçmek.

### Pilot ve tam plan hacmi

Tam rota planı:

```text
6 presentation class × 15 boylamasına mesafe × 7 rota konumu × 11 eğim
= 6.930 temel dünya
```

İlk pilot, tam plan içinden `5/10/15 m` boylamasına mesafe ve `8/16/24°` eğim
seçerek `6 × 3 × 7 × 3 = 378` dünya üretir. Yaw ayrıca çarpılmaz; rota
geometrisinden gelir. Zoom türevleri ayrı `variantId` olur. Stratified `%40` alt
kümeye `1.5×/2.0×`, `%10` hard-case alt kümeye `3.0×` uygulanır.

### Deneyler

- `B0`: yalnız mevcut `synthetic_seed_2d`;
- `B1`: yalnız `synthetic_cad_pbr`;
- `B2`: PBR + geometri/yaw/eğim randomization;
- `B3`: B2 + kamera kusurları;
- `B4`: B3 + zoom türevleri;
- `B5`: B4 + hybrid background;
- `B6`: sentetik pretrain + gerçek fine-tune (AR-09 sonrası);
- `B7`: yalnız gerçek veri baseline'ı (AR-09 sonrası).

### Model kararı

- İlk bütün deneyler YOLOv8n ve `640×640` ile yapılır.
- Dataset etkisi ile mimari etkisi aynı deneyde değiştirilmez.
- Başka model ancak aynı real-only validation split'inde belirgin kazanç veya
  Hailo uyumluluk sorunu gösterilirse ayrı ADR ile değerlendirilir.

### Araştırma raporu

Her deney için:

- sınıf bazlı precision/recall/mAP;
- 5/10/15 m recall;
- yaw ve `topSurfaceViewDeg` bucket metriği;
- zoom modu/faktörü metriği;
- dost→düşman kritik karışıklık;
- balon association hatası;
- background-only false positive/minute;
- eğitim süresi ve model hash'i.

### Çıkış kapısı

Kazanan sentetik reçete seçilir fakat durum hâlâ
`SYNTHETIC_RESEARCH_ONLY` olur.

---

## FAZ 10 — Hareketli sekans, takip ve zoom state machine

**Amaç:** Tek kare başarısını takip/nişan davranışı sanmamak.

### Yapılacaklar

- [ ] Aynı target `trackId` ile hareketli BlenderProc sekansları üret.
- [ ] Parkur kolları, bariyere giriş/çıkış, yeniden görünme ve hız değişimi ekle.
- [ ] RGB + depth + optical flow + pose + track metadata üret.
- [ ] Hareketli CAD sekansı üretildikten sonra Detector → tracker → backend bridge replay testini çalıştır.
- [x] Zoom state machine'i uygula:
  - `SEARCH_FULL_FRAME`;
  - `TRACK_CONFIRMING`;
  - `TRACK_ROI_1_5X`;
  - `TRACK_ROI_2X`;
  - `LOST_FAILBACK`.
- [x] Zoom crop merkezinde bir kare gecikme ve ölçüm jitter'ı test et.
- [x] Track stale/low-confidence olduğunda tam kadraja dön; zoom kararı hiçbir zaman atış yetkisi üretmez.

### Çıkış kapısı

- Track ID kararlılığı raporlanıyor.
- Zoom hedefi kadrajdan çıkardığında tam kadraja dönüş var.
- Dost hedef/bağlı balon hiçbir replay'de fire candidate olmuyor.
- Sentetik replay fiziksel HIL olarak adlandırılmıyor.

---

## FAZ 11 — Gerçek veri, sim-to-real ve materyal düzeltmesi

**Amaç:** Sentetik kısa yolları gerçek kamera verisiyle kırmak.

### Zorunlu durak

- Fiziksel renk/malzeme ölçümü gerçek veri fazında ek kalibrasyon girdisidir.
- `AR-09`: gerçek hedef oturumları.

### Yapılacaklar

- [ ] Gerçek session importunu mevcut idempotent SHA-256 hattından yap.
- [ ] Oturumları gün/ışık/mesafe olarak grupla; kare bazlı split yapma.
- [ ] Annotation'ları insan incelemesinden geçir.
- [ ] En az bir real-only validation ve bir real-only test session ayır.
- [ ] `B6` ve `B7` deneylerini çalıştır.
- [ ] Sentetik/gerçek karışım oranını real-only validation ile seç.
- [ ] 15 m, sağ/sol yaw, `4–28°` örneklenmiş eğim ve zoom bucket'larında hata analizi yap.
- [ ] Gerçekte görülen hata bucket'ları için targeted synthetic generation üret.

### Release için başlangıç kabul eşikleri

Bu eşikler yarışma riskine göre repo default'u olarak kullanılacak; değişiklik ADR
ve gerçek test kanıtı gerektirir:

- friendly-linked balloon fire candidate: `0`;
- unlinked balloon fire candidate: `0`;
- dost hedefin düşman sınıflandırılması: real-only testte `≤ %1`;
- 15 m hedef recall: `≥ %85`;
- background-only false positive: `≤ 1/dakika`;
- zoom etkinleştirme: 15 m recall'da en az `+5 yüzde puan` kazanç ve kritik
  false-positive metriğinde kötüleşme yok;
- annotation review queue: `0`.

Eşik sağlanmıyorsa Safety Gate gevşetilmez; veri/model/zoom stratejisi düzeltilir.

### Çıkış kapısı

- `trainingAuthorized=true` yalnız gerçek kapılarla oluşmuş.
- Kazanan checkpoint real-only testte raporlanmış.
- Dataset/model/calibration hash'leri kayıtlı.

---

## FAZ 12 — ONNX, HEF ve Raspberry Pi kabulü

**Amaç:** Eğitim modelini gerçek deployment zincirinde doğrulamak.

### Yapılacaklar

- [ ] Kazanan modeli ONNX'e export et.
- [ ] FP32 ↔ ONNX çıktı eşdeğerliğini sabit regression setinde ölç.
- [ ] Quantization calibration için temsilî **gerçek** kamera kareleri kullan.
- [ ] HEF üret.
- [ ] FP32 ↔ ONNX ↔ HEF bbox/class/score toleranslarını raporla.
- [ ] Pi 5 + Hailo-8 üzerinde `1280×720 @ 30 FPS` capture ile latency/FPS ölç.
- [ ] Zoom state machine, tracker, backend bridge ve Safety Gate ile soak test yap.
- [ ] Model/dataset/calibration/runtime sürümlerini release manifestine yaz.

### Zorunlu durak

`AR-10` olmadan HEF ve gerçek Pi/Hailo kabulü tamamlanamaz.

### Çıkış kapısı

- Gerçek HEF hash'i ve HailoRT sürümü var.
- Gerçek kamera latency/FPS ölçümü var.
- Uzun süreli soak ve rollback kanıtı var.
- LIVE preflight `UNVERIFIED` fiziksel kanıtla geçilmiş.

---

## FAZ 13 — Sürekli iyileştirme

**Amaç:** Yarışma öncesi yeni veriyi test setini kirletmeden kullanmak.

### Yapılacaklar

- [ ] Düşük güven, yanlış pozitif, ID switch ve zoom-fail karelerini kuyruğa al.
- [ ] Yeni gerçek oturumları session bazında ekle.
- [ ] Eski real-only test setini sabit regression seti olarak koru.
- [ ] Hata bucket'ına yönelik yeni sentetik reçete üret.
- [ ] Her renderer/model değişiminde eski gerçek testte regression çalıştır.
- [ ] Renderer, dataset ve model semver/hash zincirini sürdür.

### Çıkış kapısı

Yeni sürüm eski gerçek test setinde kritik güvenlik metriğini geriletmiyor ve yeni
hata bucket'ında ölçülebilir iyileşme sağlıyor.

---

## 4. Planlanan repo yapısı

```text
requirements/
  synthetic-render.lock

perception/synthetic/
  README.md
  schema/
    cad-source.schema.json
    cad-asset-manifest.schema.json
    render-batch.schema.json
    render-record.schema.json
  config/
    cad_source.json
    cad_asset_manifest.json
    render.toml
    camera_profiles/
      camera_module_3_provisional.toml
      camera_module_3_calibrated.toml
    material_profiles/
      nominal_colors.toml
    scene_profiles/
      committee_tilted_targets_sweep_v1.toml
  tools/
    inspect_3mf.py
    convert_cad_assets.py
    render_dataset.py
    apply_camera_pipeline.py
    validate_render_batch.py
    build_contact_sheet.py
    capture_calibration.py
    calibrate_camera.py
    capture_zoom_pairs.py
    capture_backgrounds.py
    compose_hybrid.py
  generated/                         # gitignore
    inspection/
    normalized_assets/
    render_batches/
    contact_sheets/

perception/dataset/captures/
  backgrounds/                       # ağır veri git dışında

tests/
  test_synthetic_contracts.py
  test_synthetic_3mf_inspection.py
  test_synthetic_asset_normalization.py
  test_synthetic_lod.py
  test_synthetic_render_annotations.py
  test_synthetic_camera_pipeline.py
  test_synthetic_dataset_ingest.py
  test_synthetic_world_split.py
```

---

## 5. Her implementasyon turunda çalışma sırası

Her turda aşağıdaki sıra korunacak:

1. **Sözleşmeyi yaz/güncelle.** Alan adı ve durumlar koddan önce belli olacak.
2. **Dar regresyon testini yaz.** Mevcut davranış veya yeni invariant kilitlenecek.
3. **En küçük üretim kodunu ekle.** Bir fazda birden fazla belirsiz soyutlama yok.
4. **Dar testi çalıştır.** Başarısızsa sonraki faza geçme.
5. **Smoke artifact üret.** JSON rapor/contact sheet veya küçük render.
6. **Artifact'i gerçekten aç/incele.** Yalnız exit code'a güvenme.
7. **Tam ilgili test grubunu çalıştır.** Dataset/perception regresyonu.
8. **Manifest ve hash'i kaydet.** Üretilmiş binary'yi Git'e ekleme.
9. **Çıkış kapısını değerlendir.** Kanıt yoksa checkbox kapatma.
10. **ACTION REQUIRED varsa dur.** Gerekli kullanıcı girdisini tek listede bildir.

---

## 6. Commit sınırları

İmplementasyon sırasında önerilen küçük ve geri alınabilir commitler:

1. `feat(perception): add synthetic CAD contracts and tooling environment`
2. `feat(perception): inspect and normalize 3mf target assets`
3. `feat(perception): add deterministic BlenderProc render smoke`
4. `feat(perception): model target poses balloons and stage scenes`
5. `feat(perception): add digital zoom and camera degradation pipeline`
6. `feat(perception): add camera calibration and background capture tools`
7. `feat(perception): ingest CAD render manifests into dataset pipeline`
8. `test(perception): add synthetic video and zoom replay coverage`
9. `feat(perception): add real-data ablation and deployment evidence gates`

Her commit öncesi en az `git diff --check` ve ilgili dar test çalıştırılacak.

---

## 7. Tam doğrulama matrisi

### Doküman ve şema

```bash
git diff --check
.venv/bin/python -m json.tool perception/synthetic/config/cad_source.json >/dev/null
.venv/bin/python -m json.tool perception/synthetic/config/cad_asset_manifest.json >/dev/null
```

### Sentetik araçlar

```bash
.venv-synthetic/bin/python -m pytest tests/test_synthetic_*.py
npm run dataset:cad:render:smoke
npm run dataset:cad:validate:batch -- --batch <batch-path>
```

### Dataset ve eğitim hattı

```bash
.venv-perception/bin/python -m pytest \
  tests/test_dataset_pipeline.py \
  tests/test_perception_bridge.py \
  tests/test_phase9_sensor_fusion.py
npm run dataset:prepare
.venv-perception/bin/python perception/tools/train_yolo.py \
  --allow-unverified --dry-run
```

### Repo regresyonu

```bash
.venv/bin/python -m pytest
npm run typecheck
npm run build
npm run dev:check
```

### Fiziksel kanıt gerektiren ve yerelde taklit edilemeyecek kontroller

- Camera Module 3 gerçek calibration/zoom pair;
- gerçek boş parkur/background session;
- gerçek hedef 5/10/15 m session;
- gerçek materyal ve ışık davranışı;
- Hailo HEF eşdeğerliği;
- Pi latency/FPS;
- fiziksel HIL, soak ve rollback.

Bunlar çalıştırılmadan “tam entegre”, “sahada doğrulandı” veya “release hazır”
ifadesi kullanılmayacak.

---

## 8. Tamamlanan implementasyon turları

### Tur 1 — tamamlandı

- FAZ 0 sözleşme ve bağımlılık iskeleti.
- FAZ 1 deterministik 3MF inspection ve contact sheet.

### Tur 2 — tamamlandı; rota geometrisi V2’ye geçildi

- Bambu Front/Top matematik sözleşmesi.
- 6.930 kayıtlık rota-türetilmiş yaw, mesafe, eğim ve görünüm render planı.
- Gerçek açıya göre tahribatsız seçim manifesti.
- Dört CAD varlığı için LOD0/1/2 ve siluet/bbox kabulü.
- Blender 4.2.1 + BlenderProc RGB/depth/segmentation smoke renderı.
- 3MF gerçek ölçüleri kilitlendi; CAD/sentetik implementasyon sonraki fazlarla sürer.

---

## 9. Nihai tamamlanma tanımı

### Araştırma pipeline'ı tamamlandı

- Dört CAD hedefi hash/ölçek/yön manifestinde.
- Aynı yükseklik, rota-türetilmiş sağ/sol yaw, `4–28°` örneklenmiş üst-yüzey görünümü ve `3–17 m`
  renderları var.
- PBR, DR, zoom/degradasyon ve hybrid kaynakları izlenebilir.
- Bbox/mask/depth/pose/association testleri geçiyor.
- World/session split sızıntısı yok.
- YOLOv8n ablation raporu var.
- Sonuç `SYNTHETIC_RESEARCH_ONLY` olarak işaretli.

### Sim-to-real tamamlandı

- Gerçek camera calibration ve zoom pairs mevcut.
- Gerçek hedef session'ları train/val/test olarak grup ayrılmış.
- Annotation insan incelemesinden geçmiş.
- B6/B7 real-only kıyası yapılmış.
- Kritik güvenlik ve 15 m recall eşikleri sağlanmış.

### Deployment tamamlandı

- ONNX/HEF eşdeğerliği ölçülmüş.
- Pi 5 + Hailo-8 gerçek kamera latency/FPS ve soak kanıtı var.
- Dataset/model/calibration/HEF hash'leri release manifestinde.
- Safety Gate dışında hiçbir algı çıktısı doğrudan atış yetkisi üretmiyor.

---

## 10. Teknik referanslar

- Güncel hedef/parkur sözleşmesi:
  [`hedef_ve_parkur_operasyon_guncellemesi.md`](hedef_ve_parkur_operasyon_guncellemesi.md)
- Mevcut veri/model planı:
  [`hedef_gorseli_yolo_veri_plani.md`](hedef_gorseli_yolo_veri_plani.md)
- Mevcut model sözleşmesi:
  [`../perception/models/target_detector_contract.json`](../perception/models/target_detector_contract.json)
- 3MF Consortium `lib3mf`: <https://github.com/3MFConsortium/lib3mf>
- 3MF Core Specification: <https://github.com/3MFConsortium/spec_core>
- BlenderProc ana dokümantasyon: <https://dlr-rm.github.io/BlenderProc/>
- BlenderProc `2.8.0` paketi: <https://pypi.org/project/blenderproc/2.8.0/>
- BlenderProc kamera intrinsics/extrinsics:
  <https://dlr-rm.github.io/BlenderProc/docs/tutorials/camera.html>
- BlenderProc lens distortion:
  <https://dlr-rm.github.io/BlenderProc/examples/advanced/lens_distortion/README.html>
- BlenderProc RGB/depth/segmentation/optical flow:
  <https://dlr-rm.github.io/BlenderProc/docs/tutorials/renderer.html>
- Raspberry Pi Camera Module 3 product brief:
  <https://datasheets.raspberrypi.com/camera/camera-module-3-product-brief.pdf>
- Picamera2 manual:
  <https://datasheets.raspberrypi.com/camera/picamera2-manual.pdf>
