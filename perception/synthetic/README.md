# CAD Tabanlı Sentetik Veri Araçları

Bu dizin `Modeller.3mf` içindeki Drone, Helikopter, F16 ve Füze geometrilerini
inceleme, normalize etme, açı/X/Y/Z render planı oluşturma ve BlenderProc ile
kamera benzeri çıktılar üretme araçlarını barındırır.

Uygulama planı:
[`docs/CAD_TABANLI_SENTETIK_VERI_IMPLEMENTASYON_PLANI.md`](../../docs/CAD_TABANLI_SENTETIK_VERI_IMPLEMENTASYON_PLANI.md).

## Koordinat ve eğim sözleşmesi

- Bambu Studio `Front`: kamera kaynak `-Y` tarafında.
- Ekran sağı: `+X`; ekran yukarısı: `+Z`.
- `topSurfaceViewDeg=0`: tam Front.
- Pozitif `topSurfaceViewDeg`: burun aşağı, Front görünüşe Top katkısı.
- `viewYawDeg`: hedefin hafif sağdan/ soldan görünümü.
- Her kayıt bucket ve jitter sonrası gerçek sayısal açıyı ayrı taşır.

Komite ileride kesin açı aralığı verirse ham renderlar silinmez. Seçim manifesti:

```bash
npm run dataset:cad:filter -- \
  --input perception/synthetic/generated/render_plans/committee_tilt_sweep_v1.json \
  --output perception/synthetic/generated/render_plans/selection_10_18_deg.json \
  --min-tilt-deg 10 --max-tilt-deg 18
```

## Kurulum

```bash
uv venv .venv-synthetic --python 3.11
uv pip install --python .venv-synthetic/bin/python \
  -r requirements/synthetic-render.lock
npm run setup:synthetic:blender
```

Blender/BlenderProc yalnız geliştirme makinesinde kullanılır; Raspberry Pi/LIVE
ortamına kurulmaz.

## Çalışma sırası

```bash
npm run dataset:cad:inspect -- --input Modeller.3mf
npm run dataset:cad:convert
npm run dataset:cad:lod
npm run dataset:cad:validate
npm run dataset:cad:plan
npm run dataset:cad:render:smoke
```

Üretilen 3MF türevleri, 15.120 kayıtlık plan, renderlar ve Blender kurulumu Git’e
eklenmez. Kaynak/manifest hash’leri sonuçların yeniden üretilebilmesini sağlar.

## Mevcut teknik durum

- Dört mesh hash ve boyut kontrolünden geçti.
- Helikopterde 4 non-manifold kenar bulundu; kaynak değiştirilmedi. Blender smoke
  renderı için kullanılabilir, fiziksel baskı/solid kabulü olarak yorumlanmaz.
- LOD0/1/2 altı görünüş siluet IoU ve bbox kapısından geçti.
- F16 için RGB, depth, instance ve semantic segmentation smoke çıktısı üretildi.
- Ölçekler `AR-03` kesinleşene kadar `PROVISIONAL_SCALE` durumundadır.

## Güvenlik ve release sınırı

CAD renderı veya sentetik metrik fiziksel hedef kabulü değildir. Gerçek Camera
Module 3 kalibrasyonu ve grup-ayrılmış gerçek hedef oturumları olmadan model
release adayı sayılmaz.
