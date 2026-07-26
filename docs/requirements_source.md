# Gereksinim Kaynağı ve Sürüm Politikası

## Kanonik kaynak

- Şartname sürümü: **v1.3**
- PDF: [`docs/sartname_v1_3.pdf`](sartname_v1_3.pdf)
- Aranabilir metin: [`docs/sartname_v1_3.txt`](sartname_v1_3.txt)
- PDF oluşturma tarihi (metadata): **17.07.2026**
- PDF SHA-256: `b57dba673f21adf9b2b4e502a41c4d7c52d39a3c3dc6e12cad624ab32990e91c`

PDF, yarışma gereksinimlerinde son otoritedir. Metin dosyası yalnız arama, satır
referansı ve otomatik kontrol içindir; tablo, şekil veya metin çıkarma hatasında
PDF’e bakılır. KTR ve Ön Tasarım Raporu geçmiş tasarım kayıtlarıdır; yeni şartname
ile çeliştiklerinde güncel karar ADR ile kaydedilir ve v1.3 uygulanır.

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
pdftotext -enc UTF-8 docs/sartname_v1_3.pdf docs/sartname_v1_3.txt
shasum -a 256 docs/sartname_v1_3.pdf docs/sartname_v1_3.txt
```

Metin yeniden üretildiğinde satır numaraları değişebileceği için
`docs/sartname_v1_3.txt:<satır>` referansları ve
[`docs/requirements_traceability.md`](requirements_traceability.md) birlikte
gözden geçirilir.

## Sürüm güncelleme prosedürü

1. Yeni PDF ayrı bir commit’te `docs/sartname_v<major>_<minor>.pdf` adıyla eklenir.
2. Aranabilir metin aynı taban adla üretilir.
3. PDF hash’i ve metadata bu dosyada güncellenir.
4. Eski/yeni sürüm farkları çıkarılır; tarihler, görevler, güvenlik ve video
   yükümlülükleri öncelikli incelenir.
5. README, AGENTS, `TARIHLER.md`, teknik yönelim, ADR’lar ve traceability matrisi
   aynı commit/PR içinde yeni sürüme geçirilir.

## v1.3 ile düzeltilen güncel tarihler

Önceki repo notlarında kalan `25.06.2026` KTR sonucu ve `10.08.2026` video
teslimi artık geçerli değildir. v1.3 takviminde:

- KTR sonucu: **13.07.2026**
- Sistem Kabiliyeti Videoları son teslimi: **17.08.2026 17:00**

Kaynak: `docs/sartname_v1_3.txt:228-268`, şartname §2.2.
