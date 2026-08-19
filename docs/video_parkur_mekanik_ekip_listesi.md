# Görev Kabiliyeti Videosu — Mekanik Ekip Parkur Listesi

Bu liste yazılım kalibrasyon değerlerini veya elektrik/sigorta tasarımını
tanımlamaz. Amaç, gerçek kamera/algı ve hareket kanıtı alınabilecek tekrarlanır
bir video parkuru hazırlamaktır.

## Ortak hazırlık

- Zeminde ölçülmüş `5 m`, `10 m` ve `15 m` çizgilerini işaretleyin.
- Kamera için sabit tripod noktası belirleyin; kadrajda hem taret hareketi hem
  ilgili hedef görünmelidir.
- Hedefleri parlama yapmayan mat yüzeyle hazırlayın; arka planla şekil ve renk
  ayrımı korunmalıdır.
- Her çekim için yedek balon ve hedef seti bulundurun.
- Pan/tilt hareket alanına kablo, insan veya gevşek ekipman girmemelidir.

## Y2 — 15 m durağan hedef

- Hedef ve balon, ölçülmüş 15 m çizgisine sabitlenir.
- Hedef, kamera ve sistemin atış yönünde aynı görüş hattında tutulur.
- Hedef arkasında güvenli fiziksel durdurucu ve çekim için görünür mesafe işareti bulunur.

## Y3/Y4 — Acil Durdur çekimi

- Acil Durdur butonu, taret ve operatörün eli aynı veya kesintisiz ikinci
  kamera kadrajında görülmelidir.
- Y3 için atış hattı kullanılmaz; taret iki eksende görünür kontrollü hareket yapar.
- Y4 için atış davranışı ve fiziksel E-Stop olayı kesintisiz kayda alınır.

## Y5 — Hareketli hedef

- Hedef, yatay ve yükseliş yönünde hareket sağlayan tekrarlanabilir ray, ip,
  taşıyıcı veya mekanik kol üzerinde ilerler.
- Rota kamera görüş alanını terk etmez; hız ilk provada düşük/orta tutulur.
- Kullanılan silüet şartnamedeki örnek hedef tiplerine benzer olmalıdır.

## Y6 — 5/10/15 m sınıflandırma

- F16, Mini/Micro İHA, Füze ve Helikopter hedefleri için baskı/maketler
  hazırlanır.
- Her çekimde hedefin gerçek konumu zemin işaretiyle birlikte görünür olmalıdır.
- Hedefler tek tek ve sabit konumda gösterilir; model çıktısı UI'de canlı
  perception kaynağından gelmelidir.

## Y7 — Opsiyonel dost/düşman

- Yaklaşık 10 m'de bir kırmızı düşman, iki mavi/camgöbeği dost hedef yerleştirin.
- Hedefler görüntüde birbirinden ayrık olmalı; dostlar atış hattına girmeyecek
  fiziksel konumda tutulmalıdır.
- Düşman hedef sonrası 10 saniye gözlem ve E-Stop sonrası 10 saniye duruş için
  kronometre görünürlüğü planlanmalıdır.
