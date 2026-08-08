# Algı Modeli Sözleşmesi

`target_detector_contract.json`, eğitim framework'ünden bağımsız sınıf ve güvenlik
sözleşmesidir. `.pt`, `.onnx` ve `.hef` dosyaları burada commit edilmez.

Araştırma modeli yedi nesne sınıfı üretir. İlk altı sınıf doğrudan
`targetType + friendFoe` değerine dönüştürülür; yedinci sınıf kırmızı balondur.
Balon çıktısı tek başına ateş adayı değildir. Aynı track'teki maketin düşman
olduğu ve Safety Gate'in diğer tüm koşulları geçtiği doğrulanmalıdır.

Modelin uygulanabilir eğitim komutu `perception/tools/train_yolo.py`, veri
hazırlama hattı `perception/tools/dataset_pipeline.py` içindedir. Kabul edilen
model daha sonra hash'i ve ölçümleriyle ayrı release manifestine yazılacaktır.
