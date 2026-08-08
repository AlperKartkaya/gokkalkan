# Hedef Veri Seti Uygulama Rehberi

Uygulanan zincir:

```text
Şartname sayfa 14 kanonik maketleri
            │
            ├── deterministik augmentation ──> sentetik train + smoke-val
            │
Camera Module 3 baskı çekimleri
            │
            └── drop → hash'li pull → session split → güvenli ön etiketleme
                                             │
                                             ▼
                              YOLO data.yaml + dataset-manifest.json
                                             │
                              YOLOv8n araştırma/smoke eğitimi
                                             │
                                ONNX/HEF kapısı (henüz açık)
```

## Komutlar

| Amaç | Komut | Sonuç |
| --- | --- | --- |
| Fotoğrafları store'a çek | `npm run dataset:pull` | Boş klasörde `EMPTY`, fotoğraf varsa içerik-adresli kopya |
| Tüm veri setini hazırla | `npm run dataset:prepare` | 6 maket sınıfı + balon sınıfı YOLO veri seti |
| Eğitimi çalıştırmadan doğrula | `.venv-perception/bin/python perception/tools/train_yolo.py --allow-unverified --dry-run` | Dataset hash'li training intent |
| Bir epoch smoke model | `npm run model:train:smoke` | Git dışı `.pt` ve eğitim raporları |

## Sentetik kapsam

Varsayılan konfigürasyon her altı sunum sınıfı için 40 örnek ve 24 negatif
sahne üretir. Uygulanan değişimler:

- 1–15 m ile ilişkili ölçek eğilimi;
- ±30° yaw perspektifi ve ±15° maket eğimi;
- siyah perde kıvrımı, düşük seviye arka plan varyasyonu;
- parlaklık, Gauss gürültüsü, blur ve JPEG sıkıştırması;
- maketin altında değişken büyüklük/konumlu kırmızı balon;
- maket bbox, balon bbox ve `targetBalloonLinked` metadata'sı.

Rastgelelik `20260808` seed'iyle tekrarlanabilir. Mosaic, MixUp ve hue kaydırma
model eğitiminde kapalıdır; dost/düşman rengi bozulmaz.

## Sınıflar

```text
0 dusman_drone_kirmizi
1 dusman_helikopter_kirmizi
2 dusman_f16_kirmizi
3 dusman_fuze_kirmizi
4 dost_helikopter_camgobegi
5 dost_f16_camgobegi
6 balon
```

Post-process ilk altı sınıfı mevcut `targetType + friendFoe` sözleşmesine çevirir.
`balon` hiçbir zaman tek başına düşman değildir. Yalnız düşman maket track'i ile
ilişkilendirilmiş balon ateş adayı olabilir.

## Kabul sınırı

Sentetik `val`, aynı altı kaynak geometrinin farklı türevlerinden oluştuğu için
yalnız pipeline/model smoke testidir. Release modeli için en az:

- gerçek Camera Module 3 çekimleri;
- `capture_session_id + print_instance_id + background_id` grup ayrımı;
- bağımsız gerçek val ve test oturumları;
- insan tarafından kontrol edilmiş maket/balon etiketleri;
- sınıf bazlı recall, false-positive/dakika ve maket→balon yanlış ilişki metriği;
- Hailo HEF dönüşümü ve Pi 5 + AI HAT+ gecikme testi

gerekir. `trainingAuthorized=false` iken eğitim ancak açık
`--allow-unverified` araştırma bayrağıyla başlar.
