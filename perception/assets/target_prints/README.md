# Kanonik Hedef Maket Varlıkları

Bu klasör, `docs/sartname_v4.pdf` dosyasının fiziksel 14. sayfasındaki gömülü
`1531×258` hedef şeridinden deterministik olarak kırpılan dört özgün maket ile
güncel hedef tablosuna göre üretilen altı sunum varyantını tutar.

## Dizin sözleşmesi

- `source_spec_page14/`: PDF içindeki özgün şeritten ayrılan dört geometri.
- `black_background/`: siyah zeminde, yayımlanan kesin renklere tonlanan altı
  varyant.
- `manifest.json`: tip, dost/düşman, renk, yaklaşık fiziksel boyut, kaynak sayfa,
  piksel boyutu ve SHA-256 değerleri.

| Sunum sınıfı | Renk | Dosya |
| --- | --- | --- |
| Düşman Drone | `#F50A0A` | `dusman_drone_kirmizi_siyah_arka_plan.png` |
| Düşman Helikopter | `#F50A0A` | `dusman_helikopter_kirmizi_siyah_arka_plan.png` |
| Düşman F16 | `#F50A0A` | `dusman_f16_kirmizi_siyah_arka_plan.png` |
| Düşman Füze | `#F50A0A` | `dusman_fuze_kirmizi_siyah_arka_plan.png` |
| Dost Helikopter | `#00A3E0` | `dost_helikopter_camgobegi_siyah_arka_plan.png` |
| Dost F16 | `#00A3E0` | `dost_f16_camgobegi_siyah_arka_plan.png` |

## Üretim yöntemi ve sınırlar

Arka plan üretimi generatif değildir: PDF'in gömülü resmi çıkarılmış, dört
x-aralığı doygun piksel sınırına göre kırpılmış, beyaz/JPEG zemin siyaha
çevrilmiş ve özgün parlaklık korunarak hedef tonu yayımlanan HEX renge
sabitlenmiştir. Böylece geometri yeniden çizilmemiştir.

Bu dosyalar **kanonik seed ve baskı prototipidir**, eğitim veri seti değildir.
JPEG kaynak ayrıntısı sınırlıdır; fiziksel baskı, Camera Module 3 çekimleri,
grup bazlı split ve gerçek parkur negatifleri olmadan model kabul edilmez.
Üretilen büyük veri setleri, model ağırlıkları ve HEF dosyaları git'e eklenmez.

Bütün maketlerin altındaki kırmızı balon ayrı nesnedir. Balon rengi dost/düşman
etiketi değildir; özellikle camgöbeği dost maketin kırmızı balonu ateşe kapalı
kalmalıdır. Ayrıntılı sözleşme:

- [`docs/hedef_ve_parkur_operasyon_guncellemesi.md`](../../../docs/hedef_ve_parkur_operasyon_guncellemesi.md)
- [`docs/hedef_gorseli_yolo_veri_plani.md`](../../../docs/hedef_gorseli_yolo_veri_plani.md)
