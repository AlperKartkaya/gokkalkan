# Teslim Takvimi ve Sistem Kabiliyeti Videosu Kanıt Planı

Bu dosya şartname v1.3 §2.2 ve §2.4.4.1–2.4.4.2’yi yazılım test/telemetri
kimliklerine bağlar. Güncel kısa takvim `TARIHLER.md` dosyasındadır.

## Takvim

| Teslim/sonuç | Tarih |
| --- | --- |
| Yarışma son başvuru | 28.02.2026 |
| Ön Tasarım Raporu teslim | 23.03.2026 17:00 |
| Ön Tasarım Raporu sonucu | 29.04.2026 |
| KTR teslim | 02.06.2026 17:00 |
| KTR sonucu | **13.07.2026** |
| Sistem Kabiliyeti Videoları teslim | **17.08.2026 17:00** |
| Finalist açıklama | 24.08.2026 |
| Yarışma finalleri | Ağustos–Eylül 2026 |
| TEKNOFEST | 30.09.2026–04.10.2026 |

## Video biçim kapısı

- Tek video ve tek YouTube linki; liste dışı olabilir.
- En az 720p.
- Toplam süre 2–5 dakika.
- Yetenekler aşağıdaki sırayla gösterilir.
- Görüntü içinde yetenek numarası; açıklamada başlangıç zamanları bulunur.
- Link T3 KYS formuna eklenir ve teslimden önce farklı cihaz/ağdan açılır.

Kaynak: `docs/sartname_v1_3.txt:384-424`.

## Sıralı yetenek ve kanıt kimlikleri

| Sıra | Requirement/Test ID | Gösterim | Yazılım kanıtı | Fiziksel kabul |
| ---: | --- | --- | --- | --- |
| 1 | `VID-Y1-UI` | Kullanıcı arayüzü, joystick/klavye ve bütün fonksiyonların anlatımı | Frontend unit/Playwright, `StageRequest`, `ModeRequest`, `ManualAimCommand`, `FireIntent` olayları | Entegre panel, gerçek operatör girdileri |
| 2 | `VID-Y2-15M` | Sistem durağanken 15 m balon imhası | `FireIntent`, Safety snapshot, menzil/track ve video frame index’i | HIL sonrası kontrollü 15 m hedef testi |
| 3 | `VID-Y3-ESTOP-MOTION` | Yan/yükseliş hareketi sırasında Acil Durdur ile sistemin durması | `ESTOP_CHANGE`, `BLOCKED_ESTOP`, CAN/encoder zaman damgaları | Motor enerjisinin donanımsal kesilme süresi |
| 4 | `VID-Y4-ESTOP-FIRE` | Ateş sırasında Acil Durdur ile ateşin kesilmesi | `ESTOP_CHANGE`, fire command/result ve interlock olayı | Güvenli yapay yükle ateş hattı kesme testi |
| 5 | `VID-Y5-TRACK` | Yan ve yükseliş ekseninde hareket eden hedef takibi | Track ID, bearing, pan/tilt feedback, frame index | Gerçek hareketli hedefle yaw/elev takip |
| 6 | `VID-Y6-CLASSIFY` *(opsiyonel)* | 5/10/15 m hedef tipi tespit/sınıflandırma | Classification, TFA50-L range, UI hedef tipi | Gerçek hedef yüzeyi ve kayıtlı mesafe |

`frontend/src/missionConfig.ts` içindeki `Y1`–`Y6` sırası bu tabloyla aynı
kalmalıdır. Fiziksel kabul sütunu tamamlanmadan yalnız simülasyon videosu
“yetenek tamamlandı” kanıtı sayılamaz.

## Video paketleme kontrolü

- [ ] `VID-Y1`–`VID-Y5` sırası değişmedi.
- [ ] Opsiyonel `VID-Y6` gösteriliyorsa Y5’ten sonra.
- [ ] Her bölümün `run_id`, config hash ve calibration hash’i kayıtlı.
- [ ] Video saat aralıkları telemetri event ID’leriyle eşleşiyor.
- [ ] Gerçek fiziksel çıkış kullanılan bölümler ayrı güvenlik tutanağına bağlı.
- [ ] YouTube linki liste dışı/farklı cihaz testinden geçti.
