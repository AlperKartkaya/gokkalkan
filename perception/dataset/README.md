# Hedef Veri Seti Çalışma Alanı

Bu dizin kanonik seed → sentetik augmentation → gerçek baskı fotoğrafı pull →
YOLO veri seti → araştırma eğitimi zincirinin giriş sözleşmesidir.

`Modeller.3mf` tabanlı fiziksel render, gerçek boş kamera arka planıyla hibrit
veri ve gerçek hedeflere geçiş yol haritası için
[`docs/CAD_TABANLI_SENTETIK_VERI_VE_MODEL_GELISTIRME_ROADMAP.md`](../../docs/CAD_TABANLI_SENTETIK_VERI_VE_MODEL_GELISTIRME_ROADMAP.md)
belgesine bakın. Uygulanacak kesin sıra, zoom/geometri sözleşmesi ve kullanıcı
aksiyonu gerektiren duraklar
[`docs/CAD_TABANLI_SENTETIK_VERI_IMPLEMENTASYON_PLANI.md`](../../docs/CAD_TABANLI_SENTETIK_VERI_IMPLEMENTASYON_PLANI.md)
belgesinde tanımlıdır. CAD türevleri gerçek grup-ayrılmış test verisi olmadan
release kanıtı değildir.

## Hızlı başlangıç

```bash
# Bir kez: Pi dışı augmentation ortamı
uv venv .venv-perception --python 3.11
uv pip install --python .venv-perception/bin/python -r requirements/perception-dev.lock

# Boş capture klasöründe de başarıyla çalışır; 264 sentetik örnek üretir.
npm run dataset:prepare

# Model komutu/manifesti, eğitim yapmadan kontrol edilir.
.venv-perception/bin/python perception/tools/train_yolo.py \
  --allow-unverified --dry-run
```

Çıktı `perception/dataset/generated/yolo_current/` altındadır ve git tarafından
yok sayılır. Kanonik sonuçlar:

- `data.yaml`: YOLO sınıf ve split sözleşmesi;
- `dataset-manifest.json`: her görüntünün kökeni, split'i, hash'i, sentetik
  parametreleri ve gerçek çekim inceleme kuyruğu;
- `images/{train,val,test}` ve `labels/{train,val,test}`.

## Gerçek fotoğraflar geldiğinde

1. `captures/session.example.json` dosyasını çekim klasörüne `session.json`
   olarak kopyalayın ve alanlarını doldurun.
2. Fotoğrafları `captures/drop/README.md` içindeki sınıf klasörlerine koyun.
3. `npm run dataset:pull` veya doğrudan `npm run dataset:prepare` çalıştırın.
4. `captures/store/pull-manifest.json` içindeki `REVIEW_REQUIRED` kayıtlarını
   düzeltin.
5. `dataset-manifest.json` içindeki `reviewQueue`, split sayıları ve
   `trainingAuthorized` değerini inceleyin.

Pull işlemi kaynak fotoğrafları silmez. Aynı dosya tekrar geldiğinde SHA-256
nedeniyle çoğaltılmaz. Split görüntü bazında değil `sessionId` bazında yapılır;
aynı çekim oturumu train ve test'e sızamaz.

Takım arkadaşlarının CVAT ile insan onaylı etiketlediği export'lar
`captures/annotated/<sessionId>/` altına açılır. Ayrıntılı görev paylaşımı,
sınıf sırası ve export biçimi için
[`docs/FIZIKSEL_VERI_ETIKETLEME_MODEL_VE_OPERATOR_AKISI.md`](../../docs/FIZIKSEL_VERI_ETIKETLEME_MODEL_VE_OPERATOR_AKISI.md)
belgesine bakın. Pipeline `Ultralytics YOLO Detection 1.0` etiketlerini
doğrular ve aynı `sessionId` grubunu tek split'te tutar.

## Otomatik ön etiketleme

Klasör adı sunum sınıfını verir. OpenCV yayımlanan kırmızı/camgöbeği renginden
maket bbox'ını, maketin altındaki dairesel kırmızı bileşenden balon bbox'ını
çıkarır. Balon bulunamazsa maket örneği yine araştırma veri setine alınabilir
ancak `AUTO_REVIEW_REQUIRED` olur; release kabulünde insan incelemesi gerekir.
Renk bileşeni bulunamazsa fotoğraf sessizce kullanılmaz.

## Eğitim

Araştırma/smoke ortamı ayrı tutulur:

```bash
uv venv .venv-training --python 3.11
uv pip install --python .venv-training/bin/python -r requirements/training-dev.lock
npm run model:train:smoke
```

CAD araştırma veri setiyle tekrarlı kullanım için kısa akış:

```bash
./scripts/train_target_detector.sh
./scripts/predict_target_val.sh
```

Eğitim scripti varsayılan olarak `yolov8s.pt`, `30 epoch`, `640 px`, batch `8`
ve disk dataset cache kullanır. `DEVICE=auto`, CUDA varsa `0`, Apple Silicon
MPS varsa `mps`, aksi halde `cpu` seçer. Ultralytics DataLoader worker sayısı
CPU'ya göre en fazla `8` olarak açıkça geçirilir; eğitim zaten bu worker'larla
paralel veri hazırlar. Örnekler:

```bash
# Daha kısa YOLOv8n deneyi
MODEL=yolov8n.pt EPOCHS=10 NAME=cad-v8n-e10 ./scripts/train_target_detector.sh

# Bellek kısıtlı makine
BATCH=4 CACHE=none WORKERS=2 ./scripts/train_target_detector.sh

# Belirli ağırlıkla val görsellerini üret
WEIGHTS=perception/dataset/model_runs/cad-v8n-e10/weights/best.pt \
NAME=cad-v8n-e10-val ./scripts/predict_target_val.sh
```

Prediction çıktıları `perception/dataset/model_runs/predictions/` altında tutulur.
Ultralytics komutu project belirtilmeden çalıştırılmışsa oluşan kök `runs/`
dizini de Git tarafından yok sayılır.

Bu komut bir epoch smoke eğitimi yapar. Gerçek, grup ayrılmış val/test oturumları
yokken çıktı release modeli değildir. Ultralytics ve temel ağırlık lisansı
ürün/release kullanımından önce ayrıca değerlendirilmelidir. `.pt`, `.onnx` ve
`.hef` dosyaları repoya eklenmez.
