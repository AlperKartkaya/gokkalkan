# CAD Tabanlı Sentetik Veri Araçları

Bu dizin `Modeller.3mf` içindeki Drone, Helikopter, F16 ve Füze geometrilerini
inceleme, normalize etme, rota-türetilmiş poz planı oluşturma ve BlenderProc ile
kamera benzeri çıktılar üretme araçlarını barındırır.

Uygulama planı:
[`docs/CAD_TABANLI_SENTETIK_VERI_IMPLEMENTASYON_PLANI.md`](../../docs/CAD_TABANLI_SENTETIK_VERI_IMPLEMENTASYON_PLANI.md).
Kamera/ROI kararı:
[`docs/KAMERA_ROI_ZOOM_VE_SENTETIK_VERI_KARARLARI.md`](../../docs/KAMERA_ROI_ZOOM_VE_SENTETIK_VERI_KARARLARI.md).

## Geometri sözleşmesi

- 3MF ölçüleri kesindir; dört varlığın render ölçeği `1.0`'dır.
- Normalize edilmiş render uzayında hedef burnu kameraya doğru `-Y`, üst yüzey `+Z`'dir.
- F16 kaynak mesh'i diğer yatay hedeflerden ters yöndedir (`burun=+Y`). Dönüştürme
  sırasında `Z` etrafında `180°` çevrilerek `burun=-Y` yapılır; bu düzeltme render
  planında ek yaw üretmez.
- Boylamasına uzaklıklar `3–17 m` arasında her tam metredir.
- Rota 1/3 enlemesine ofsetleri `±2.75`, `±2.87`, `±3.00 m`; Rota 2 `0 m`'dir.
- `viewYawDeg = degrees(atan2(signedLateralDistanceM, longitudinalDistanceM))`.
- Yaw hedefe ayrıca rotasyon olarak uygulanmaz; kamera-hedef geometrisinden doğar.
- Burun eğimi `4/6/8/10/12/14/16/18/20/24/28°`, jitter `±0.5°`'dir. Pozitif değer,
  normalize edilmiş `-Y` burun eksenini `-Z` yönüne indirir; burnu yukarı kaldırmaz.
- Nominal, hafif soluk, hafif karanlık ve hafif aydınlık görünüm profilleri pozlara
  `%40/%20/%20/%20` oranıyla deterministik atanır; veri hacmini dört katına çıkarmaz.
- Arama yolu `2304×1296` main görüntüden `%25` örtüşmeli sekiz `768×768` SAHI
  tile'ıdır. Takip yolu aynı main görüntüden `768×768`, kayıpta `960×960` veya
  `1152×1152` kare ROI'dir. Kare görünümler padding olmadan `640×640` küçültülür.
- Tam-FoV `1280×720 → 640×360` letterbox yalnız legacy ablation'dır.
- `scaler_crop` ve düşük çözünürlüklü `application_crop` varsayılan runtime değil,
  yalnız araştırma/ablation yollarıdır.

Kesin eğim bilgisi sonradan gelirse ham renderlar silinmeden seçim manifesti üretilir:

```bash
npm run dataset:cad:filter -- \
  --input perception/synthetic/generated/render_plans/committee_tilt_sweep_v1.json \
  --output perception/synthetic/generated/render_plans/selection_10_18_deg.json \
  --min-tilt-deg 10 --max-tilt-deg 18
```

## Kurulum ve çalışma sırası

Yeni bir geliştirme makinesinde yalnız ML/sentetik veri ortamlarını hazırlamak için:

```bash
./scripts/setup_ml_pipeline.sh
```

Günlük iterasyonda gereken kısa komutlar:

```bash
./scripts/render_cad_dataset.sh
./scripts/ingest_cad_dataset.sh
./scripts/train_target_detector.sh
./scripts/predict_target_val.sh
```

Scriptler parametresiz çalışır ve ek CLI argümanlarını aynen alta iletir. En sık
değiştirilen değerler ortam değişkeniyle verilebilir:

```bash
# Dört bağımsız Blender süreci ve yalnız ilk 40 kayıt
WORKERS=4 ./scripts/render_cad_dataset.sh --limit 40

# CPU render veya belirli NVIDIA backend'i
RENDER_DEVICE=cpu ./scripts/render_cad_dataset.sh --limit 4
RENDER_DEVICE=optix WORKERS=2 ./scripts/render_cad_dataset.sh

# Farklı plan/batch dizini
PLAN=perception/synthetic/generated/render_plans/selection_10_18_deg.json \
OUTPUT=perception/synthetic/generated/render_batches/selection_10_18_deg \
./scripts/render_cad_dataset.sh
```

Render varsayılanında worker sayısı güvenli otomatik seçimle en fazla `2` olur.
Her worker farklı `recordId` dizinine yazar; mevcut `record.json + tek HDF5`
kaydı resume sırasında atlanır. BlenderProc/Cycles uygun cihaz varsa GPU'yu,
render koordinasyonu için ayrılmış CPU thread'lerini kullanır. Çoklu GPU süreci
bellek baskısı yaparsa `WORKERS=1`; yalnız CPU istenirse `RENDER_DEVICE=cpu`
kullanılır. Tekil Blender/GPU süreci çökerse kayıt varsayılan olarak iki kez
yeniden denenir; yarım batch dizini denemeden önce temizlenir. Bu sayı
`RETRIES=3` gibi değiştirilebilir.

```bash
uv venv .venv-synthetic --python 3.11
uv pip install --python .venv-synthetic/bin/python \
  -r requirements/synthetic-render.lock
npm run setup:synthetic:blender

npm run dataset:cad:inspect -- --input Modeller.3mf
npm run dataset:cad:convert
npm run dataset:cad:lod
npm run dataset:cad:validate
npm run dataset:cad:plan
npm run dataset:cad:plan:pilot
npm run dataset:cad:render:smoke
npm run dataset:cad:validate:batch -- \
  --batch perception/synthetic/generated/render_batches/smoke
npm run dataset:cad:render:pilot -- --limit 1
npm run dataset:cad:ingest
```

CAD ingest bağımsız HDF5 kayıtlarını spawn edilmiş süreçlerde işler; otomatik
worker sayısı CPU'ya göre en fazla `8`'dir. Seri ve hata ayıklamaya uygun eşdeğer
komut `WORKERS=1 ./scripts/ingest_cad_dataset.sh` biçimindedir.

Bir render ve tek kanallı hedef maskesinden runtime ile aynı search tile'larını
üretmek için:

```bash
npm run dataset:cad:views -- \
  --image <render.png> \
  --mask <class-mask.png> \
  --target-value <class-id> \
  --record <record.json> \
  --output-dir <output/search> \
  --family search-sahi
```

Takip/recovery görünümü için `--family track-square --roi-size 768`; kayıp
senaryolarında `960` veya `1152` kullanılır. Blur/noise tam kareye yalnız bir kez
uygulanır, ardından tile/ROI türetilir.

Blender/BlenderProc yalnız geliştirme makinesinde kullanılır; Raspberry Pi/LIVE
ortamına kurulmaz. Üretilen meshler, `6.930` kayıtlık plan ve renderlar Git'e
eklenmez; kaynak/manifest hash'leri yeniden üretilebilirliği sağlar.

## Mevcut teknik durum ve sınır

- Dört mesh hash, kesin 3MF boyutu ve yön kontrolünden geçti.
- Helikopterde 4 non-manifold kenar kaynak özelliği olarak loglandı; sessizce onarılmadı.
- LOD0/1/2 altı görünüş siluet IoU ve bbox kapısından geçti.
- F16 RGB, depth, instance ve semantic segmentation smoke çıktısı üretilebiliyor.
- CAD/sentetik fazında fiziksel kamera blocker'ı yoktur.
- AR-09 gerçek hedef oturumları olmadan model release adayı değildir.
- AR-10 Hailo/Pi kabulü olmadan HEF ve canlı latency doğrulanmış sayılmaz.
