# Taret Kalibrasyonu ve Aşama 1 Operatör Desteği

Bu dosya fiziksel entegrasyon öncesi hazırlanan yazılım yüzeyinin kullanım
sınırlarını açıklar. Repo içindeki varsayılan taret ve balistik dosyaları
`UNVERIFIED` durumundadır; fiziksel ölçüm yapılmadan hiçbir düzeltme uygulanmaz.

## 1. Taret komut-fiziksel hareket kalibrasyonu

Kalibrasyon her eksen için şu modeli çözer:

`ölçülen fiziksel açı = gain × yazılım komutu + offset`

Saha akışı:

1. Sistem güvenli yükle, imha hattı devre dışı ve fiziksel E-Stop erişilebilir
   durumda tutulur.
2. Pan ve tilt eksenlerinde negatif, sıfır ve pozitif yönleri kapsayan en az üçer
   komut verilir. Tek yönden ölçüm yerine her iki yönden daha çok nokta alınması
   backlash etkisini görünür kılar.
3. Komut edilen açı ve bağımsız açıölçerle ölçülen **gerçek fiziksel açı**
   `docs/turret_calibration_observations.example.json` biçiminde kaydedilir.
4. Önce etkinleştirmeden çözüm üretilir:

   ```bash
   .venv/bin/gokkalkan turret calibrate saha_taret.json \
     --output /tmp/turret-candidate.toml
   ```

5. Gain, offset ve RMSE incelenir; aynı noktalarla tekrar ölçüm yapılır. Kabul
   edilen sonuç bilinçli olarak etkinleştirilir:

   ```bash
   .venv/bin/gokkalkan turret calibrate saha_taret.json \
     --output config/calibration/turret.toml --activate
   ```

Runtime, dosya `ACTIVE` değilse identity davranışını korur. Safety Gate her zaman
operatörün istediği fiziksel hedef açı üzerinde çalışır; kalibrasyon dönüşümü
yalnız bu karar kabul edildikten sonra hardware adapter sınırında uygulanır.
Panel aktif kalibrasyon kimliğini gösterir.

## 2. Aşama 1 nişan görünümü

Aşama 1'de ana yüzey, sentetik hedef çizmek yerine perception bridge tarafından
sunulan gerçek MJPEG kamera akışını gösterir. Kaynak varsayılan olarak:

`http://127.0.0.1:8090/camera/live.mjpg`

Farklı adres `VITE_GOKKALKAN_CAMERA_STREAM_URL` veya
`?cameraStream=...` ile verilebilir. Perception bridge çalıştırıldığında aynı
portta `/camera/frame.jpg` ve `/health` de sunulur.

Nişangâhın mavi merkezi kamera/taret eksenidir. Operatör Space/deadman basılıyken
WASD, ok tuşları veya yön düğmeleriyle tareti doğrudan hareket ettirir. Adım
`0,25°`, `0,5°`, `1°` veya `2°` seçilebilir. Yazılım limiti ve Safety Gate
backend'de kalır.

## 3. 1D LiDAR ve balistik holdover

2D LiDAR ham tarama sayfası kaldırılmıştır. Seçili hedefe ait boresight menzili
Aşama 1 kamera görünümünün sol üstünde canlı sayı olarak gösterilir.

`config/calibration/airsoft_trajectory.toml`, fiziksel atış denemelerinden gelen
`range_m → elevation_deg` noktalarını taşır. En az iki nokta ve `status =
"ACTIVE"` olmadıkça sarı darbe noktası gösterilmez. Aktif tabloda ara menziller
doğrusal enterpolasyonla hesaplanır; tablo dışı menziller fail-closed kalır.

Mevcut hardware protokolünde “yönel, encoder ile yerleşmeyi doğrula, sonra ateş
et” atomik işlemi bulunmadığı için backend atış anında gizli bir taret hareketi
yapmaz. Bunun yerine sarı **tahmini darbe noktası** operatöre holdover verir.
Otomatik telafi ancak firmware ACK'si ve yerleşme toleransı doğrulanan ayrı bir
komut sözleşmesi eklendiğinde güvenli biçimde etkinleştirilmelidir.
