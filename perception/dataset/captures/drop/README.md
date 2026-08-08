# Gerçek Baskı Fotoğrafı Bırakma Alanı

Her çekim oturumu ayrı klasördür:

```text
drop/
└── 2026-08-20-camera3-session01/
    ├── session.json
    ├── dusman_drone_kirmizi/
    │   ├── frame_0001.jpg
    │   └── frame_0002.jpg
    ├── dusman_helikopter_kirmizi/
    ├── dusman_f16_kirmizi/
    ├── dusman_fuze_kirmizi/
    ├── dost_helikopter_camgobegi/
    └── dost_f16_camgobegi/
```

`session.json` için `../session.example.json` kopyalanır. Fotoğrafın üst klasörü
sunum sınıfını belirler. Pipeline kaynakları silmez; SHA-256 ile içerik-adresli
`store/` alanına kopyalar. Etiketi güvenle çıkarılamayan fotoğraf veri setine
sessizce alınmaz ve import manifestinde `REVIEW_REQUIRED` olur.
