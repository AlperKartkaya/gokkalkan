# İnsan Onaylı Fiziksel Veri Girişi

CVAT'tan **Ultralytics YOLO Detection 1.0** biçiminde dışa aktarılan her çekim
oturumu ayrı klasöre açılır. Aynı çekim oturumu train/val/test arasında
bölünmez; split `sessionId` üzerinden pipeline tarafından yeniden atanır.

```text
annotated/
└── 2026-09-01-camera3-session01/
    ├── session.json
    ├── images/
    │   └── train/frame_000001.jpg
    └── labels/
        └── train/frame_000001.txt
```

`session.json` zorunludur:

```json
{
  "schemaVersion": 1,
  "sessionId": "2026-09-01-camera3-session01",
  "annotator": "takim-uyesi-1",
  "reviewer": "takim-uyesi-2",
  "camera": "Raspberry Pi Camera Module 3 Standard"
}
```

Etiket sırası `perception/dataset/config.json` ile bire bir aynı olmalıdır.
Eksik label, geçersiz sınıf veya 0..1 dışı bbox pipeline'ı fail-closed durdurur.
Negatif kare için eşleşen boş `.txt` dosyası bırakılır.

```bash
npm run dataset:prepare
```

Kaynak CVAT export'u ve ham fotoğraflar Git'e eklenmez; ekip depolamasında
hash/oturum kimliğiyle saklanır.
