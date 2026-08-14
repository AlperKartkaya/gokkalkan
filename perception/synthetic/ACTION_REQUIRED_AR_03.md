# ACTION REQUIRED — AR-03 Üretim Ölçeği

FAZ 0–2 tamamlandı. Production sentetik dataset başlamadan dört hedefin imalatta
kullanılacak en uzun eksen ölçüsü kesinleştirilmelidir.

## En kısa çözüm

Aşağıdaki mevcut plan değerleri imalatta da kullanılacaksa yalnız “onaylıyorum”
demek yeterlidir:

```text
Drone: 300 mm
F16: 500 mm
Helikopter: 500 mm
Füze: 400 mm
```

Cevap şablonu:

```text
AR-03
Drone en uzun eksen: ... mm
F16 en uzun eksen: ... mm
Helikopter en uzun eksen: ... mm
Füze en uzun eksen: ... mm
Bu değerler üretim ölçüleridir: evet
```

## Değerlerden biri kesin değilse

1. Bambu Studio’da ilgili modeli seçin.
2. `Scale` panelinde X/Y/Z boyutlarını milimetre olarak okuyun.
3. İmalatta kullanılacak ölçek uygulanmış durumdaki en büyük değeri yazın.
4. Baskı zaten üretildiyse modelin uçtan uca en uzun mesafesini metre ile ölçün.
5. Yalnız değişen hedefi bildirin; dört model için ekran görüntüsü hazırlamanız gerekmez.

## Neden otomatik karar verilmiyor?

3MF geometrisinin mevcut boyutunu biliyoruz; fakat üretimde hangi nihai ölçeğin
kullanılacağı bir imalat kararıdır. Fiziksel boyut, hedefin 5/10/15 metrede kaç
piksel kaplayacağını doğrudan değiştirir. Yanlış ölçüyle geniş dataset üretmek,
açı belirsizliğinden farklı olarak sonradan yalnız filtreleme ile düzeltilemez.

Onay geldiğinde `cad_asset_manifest.json` içindeki ölçekler `VERIFIED` yapılacak,
normalize varlıklar yeniden üretilecek ve FAZ 3 tam açı/konum render matrisine
devam edilecektir.
