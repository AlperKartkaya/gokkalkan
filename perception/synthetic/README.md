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
- Bambu Studio `Front`: kamera kaynak `-Y`; ekran sağı `+X`, ekran yukarısı `+Z`.
- Boylamasına uzaklıklar `3–17 m` arasında her tam metredir.
- Rota 1/3 enlemesine ofsetleri `±2.75`, `±2.87`, `±3.00 m`; Rota 2 `0 m`'dir.
- `viewYawDeg = degrees(atan2(signedLateralDistanceM, longitudinalDistanceM))`.
- Yaw hedefe ayrıca rotasyon olarak uygulanmaz; kamera-hedef geometrisinden doğar.
- Burun eğimi `4/6/8/10/12/14/16/18/20/24/28°`, jitter `±0.5°`'dir.
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
