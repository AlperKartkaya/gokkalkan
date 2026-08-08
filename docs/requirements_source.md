# Gereksinim Kaynağı ve Sürüm Politikası

## Kanonik kaynak

- Kanonik repo dosya sürümü: **v4**
- Belgenin iç sürümü: **V1.4**, tarih **23.06.2026**
- PDF: [`docs/sartname_v4.pdf`](sartname_v4.pdf)
- Aranabilir metin: [`docs/sartname_v4.txt`](sartname_v4.txt)
- PDF oluşturma tarihi (metadata): **28.07.2026**
- PDF SHA-256: `b1e6069d69a09dfaef5abb40e73f1dcc5854b04a44d22b6f57b5582e4fc63ace`
- TXT SHA-256: `2a1a3b7d67b41ab60d429e191070da291371f35eaf00192608b0c0d055536e0a`

PDF, yarışma gereksinimlerinde son otoritedir. Metin dosyası yalnız arama, satır
referansı ve otomatik kontrol içindir; tablo, şekil veya metin çıkarma hatasında
PDF’e bakılır. KTR ve Ön Tasarım Raporu geçmiş tasarım kayıtlarıdır; yeni şartname
ile çeliştiklerinde güncel karar ADR ile kaydedilir ve v1.4 uygulanır.

## Sonraki tarihli operasyon bilgilendirmesi

Ekibin 8 Ağustos 2026'da sağladığı hedef/parkur mesajı ve görselleri
[`hedef_ve_parkur_operasyon_guncellemesi.md`](hedef_ve_parkur_operasyon_guncellemesi.md)
dosyasında tutulur. Bu kaynak; dost rengini `#00A3E0` camgöbeği olarak
kesinleştirir, balon çapını yaklaşık 12–16 cm, parkuru 10×16 m, hedef yüksekliğini
yaklaşık 1,30 m ve sistem masasını 0,60 m olarak bildirir. Duyuru metni yeni bir
şartname PDF'i değildir; yeni resmî doküman geldiğinde bu kayıt yeniden doğrulanır.

## Kanonik geometrik ek

- Teknik çizim:
  [`docs/Celikkubbe_Hava_Savunma_Sistemleri_Parkur_Cizim.pdf`](Celikkubbe_Hava_Savunma_Sistemleri_Parkur_Cizim.pdf)
- Çizim numarası / revizyon: **PLG26-A-001-002-00 / Rev 1**
- PDF SHA-256:
  `466ef675555aace404e1e52902a12c01a92bae616418cc3f34f1330e43f2755e`
- İnsan-okunur çıkarım:
  [`docs/parkur_geometri_referansi.md`](parkur_geometri_referansi.md)
- Makine-okunur çıkarım:
  [`config/course/plg26_a_001_002_r1.json`](../config/course/plg26_a_001_002_r1.json)

Teknik çizim; parkur ve poligon geometrisi, yazılı ölçüler ve antetteki
toleranslar için kanonik kaynaktır. Şartname ise A→B görev akışı, üç kol,
aşama ve güvenlik kurallarında son otoritedir. Yazılı ölçüler raster
ölçeklemesinden üstündür. Organizasyon yeni bir revizyon yayımlamadıkça sensör
gözlemi parkur geometrisini yeniden kalibre etmez. Çalışma zamanı kestirimi
yalnız rotaların poligon içinde kalan eğri parçalarını kullanır; poligon dışı
geri dönüşler konum/atış tahminine alınmaz ve her yeniden girişte yay
koordinatı sıfırlanır.

## Metin çıktısını yeniden üretme

Poppler kurulu bir ortamda:

```bash
pdftotext -enc UTF-8 docs/sartname_v4.pdf docs/sartname_v4.txt
shasum -a 256 docs/sartname_v4.pdf docs/sartname_v4.txt
```

Metin yeniden üretildiğinde satır numaraları değişebileceği için
`docs/sartname_v4.txt:<satır>` referansları ve
[`docs/requirements_traceability.md`](requirements_traceability.md) birlikte
gözden geçirilir.

## Sürüm güncelleme prosedürü

1. Yeni PDF, organizasyon tarafından yayımlanan repo dosya adı korunarak `docs/` altına eklenir.
2. Aranabilir metin aynı taban adla üretilir.
3. PDF hash’i ve metadata bu dosyada güncellenir.
4. Eski/yeni sürüm farkları çıkarılır; tarihler, görevler, güvenlik ve video
   yükümlülükleri öncelikli incelenir.
5. README, AGENTS, `TARIHLER.md`, teknik yönelim, ADR’lar ve traceability matrisi
   aynı commit/PR içinde yeni sürüme geçirilir.

## v4 / belge içi V1.4 değişiklik özeti

V1.3’e göre uygulamayı etkileyen değişiklikler:

- Aşama 1 geçiş eşiği **30 puandan 20 puana** düşürülmüştür.
- Aşama 2’de üç isabetsiz tur sonrası aşamanın sıfırlanması kuralı kaldırılmıştır; hedef
  vurulamayan her tur için `-5` puan uygulanır.
- Aşama 3 başarısızlık koşulu üç yerine **dört ardışık** düşman hedef kaçırmadır.
- Aşama 1 ve Aşama 2 maketleri kırmızı; Aşama 3 düşmanları kırmızı, dostları mavidir.
  Bütün hedef maketlerinin altındaki imha balonu kırmızıdır.
- Video Yetenek 6 artık zorunludur; kırmızı düşman/mavi dost gösterimi Yetenek 7 olarak
  opsiyonel eklenmiştir.
- OTR teslim/sonuç, KTR sonuç, finalist açıklama ve final tarihleri güncellenmiştir.

Kaynak: `docs/sartname_v4.txt:174-216,318-342,462-509,701-718,759-907`.
