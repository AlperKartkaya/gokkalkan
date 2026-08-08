# Hedef Veri Seti Çalışma Alanı

Bu dizin kanonik seed → sentetik augmentation → gerçek baskı fotoğrafı pull →
YOLO veri seti → araştırma eğitimi zincirinin giriş sözleşmesidir.

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

Bu komut bir epoch smoke eğitimi yapar. Gerçek, grup ayrılmış val/test oturumları
yokken çıktı release modeli değildir. Ultralytics ve temel ağırlık lisansı
ürün/release kullanımından önce ayrıca değerlendirilmelidir. `.pt`, `.onnx` ve
`.hef` dosyaları repoya eklenmez.
