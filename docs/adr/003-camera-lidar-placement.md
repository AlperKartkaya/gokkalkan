# ADR-003 — Tek Kamera ve TFA50-L Yerleşimi

- Durum: **Güncellendi ve kabul edildi; sayısal extrinsic değerler imalat ölçümünü bekliyor**
- Tarih: **25.07.2026**
- İlgili işler: `ADR-003`, `PER-001`–`PER-006`, `LID-001`–`LID-005`

## Mekanik karar

TFA50-L ve tek Raspberry Pi Camera Module 3 Standard, silahın pitch hareketine
rijit bağlanmayacaktır. İki sensör yaw tablasıyla birlikte dönen fakat pitch
yapmayan, yüksekliği elle ayarlanıp kilitlenen köprü/profile bağlanır. LiDAR
optik merkezi sistemin en alt fiziksel noktasından 700 mm yukarıdadır.

Bu yerleşimde:

- LiDAR taret yaw açısını izler;
- Tek kamera aynı yaw açısını izler;
- Silah hedefin üstüne yükseldiğinde LiDAR pitch yapmaz ve hedef yüksekliğinde
  menzil ölçmeye devam edebilir;
- Kamera görüntüsü silah pitch hareketinden etkilenmez;
- Köprü/kızak çalışma zamanı aktüatörü değildir;
- Manuel yükseklik değişikliği kalibrasyon hash’ini geçersiz kılar ve LIVE arm
  kapanır.

## Koordinat çerçeveleri

| Çerçeve | Tanım |
| --- | --- |
| `base` | Orijin yaw dönüş merkezinin taban izdüşümü; `+X` hedef yönü, `+Y` sol, `+Z` yukarı |
| `turret_yaw` | `base` üzerinde `+Z` etrafında dönen dış yan plakalar/köprü |
| `weapon_pitch` | Yatay namlu/atış ekseni mafsalı; elevasyon `-Y` ekseni etrafında pozitif yukarı |
| `sensor_bridge` | Yaw gövdesine bağlı, elle ayarlanan ve kilitlenen, pitch yapmayan profil |
| `camera_main` | Köprüdeki tek Camera Module 3 Standard; target/bearing üretir, pitch yapmaz |
| `lidar_tfa50` | Köprüde, 0,700 m optik merkez yüksekliğinde; pitch dönüşüne katılmaz |

İmalat sonrası ölçülecek her sensör için `translation_m=[x,y,z]` ve
`rotation_deg=[yaw,pitch,roll]` kaydedilir. `mount_height_m`,
`yaw_offset_deg`, `pitch_offset_deg`, hedef düşey bandı, tarih, operatör ve
kalibrasyon ID/hash session manifestine girer. Sayısal değerler ölçülmeden
uydurulmaz.

## Tek kamera/LiDAR iş bölümü

- `camera_main` yaw taramasıyla hedefleri bulur; tip ve gerektiğinde
  dost/düşman girdisi ile `base/turret_yaw` bearing'i üretir.
- Taret yaw encoder’ı ile `lidar_tfa50.yaw_offset_deg` birleştirilir.
- TFA50-L ölçümü yalnız seçili track bearing’i dar hizalama toleransındayken o
  track’e atanır.
- Silah pitch açısı LiDAR ölçüm doğrultusuna eklenmez.
- Ayrı nişan kamerası yoktur. Kamera merkezinin `weapon_bore` ile aynı olduğu
  varsayılmaz; extrinsic ve menzile bağlı balistik elevasyon uygulanır.
- Stale track, geçersiz kalibrasyon, yaw uyumsuzluğu, checksum hatası veya
  no-detection imha iznini kapatır.

## Mekanik referanslar

- [`gokkalkan_izometrik_cizim.png`](../images/gokkalkan_izometrik_cizim.png): temel taret.
- [`version_final_kamera_ve_lidarın_konumu.jpeg`](../images/version_final_kamera_ve_lidar%C4%B1n_konumu.jpeg): nihai sensör köprüsü, kamera/LiDAR konumu ve 700 mm referansı.
- [`taret_mekanik_ve_sensor_yerlesimi.md`](../taret_mekanik_ve_sensor_yerlesimi.md): kanonik fiziksel/yazılım referansı.

## Kabul ve fallback

TFA50-L; gerçek hedef yüzeyiyle 5/10/15 m, sağ/merkez/sol yaw, titreşim ve
silah pitch hareketi sırasında test edilir. Kabul kriterleri LID-005 kapsamında
ölçülür. Başarısızlık sırası:

1. optik hizalama, filtreleme ve kalibrasyon düzeltmesi;
2. ikinci tek nokta sensör ihtiyacının değerlendirilmesi;
3. ancak ölçümle gerekçelendirilirse 2D tarayıcı değerlendirmesi.

## Kaynaklar

- [`docs/imalat_oncesi_yazilim_todo.md`](../imalat_oncesi_yazilim_todo.md)
- [`docs/taret_mekanik_ve_sensor_yerlesimi.md`](../taret_mekanik_ve_sensor_yerlesimi.md)
- [TFA50-L Datasheet](https://www.e-kom.com/Datasheet/Benewake/TFA50-L_Datasheet.pdf)
- [`reports/Gökkalkan Kritik Tasarım Raporu.pdf`](../../reports/Gökkalkan%20Kritik%20Tasarım%20Raporu.pdf), kamera/algı mimarisi.
