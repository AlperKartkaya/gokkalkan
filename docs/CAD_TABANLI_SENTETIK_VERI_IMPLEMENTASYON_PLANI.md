# CAD Tabanlı Sentetik Veri — Adım Adım İmplementasyon Planı

> **Durum:** Uygulamaya hazır teknik plan
> **Tarih:** 14 Ağustos 2026
> **Ana roadmap:** [`CAD_TABANLI_SENTETIK_VERI_VE_MODEL_GELISTIRME_ROADMAP.md`](CAD_TABANLI_SENTETIK_VERI_VE_MODEL_GELISTIRME_ROADMAP.md)
> **Kapsam:** `Modeller.3mf` → gerçekçi sentetik görüntü → zoom/degradasyon → araştırma modeli → gerçek veriyle sim-to-real → ONNX/HEF
> **Güvenlik sınırı:** Sentetik başarı fiziksel kabul veya atış yetkisi değildir. Backend Safety Gate bütün aşamalarda nihai yetki kapısıdır.

> **Uygulama ilerlemesi — 14 Ağustos 2026:** FAZ 0 ve FAZ 1 tamamlandı.
> `Modeller.3mf` beklenen hash ile doğrulandı; dört kaynak-eksen contact sheet'i
> üretildi. Uygulama `AR-01` ve `AR-02` girdileri için durduruldu. Ayrıntılı cevap
> şablonu:
> [`perception/synthetic/ACTION_REQUIRED_AR_01_AR_02.md`](../perception/synthetic/ACTION_REQUIRED_AR_01_AR_02.md).

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

Dünya ve nesne koordinatları tek bir kanonik sözleşmeyle tutulacak:

- Dünya ekseni: `+Z = yukarı`.
- Kanonik hedef ekseni: `+X = burun/ileri`, `+Y = hedefin solu`, `+Z = üst yüzey`.
- Kamera ve hedef referans merkezi başlangıçta aynı dünya yüksekliğinde olacak:
  `cameraHeightM = targetReferenceHeightM = 1.30`.
- Kamera yüksekliğinden kaynaklanan dikey bakış açısı temel durumda `0°` olacak.
- Montaj/zemin toleransı için yalnız `cameraElevationOffsetDeg ∈ [-1°, +1°]`
  robustness örnekleri üretilecek. Geniş aşağıdan/yukarıdan görüşler ana veri setine
  alınmayacak.
- Hedefler üst yüzey görünecek biçimde burunları aşağı eğimli kabul edilecek.
  Ham Euler işareti yerine anlaşılır `topSurfaceViewDeg` alanı kullanılacak.
- İlk mühendislik profili:
  - `topSurfaceViewDeg`: `8°`, `12°`, `18°`
  - nominal: `12°`
  - her bucket için en fazla `±1.5°` jitter
- Hedefin sağdan/soldan görünümü simetrik üretilecek:
  - `viewYawDeg`: `-25°`, `-15°`, `-5°`, `0°`, `+5°`, `+15°`, `+25°`
  - her bucket için en fazla `±2°` jitter
  - negatif: kamera hedefin sağ tarafını daha çok görür;
  - pozitif: kamera hedefin sol tarafını daha çok görür.
- `viewYawDeg` hedef pozu ile kamera pan açısını birbirine karıştırmayacak;
  manifestte ikisi ayrı alan olacak.

> `8°–18°` burun eğimi komite tarafından sayısal olarak verilmiş bir değer
> değildir. PoC ve araştırma için kilitlenen **geçici mühendislik aralığıdır**.
> Fiziksel/komite ölçümü gelince `committee_tilted_targets_v1` profili sürümlenerek
> güncellenecek; eski dataset yeniden üretilebilir kalacak.

### 1.3. Mesafe örneklemesi

- Yarışma anchor'ları: tam `5.0 m`, `10.0 m`, `15.0 m`.
- Ana renderların `%70`i bu üç anchor arasında dengeli dağıtılacak.
- Ana renderların `%30`u `5.0–15.0 m` sürekli uniform örneklenecek.
- Test/rapor bucket'ları her zaman ayrı `5 m`, `10 m`, `15 m` olarak gösterilecek.
- Aynı hedefin mesafe, yaw, eğim, ışık ve zoom türevleri aynı `worldId` altında
  kalacak; split sızıntısı olmayacak.

### 1.4. Zoom ve çözünürlük kaybı

Camera Module 3 üzerinde optik zoom yoktur. Bu nedenle iki ayrı dijital zoom yolu
modellenip karşılaştırılacak:

1. **`sensor_roi`** — yüksek çözünürlüklü sensör alanı önce kırpılır, sonra
   `1280×720` çıkışa ölçeklenir. Picamera2 `ScalerCrop` davranışına yakın adaydır.
2. **`application_crop`** — mevcut `1280×720` kare kırpılır ve tekrar
   `1280×720` boyutuna büyütülür. Detay kaybı daha yüksektir.

Kesin zoom bucket'ları:

- ana veri: `1.0×`, `1.5×`, `2.0×`;
- yalnız hard-case/robustness: `3.0×`;
- model girdisi: mevcut sözleşmeye uygun `640×640` letterbox.

İşlem sırası değişmeyecek:

```text
sahne renderı
→ sensör/uygulama crop'u
→ 1280×720 runtime karesi
→ blur + noise + sıkıştırma + sharpening profili
→ 640×640 model letterbox
```

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

İmplementasyon sırasında ajan şu kurala göre çalışacak:

1. Bulunduğu fazdaki otomatik ve bağımsız işleri tamamlar.
2. Sonraki gerekli iş aşağıdaki blocker'lardan birine bağlıysa `ACTION REQUIRED`
   başlığıyla gereken girdiyi ve beklenen dosyayı bildirir.
3. Blocker'ı geçmiş gibi işaretlemez; fiziksel/manuel kanıt gelene kadar durur.
4. Kullanıcı çıktıyı repoya eklediğinde veya yolu verdiğinde hash/format kontrolü
   yapar ve kaldığı fazdan devam eder.
5. Blocker yalnız sonraki bağımlı fazı durduruyorsa diğer bağımsız test/doküman
   işleri sürdürülebilir.

### AR-01 — CAD kaynağı ve ekip erişimi

**Ne zaman durulur:** CAD-1 sonunda, tam ekip/CI tekrarlanabilirliği başlamadan önce.
**Kullanıcı aksiyonu:**

- `Modeller.3mf` dosyasının kimden/hangi kaynaktan geldiğini ve takım içinde
  kullanma/dönüştürme iznini doğrula.
- Dosyayı takımın erişebileceği haricî depoya koy; paylaşılabilir URL veya artifact
  kimliği sağla. Tercih: haricî depolama + SHA-256; normal Git'e ekleme yok.
- Beklenen hash:
  `9f696bf7aa8c5c0dc2fa1e733266e6e9c274494bc2f210c3bc40b8975fb47028`.

**Beklenen çıktı:** `perception/synthetic/config/cad_source.json` içindeki
`sourceUri`, `licenseOrPermission`, `sha256`, `owner` alanlarının doldurulması.
**Blokladığı iş:** Başka makinede/CI'da full-CAD renderı ve türetilmiş asset dağıtımı.
**Bloklamadığı iş:** Yerel inspect aracı, şema/testler ve küçük test fixture'ı.

### AR-02 — Burun/üst yön doğrulaması

**Ne zaman durulur:** Otomatik altı-yüz contact sheet üretildikten sonra.
**Kullanıcı aksiyonu:** Her hedef için işaretlenen `BURUN` ve `ÜST` yönünü onayla.
Contact sheet yeterli değilse Bambu Studio'da modeli açıp eksen gismosu görünür
şekilde ön/üst görünüş ekran görüntüsü al. Blender kullanman varsayılan olarak
gerekmez.

**Beklenen çıktı:**

- Drone, Helikopter, F16 ve Füze için `noseAxis` ve `upAxis` onayı;
- gerekirse `docs/evidence/cad_orientation/` altında ekran görüntüsü.

**Blokladığı iş:** Nihai normalization transformu, yaw işareti ve eğim uygulaması.
**Bloklamadığı iş:** Geometri parse/LOD PoC'si.

### AR-03 — Fiziksel hedef boyutları

**Ne zaman durulur:** Ölçek manifesti `provisional` durumundan çıkarılmadan önce.
**Kullanıcı aksiyonu:** Komitenin/imalatın son ölçüsünü onayla veya gerçek baskıyı
ölç. Başlangıçta kullanılacak değerler:

- Drone: `300 mm`;
- Füze: `400 mm`;
- Helikopter: `500 mm`;
- F16: `500 mm`.

**Beklenen çıktı:** Ölçü kaynağı ve tarih; mümkünse fotoğraflı metre/kumpas kanıtı.
**Blokladığı iş:** `cad_asset_manifest.json` durumunun `VERIFIED_SCALE` olması ve
calibrated dataset üretimi.
**Bloklamadığı iş:** Yukarıdaki değerlerle `PROVISIONAL_SCALE` araştırma renderı.

### AR-04 — Burun eğimi/jig açısı

**Ne zaman durulur:** `committee_tilted_targets_v1` üretim profili kilitlenmeden önce.
**Kullanıcı aksiyonu:** Komite sayısal açı verirse kaydet; vermiyorsa imalat standı
veya hedef üzerinde telefon inclinometer/iletki ile burun-aşağı açıyı ölç. En az
nominal ve mekanik min/max değeri gerekli.

**Beklenen çıktı:** `minDeg`, `nominalDeg`, `maxDeg`, ölçüm yöntemi ve tarih.
**Blokladığı iş:** Gerçek düzeni temsil ettiği iddia edilen production render profili.
**Bloklamadığı iş:** `8°/12°/18°` araştırma profili.

### AR-05 — Camera Module 3 kalibrasyonu

**Ne zaman durulur:** Kamera-doğrulu render ve hibrit dataset öncesi.
**Kullanıcı aksiyonu:** Gerçek Pi 5 + Camera Module 3 Standard ile sağlanacak
çekim scriptini çalıştır:

- checkerboard görüntüleri;
- kullanılacak `1280×720 @ 30 FPS` video modu;
- sabit/otomatik focus, exposure, gain ve AWB metadata'sı;
- kamera taret üzerinde son yerine takılıyken boresight/extrinsic ölçümü.

**Beklenen çıktı:** Hash'li calibration oturumu ve `K`, distortion, çözünürlük,
focus/exposure profili.
**Blokladığı iş:** `camera_calibrated_v1` renderı ve lens-distortion eşleşmesi.
**Bloklamadığı iş:** Provisional pinhole/PBR/DR araştırma renderı.

### AR-06 — Boş arka plan kayıtları

**Ne zaman durulur:** Hibrit dataset üretiminden önce.
**Kullanıcı aksiyonu:** Sağlanacak capture komutuyla Camera Module 3 üzerinden:

- siyah perde/duvar;
- zemin, ray, stand, kablo ve güvenlik bariyeri;
- farklı ışık/exposure;
- hareketli mekanizma ama hedefsiz sahne;
- kırmızı/camgöbeği ilgisiz nesne hard-negative;
- lens kapalı dark-frame

oturumlarını kaydet.

**Beklenen çıktı:** Her oturumda benzersiz `sessionId`, ortam/ışık metadata'sı ve
video/kare hash'leri.
**Blokladığı iş:** `synthetic_cad_hybrid`.
**Bloklamadığı iş:** Saf PBR ve domain-randomized render.

### AR-07 — Zoom davranışı için gerçek kamera örneği

**Ne zaman durulur:** Runtime zoom yöntemi kilitlenmeden önce.
**Kullanıcı aksiyonu:** Aynı durağan sahneyi ve aynı hedef/kalibrasyon levhasını:

- zoomsuz `1280×720`;
- Picamera2 `ScalerCrop` ile `1.5×` ve `2.0×`;
- zoomsuz kareden yazılım crop ile `1.5×` ve `2.0×`

kaydet. Kamera focus/exposure metadata'sını koru.

**Beklenen çıktı:** Aynı `sceneId` altında eşleştirilmiş zoom örnekleri.
**Blokladığı iş:** `sensor_roi` ile `application_crop` arasındaki runtime seçimi.
**Bloklamadığı iş:** Her iki yöntemin sentetik üretimi ve yazılım ablation'ı.

### AR-08 — Renk ve malzeme karakterizasyonu

**Ne zaman durulur:** Kamera-kalibre materyal profili öncesi.
**Kullanıcı aksiyonu:** Gerçek baskı/paint sample geldiğinde kırmızı ve camgöbeği
numuneyi Camera Module 3 ile en az üç ışıkta, bir renk referansı yanında çek.

**Beklenen çıktı:** `material_sessionId`, kullanılan boya/filament, mat/parlak
bilgisi ve ham görüntüler.
**Blokladığı iş:** `material_camera_measured_v1`.
**Bloklamadığı iş:** Nominal `#F50A0A`/`#00A3E0` dar randomization profili.

### AR-09 — Gerçek hedef oturumları

**Ne zaman durulur:** Fine-tuning ve release metriği öncesi.
**Kullanıcı aksiyonu:** Gerçek hedefleri ayrı gün/ışık oturumlarında; `5/10/15 m`,
sağ/sol yaw, nominal/min/max burun eğimi, zoomsuz/zoomlu ve hareketli biçimde
çek. Aynı oturumu train ve test için bölme.

**Beklenen çıktı:** Session bazlı ham veri + insan gözünden geçirilmiş annotation.
**Blokladığı iş:** Real-only validation/test, releaseCandidate ve fiziksel model kabulü.
**Bloklamadığı iş:** Araştırma eğitimi, replay ve deployment smoke.

### AR-10 — Hailo donanımı ve dönüşüm ortamı

**Ne zaman durulur:** HEF eşdeğerlik ve Pi latency kabulünde.
**Kullanıcı aksiyonu:** Pi 5 + AI HAT+ 26 TOPS/Hailo-8, uyumlu HailoRT ve HEF
compiler ortamını erişilebilir kıl.

**Beklenen çıktı:** Cihaz/SDK sürümü, model/HEF hash'i ve ölçüm logları.
**Blokladığı iş:** HEF/Pi canlı kabulü ve soak.
**Bloklamadığı iş:** ONNX export ve mock runner testleri.

---

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

### Zorunlu durak

- `AR-01` ekip erişimi/provenance.
- `AR-02` burun ve üst yön onayı.

---

## FAZ 2 — Normalizasyon, ölçek ve LOD

**Amaç:** Master 3MF'yi bozmadan render varlıklarını üretmek.

### Yapılacaklar

- [ ] `perception/synthetic/tools/convert_cad_assets.py` oluştur.
- [ ] Contact sheet onayına göre her mesh'i kanonik `+X nose / +Z up` eksenine
  dönüştür.
- [ ] Ölçekleri manifestte uygula, mesh dosyasına sessizce bake etme.
- [ ] `LOD0`, `LOD1`, `LOD2` üret.
- [ ] Her LOD için hash, bbox, triangle count, transform ve fiziksel uzunluk yaz.
- [ ] LOD siluet ve 2B bbox sapmasını canonical camera views üzerinde ölç.
- [ ] Procedural balon ve ip varlığının ilk sürümünü üret.

### İlk ölçek katsayıları

| Varlık | Katsayı | Durum |
| --- | ---: | --- |
| F16 | `1.000` | provisional/uyumlu |
| Helikopter | `0.858` | provisional |
| Drone | `0.800` | provisional |
| Füze | `0.800` | provisional |

### Kabul kuralı

- LOD2 siluet IoU: canonical görünüşlerde `≥ 0.98`.
- LOD2 bbox kenar farkı: en fazla `2 px` @ `1280×720` referans görünüşü.
- Bozuk/non-manifold geometri loglanır; sessiz onarım yapılmaz.

### Doğrulama

```bash
npm run dataset:cad:convert
.venv-synthetic/bin/python -m pytest \
  tests/test_synthetic_asset_normalization.py \
  tests/test_synthetic_lod.py
```

### Çıkış kapısı

- Dört hedef aynı koordinat sözleşmesinde.
- Ölçek ve yön manifestten okunuyor.
- LOD kabul kontrolleri geçiyor.

### Blocker

`AR-03` gelene kadar durum `PROVISIONAL_SCALE` kalır; PoC devam edebilir.

---

## FAZ 3 — Tek nesneli BlenderProc PoC

**Amaç:** Önce küçük, deterministik ve görsel olarak denetlenebilir render zinciri.

### Yapılacaklar

- [ ] `perception/synthetic/tools/render_dataset.py` ilk sürümünü oluştur.
- [ ] Önce F16 kırmızı/camgöbeği ile çalış.
- [ ] Aynı yükseklik, `5/10/15 m`, yedi yaw bucket ve `8/12/18°`
  `topSurfaceViewDeg` uygula.
- [ ] Siyah perde, nötr zemin ve tek PBR ışık profili kullan.
- [ ] RGB, instance mask, semantic mask, depth, bbox ve metadata üret.
- [ ] Aynı seed'in byte-identical metadata ve aynı annotation üretmesini test et.
- [ ] Contact sheet'i mesafe × yaw × eğim matrisi halinde üret.

### Smoke hacmi

```text
2 materyal × 3 mesafe × 7 yaw × 3 eğim = 126 temel dünya
```

Bu fazda zoom yoktur. Amaç renderer/annotation/geometriyi ayırarak doğrulamaktır.

### Doğrulama

```bash
npm run dataset:cad:render:smoke
npm run dataset:cad:validate -- \
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

- [ ] Drone, Helikopter, F16 ve Füze geometrilerini ekle.
- [ ] Helikopter/F16 için kırmızı düşman ve camgöbeği dost materyali üret.
- [ ] Drone/Füze için yalnız izin verilen kırmızı presentation class'ları kullan.
- [ ] `12–16 cm` procedural kırmızı balon üret.
- [ ] Balonu `targetInstanceId` ile tam bir makete bağla.
- [ ] Hedef standı, ip, ray, siyah duvar/perde, zemin ve bariyer ekle.
- [ ] Aşama 1/2/3 sahne üreticilerini ayrı profiller yap.
- [ ] Occlusion/truncation oranını metadata'ya ekle.
- [ ] Dost hedef altındaki kırmızı balonun ateş adayı olmadığını ground-truth
  ilişki kaydında açıkça tut.

### Geometri profili

```toml
cameraHeightM = 1.30
targetReferenceHeightM = 1.30
cameraElevationOffsetDeg = [-1.0, 1.0]
viewYawBucketsDeg = [-25, -15, -5, 0, 5, 15, 25]
topSurfaceViewBucketsDeg = [8, 12, 18]
distanceAnchorsM = [5, 10, 15]
```

### Doğrulama

- Yasak class/stage kombinasyonu üretilirse batch fail.
- `balon.targetInstanceId` yok/çoğul ise batch fail.
- Friendly-linked balloon runtime label'i `fireAuthorized=false`.
- Görünür piksel ve occlusion eşikleri manifestte.

### Çıkış kapısı

Tüm sınıflar ve görev ilişkileri görsel contact sheet + otomatik validator ile
onaylanmış.

### Blocker

`AR-04` gelmezse çıktı `committee_tilted_targets_provisional_v0` olarak kalır;
komite-doğruluğu iddia edilmez.

---

## FAZ 5 — Zoom, çözünürlük kaybı ve kamera kusurları

**Amaç:** 5–15 m hedeflerinde dijital zoom'un gerçek faydasını/zararını ölçmek.

### Yapılacaklar

- [ ] `perception/synthetic/tools/apply_camera_pipeline.py` oluştur.
- [ ] `sensor_roi` ve `application_crop` yollarını ayrı fonksiyonlar yap.
- [ ] `1.0×`, `1.5×`, `2.0×`; hard-case için `3.0×` üret.
- [ ] PoC/pilot renderı `2304×1296`, kamera-doğruluk alt kümesini daha sonra
  `4608×2592` üret.
- [ ] Runtime ara karesini `1280×720`, model girdisini `640×640` yap.
- [ ] Crop merkezi hatası, takip gecikmesi, kısmi target crop ekle.
- [ ] Blur, noise, JPEG/H.264 benzeri sıkıştırma ve sharpening profillerini zoom
  işleminden sonra uygula.
- [ ] Her base world ve zoom türevini aynı `worldId/groupId/split` içinde tut.
- [ ] Zoomsuz arama + track sonrası ROI zoom stratejisini replay için yapılandır.

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
- Runtime yöntemi `AR-07` ve gerçek kamera kıyası gelene kadar kilitlenmiyor.

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

### Zorunlu durak

`AR-05` ve `AR-07` olmadan bu fazın fiziksel kabul kısmı tamamlanmış sayılmaz.
Ajan script/testleri tamamladıktan sonra gerçek çekimleri bekler.

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

### Zorunlu durak

Scriptler hazır olduğunda `AR-06` kayıtları beklenir.

### Çıkış kapısı

- Aynı background session train ve val/test'e sızmıyor.
- Hedef kenarında halo/renk taşması otomatik ve görsel kontrolden geçiyor.
- Hedefsiz gerçek background'larda false positive metriği raporlanıyor.

---

## FAZ 8 — Mevcut dataset pipeline entegrasyonu

**Amaç:** Yeni renderer'ı mevcut güvenli veri sözleşmesine bağlamak.

### Yapılacaklar

- [ ] `perception/tools/dataset_pipeline.py` içine render-manifest ingest ekle.
- [ ] Mevcut `synthetic_seed_2d` üretimini smoke amaçlı koru.
- [ ] CAD config'i mevcut `perception/dataset/config.json` içine sessizce
  sıkıştırma; ayrı `perception/synthetic/config/render.toml` kullan.
- [ ] CAD kayıtlarında `worldId` tabanlı stable split uygula.
- [ ] Sentetik CAD için yalnız train/val üret; gerçek test'i sentetikle doldurma.
- [ ] `trainingAuthorized` hesabını şu koşullara bağla:
  - bağımsız gerçek val ve test session;
  - boş review queue;
  - geçerli camera/calibration hash;
  - açık model/release sözleşmesi.
- [ ] `dataset-manifest.json` içine renderer, BlenderProc, Blender, asset, camera,
  material, scene ve postprocess hash'lerini ekle.

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

### Pilot hacim

```text
6 presentation class
× 3 mesafe
× 7 yaw
× 3 üst-yüzey eğimi
× 4 ışık profili
× 2 seed
= 3.024 temel dünya
```

Zoom türevleri ayrı `variantId` olarak üretilir. İlk pilotta her dünya için tüm
zoomları üretmek yerine stratified `%40` alt kümeye `1.5×/2.0×`, `%10` hard-case
alt kümeye `3.0×` uygulanır.

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
- [ ] Detector → tracker → backend bridge replay testini çalıştır.
- [ ] Zoom state machine'i uygula:
  - `SEARCH_FULL_FRAME`;
  - `TRACK_CONFIRMING`;
  - `TRACK_ROI_1_5X`;
  - `TRACK_ROI_2X`;
  - `LOST_FAILBACK`.
- [ ] Zoom crop merkezinde bir kare gecikme ve ölçüm jitter'ı test et.
- [ ] Track stale/low-confidence olduğunda ateş yolunu fail-closed tut.

### Çıkış kapısı

- Track ID kararlılığı raporlanıyor.
- Zoom hedefi kadrajdan çıkardığında tam kadraja dönüş var.
- Dost hedef/bağlı balon hiçbir replay'de fire candidate olmuyor.
- Sentetik replay fiziksel HIL olarak adlandırılmıyor.

---

## FAZ 11 — Gerçek veri, sim-to-real ve materyal düzeltmesi

**Amaç:** Sentetik kısa yolları gerçek kamera verisiyle kırmak.

### Zorunlu durak

- `AR-08`: renk/malzeme örnekleri.
- `AR-09`: gerçek hedef oturumları.

### Yapılacaklar

- [ ] Gerçek session importunu mevcut idempotent SHA-256 hattından yap.
- [ ] Oturumları gün/ışık/mesafe olarak grupla; kare bazlı split yapma.
- [ ] Annotation'ları insan incelemesinden geçir.
- [ ] En az bir real-only validation ve bir real-only test session ayır.
- [ ] `B6` ve `B7` deneylerini çalıştır.
- [ ] Sentetik/gerçek karışım oranını real-only validation ile seç.
- [ ] 15 m, sağ/sol yaw, `8/12/18°` ve zoom bucket'larında hata analizi yap.
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
      committee_tilted_targets_provisional_v0.toml
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
npm run dataset:cad:validate -- --batch <batch-path>
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

## 8. İlk implementasyon turunun kesin kapsamı

İmplementasyona başlandığında ilk turda yalnız şu sıra uygulanacak:

1. FAZ 0 şema/dizin/dependency iskeleti.
2. FAZ 1 `inspect_3mf.py` ve küçük test fixture'ı.
3. Yerel `Modeller.3mf` inspection raporu.
4. Dört model için altı-yüz contact sheet.
5. Testler ve hash doğrulaması.
6. **DURAKLA — AR-01 ve AR-02** çıktısını kullanıcıdan bekle.

Bu ilk duraktan önce kullanıcıdan Bambu Studio veya Blender'da işlem istenmez.
Yalnız otomatik contact sheet yönü belirsiz bırakırsa Bambu Studio ekran görüntüsü
istenir. Manuel Blender mesh onarımı ancak dönüştürücü belirli bir geometriyi
otomatik ve kayıpsız işleyemezse ayrı, nesneye özgü blocker olarak açılır.

---

## 9. Nihai tamamlanma tanımı

### Araştırma pipeline'ı tamamlandı

- Dört CAD hedefi hash/ölçek/yön manifestinde.
- Aynı yükseklik, sağ/sol yaw, `8/12/18°` üst-yüzey görünümü ve 5/10/15 m
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
