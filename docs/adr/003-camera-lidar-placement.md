# ADR-003 — Kamera ve TFA50-L Yerleşimi

- Durum: **Kabul edildi; sayısal extrinsic değerler imalat ölçümünü bekliyor**
- Tarih: **25.07.2026**
- İlgili işler: `ADR-003`, `PER-001`–`PER-006`, `LID-001`–`LID-005`

## Mekanik karar

TFA50-L, silahın pitch hareketine rijit bağlanmayacaktır. Öncelikli çözüm, yaw
tablasıyla birlikte dönen fakat pitch yapmayan iki dış yan plakayı bağlayan
merkezî köprü/profildir. Köprü yüksekliği kurulum sırasında elle ayarlanıp
mekanik olarak kilitlenir. Aynı kinematiği sağlayan merkezî düşey kızak/direk
mekanik alternatiftir.

Bu yerleşimde:

- LiDAR taret yaw açısını izler;
- Silah hedefin üstüne yükseldiğinde LiDAR pitch yapmaz ve hedef yüksekliğinde
  menzil ölçmeye devam edebilir;
- Köprü/kızak çalışma zamanı aktüatörü değildir;
- Manuel yükseklik değişikliği kalibrasyon hash’ini geçersiz kılar ve LIVE arm
  kapanır.

## Koordinat çerçeveleri

| Çerçeve | Tanım |
| --- | --- |
| `base` | Orijin yaw dönüş merkezinin taban izdüşümü; `+X` hedef yönü, `+Y` sol, `+Z` yukarı |
| `turret_yaw` | `base` üzerinde `+Z` etrafında dönen dış yan plakalar/köprü |
| `weapon_pitch` | Yatay namlu/atış ekseni mafsalı; elevasyon `-Y` ekseni etrafında pozitif yukarı |
| `camera_wide` | Yaw gövdesine bağlı geniş görüş kamerası; parkur ve track bearing üretir |
| `camera_aim` | Silah pitch gövdesine bağlı ince nişan kamerası; merkezleme hatası üretir |
| `lidar_tfa50` | `turret_yaw` köprüsünün merkezinde; pitch dönüşüne katılmaz |

İmalat sonrası ölçülecek her sensör için `translation_m=[x,y,z]` ve
`rotation_deg=[yaw,pitch,roll]` kaydedilir. `mount_height_m`,
`yaw_offset_deg`, `pitch_offset_deg`, hedef düşey bandı, tarih, operatör ve
kalibrasyon ID/hash session manifestine girer. Sayısal değerler ölçülmeden
uydurulmaz.

## Kamera/LiDAR iş bölümü

- Geniş kamera hedefi bulur ve `base/turret_yaw` bearing’i üretir.
- Taret yaw encoder’ı ile `lidar_tfa50.yaw_offset_deg` birleştirilir.
- TFA50-L ölçümü yalnız seçili track bearing’i dar hizalama toleransındayken o
  track’e atanır.
- Silah pitch açısı LiDAR ölçüm doğrultusuna eklenmez.
- Nişan kamerası silahın ince merkezlemesini yapar; LiDAR menzili değiştirmez.
- Stale track, geçersiz kalibrasyon, yaw uyumsuzluğu, checksum hatası veya
  no-detection imha iznini kapatır.

## Mekanik referanslar

- [`gokkalkan_izometrik_cizim.png`](../gokkalkan_izometrik_cizim.png): temel taret.
- [`gokkalkan_izometrik_cizim_uzerinde_lidar_konumu.png`](../gokkalkan_izometrik_cizim_uzerinde_lidar_konumu.png): öncelikli köprü/profil.
- [`gokkalkan_izometrik_cizim_lidar_konumu_2.png`](../gokkalkan_izometrik_cizim_lidar_konumu_2.png): merkezî kızak/direk alternatifi.

## Kabul ve fallback

TFA50-L; gerçek hedef yüzeyiyle 5/10/15 m, sağ/merkez/sol yaw, titreşim ve
silah pitch hareketi sırasında test edilir. Kabul kriterleri LID-005 kapsamında
ölçülür. Başarısızlık sırası:

1. optik hizalama, filtreleme ve kalibrasyon düzeltmesi;
2. ikinci tek nokta sensör ihtiyacının değerlendirilmesi;
3. ancak ölçümle gerekçelendirilirse 2D tarayıcı değerlendirmesi.

## Kaynaklar

- [`docs/imalat_oncesi_yazilim_todo.md`](../imalat_oncesi_yazilim_todo.md)
- [TFA50-L Datasheet](https://www.e-kom.com/Datasheet/Benewake/TFA50-L_Datasheet.pdf)
- [`reports/Gökkalkan Kritik Tasarım Raporu.pdf`](../../reports/Gökkalkan%20Kritik%20Tasarım%20Raporu.pdf), kamera/algı mimarisi.
