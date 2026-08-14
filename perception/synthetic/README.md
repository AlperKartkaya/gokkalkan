# CAD Tabanlı Sentetik Veri Araçları

Bu dizin `Modeller.3mf` içindeki Drone, Helikopter, F16 ve Füze geometrilerini
izlenebilir biçimde inceleme, normalize etme ve daha sonraki fazlarda BlenderProc
ile render etme sözleşmesini barındırır.

Uygulama sırası ve fiziksel duraklar:
[`docs/CAD_TABANLI_SENTETIK_VERI_IMPLEMENTASYON_PLANI.md`](../../docs/CAD_TABANLI_SENTETIK_VERI_IMPLEMENTASYON_PLANI.md).

## Kurulum

```bash
uv venv .venv-synthetic --python 3.11
uv pip install --python .venv-synthetic/bin/python \
  -r requirements/synthetic-render.lock
```

Bu ortam geliştirme makinesine özeldir. Raspberry Pi/LIVE ortamına `lib3mf`,
BlenderProc veya Blender kurulmaz.

## FAZ 1: 3MF inceleme

```bash
npm run dataset:cad:inspect -- \
  --input Modeller.3mf \
  --source-config perception/synthetic/config/cad_source.json \
  --asset-manifest perception/synthetic/config/cad_asset_manifest.json \
  --report perception/synthetic/generated/inspection/modeller.report.json \
  --contact-sheet-dir perception/synthetic/generated/contact_sheets
```

Üretilen rapor/contact sheet dosyaları Git'e eklenmez; aynı kaynak hash'i ve araç
sürümüyle tekrar üretilebilir. Contact sheet'ler yalnız kaynak `±X/±Y/±Z`
yönlerini gösterir. `noseAxis` ve `upAxis`, AR-02 kullanıcı onayına kadar
`PENDING` kalır.

FAZ 1 yerel incelemesi dört mesh ve beklenen SHA-256 değerini doğruladı. Drone,
F16 ve Füze lib3mf geçerlilik/manifold kontrolünü geçti; Helikopter geçmedi ve
FAZ 2'de otomatik tanı/onarıma alınacak. Mevcut zorunlu kullanıcı adımları ve
cevap şablonu için [`ACTION_REQUIRED_AR_01_AR_02.md`](ACTION_REQUIRED_AR_01_AR_02.md)
belgesine bakın.

## Güvenlik ve release sınırı

CAD görüntüsü, sentetik model metriği veya contact sheet fiziksel hedef kabulü
değildir. Gerçek Camera Module 3 calibration ve grup-ayrılmış gerçek hedef
oturumları gelmeden hiçbir model release adayı sayılmaz.
