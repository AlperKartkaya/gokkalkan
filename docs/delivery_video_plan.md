# Teslim Takvimi ve Sistem Kabiliyeti Videosu Kanıt Planı

Bu dosya şartname v1.4 §2.2 ve §2.4.4.1–2.4.4.2'yi yazılım test/telemetri
kimliklerine bağlar. Güncel kısa takvim `TARIHLER.md` dosyasındadır.

> **⚠️ ACİL — Video teslim tarihi: 20.08.2026 17:00 — 5 gün kaldı)**
> Zorunlu Y1–Y6 sırasının fiziksel kabul sütunları için gerçek donanım kanıtı gerekmektedir.
> Yalnız simülasyon + yazılım kanıtı yeterli değildir — şartname §2.4.4.1 gereği.
> Hazırlanan yazılım kanıtları ve simülasyon KTR kanıtı olarak saklanır.

## Takvim

| Teslim/sonuç | Tarih | Durum |
| --- | --- | --- |
| Yarışma son başvuru | 28.02.2026 | ✅ |
| Ön Tasarım Raporu teslim | 17.03.2026 17:00 | ✅ |
| Ön Tasarım Raporu sonucu | 13.04.2026 | ✅ |
| KTR teslim | 02.06.2026 17:00 | ✅ |
| KTR sonucu | **25.06.2026** | ✅ |
| **Sistem Kabiliyeti Videoları teslim** | **20.08.2026 17:00 — 5 gün kaldı |
| Finalist açıklama | 31.08.2026 | — |
| Yarışma finalleri / TEKNOFEST | 30.09.2026–04.10.2026 | — |

## Video biçim kapısı

- Tek video ve tek YouTube linki; liste dışı olabilir.
- En az 720p.
- Toplam süre 2–5 dakika.
- Yetenekler aşağıdaki sırayla gösterilir.
- Görüntü içinde yetenek numarası; açıklamada başlangıç zamanları bulunur.
- Link T3 KYS formuna eklenir ve teslimden önce farklı cihaz/ağdan açılır.

Kaynak: `docs/sartname_v4.txt:462-509`.

## Sıralı yetenek ve kanıt kimlikleri

| Sıra | Req/Test ID | Gösterim | Yazılım kanıtı | Fiziksel kabul | Mevcut Durum |
| ---: | --- | --- | --- | --- | --- |
| 1 | `VID-Y1-UI` | Kullanıcı arayüzü, joystick/klavye ve bütün fonksiyonların anlatımı | Frontend unit/Playwright, `StageRequest`, `ModeRequest`, `ManualAimCommand`, `FireIntent` olayları | Entegre panel, gerçek operatör girdileri | ✅ Yazılım tam; fiziksel panel bağlantısı açık |
| 2 | `VID-Y2-15M` | Sistem durağanken 15 m balon imhası | `FireIntent`, Safety snapshot, menzil/track ve video frame index'i | HIL sonrası kontrollü 15 m hedef testi | ⚠️ Yazılım pipeline hazır; LiDAR kalibrasyon + fiziksel atış açık |
| 3 | `VID-Y3-ESTOP-MOTION` | Yan/yükseliş hareketi sırasında Acil Durdur ile sistemin durması | `ESTOP_CHANGE`, `BLOCKED_ESTOP`, USB/encoder zaman damgaları | Motor enerjisinin donanımsal kesilme süresi | ⚠️ Yazılım + firmware tam; fiziksel motor testi açık |
| 4 | `VID-Y4-ESTOP-FIRE` | Ateş sırasında Acil Durdur ile ateşin kesilmesi | `ESTOP_CHANGE`, fire command/result ve interlock olayı | Güvenli yapay yükle ateş hattı kesme testi | ⚠️ Yazılım + firmware tam; fiziksel ateş hattı testi açık |
| 5 | `VID-Y5-TRACK` | Yan ve yükseliş ekseninde hareket eden hedef takibi | Track ID, bearing, pan/tilt feedback, frame index | Gerçek hareketli hedefle yaw/elev takip | ⚠️ HSV+CentroidTracker çalışıyor; SAHI/Hailo HEF modeli yok |
| 6 | `VID-Y6-CLASSIFY` | 5/10/15 m hedef tipi tespit/sınıflandırma | Classification, TFA50-L range, UI hedef tipi | Gerçek hedef yüzeyi ve kayıtlı mesafe | ❌ HEF model artefaktı yok; TFA50-L fiziksel kalibrasyon açık |
| 7 | `VID-Y7-IFF` *(opsiyonel)* | ~10 m'de 1 kırmızı düşman ve 2 camgöbeği dost arasından düşmanın altındaki kırmızı balonu otonom imha; 10 sn sonra Acil Durdur | Maket sınıf + maket→balon ilişkisi, Safety Gate, `AUTO_ENGAGE`, `ESTOP_CHANGE` | Dost makete ait kırmızı balona ateş edilmediğinin entegre fiziksel gösterimi | ❌ balloon_association.py yazılmamış |

`frontend/src/missionConfig.ts` içindeki `Y1`–`Y7` sırası bu tabloyla aynı
kalmalıdır. Fiziksel kabul sütunu tamamlanmadan yalnız simülasyon videosu
"yetenek tamamlandı" kanıtı sayılamaz.

## Yazılım kanıtı hazır olan yetenekler (simülatör + test)

Bu bölüm fiziksel kabul bekleyen ama yazılım kanıtı olan yetkinlikleri listeler.
Bunlar gerçek videoya ek arka plan kanıtı olarak saklanır:

- **Y1-UI:** `npm run test` + Playwright e2e — tam; simülatör videosu çekilebilir
- **Y2-15M:** Safety Gate, FireIntent, menzil mock ile dry-run — tam
- **Y3/Y4 E-STOP:** `test_phase4_safety.py` + `test_hardware_adapter.py` — tam; HIL mock
- **Y5-TRACK:** `test_perception_bridge.py` + `test_sahi_search.py` — yazılım tam
- **Y6-CLASSIFY:** `target_detector_contract.json` release gate'ler PENDING

## Perception pipeline durumu (15 Ağustos 2026 itibarıyla)

Yetenek videosunun **Y5** ve **Y6** bölümleri için perception altyapısının durumu:

| Bileşen | Durum |
|---------|-------|
| HSV renk filtresi + CentroidTracker | ✅ Çalışıyor |
| SAHI tiled search engine | ✅ Yazılım hazır |
| Hailo-8 health probe | ✅ Çalışıyor |
| HEF model artefaktı | ❌ Yok — gerçek veri + eğitim gerekiyor |
| Balon ayrı track (`objectRole=balloon`) | ✅ frame_processor'a eklendi |
| balloon_association.py | ❌ Yazılmamış (Balon Planı Faz 1) |
| Kamera kalibrasyonu | ⚠️ Nominal IMX708 değerleri mevcut; UNVERIFIED |
| Distortion düzeltmesi | ✅ Brown-Conrady eklendi; katsayılar fiziksel ölçüm bekliyor |
| TFA50-L menzil füzyonu | ⚠️ Yazılım hazır; fiziksel kalibrasyon açık |

## Video paketleme kontrolü

- [ ] Zorunlu `VID-Y1`–`VID-Y6` sırası değişmedi.
- [ ] Opsiyonel `VID-Y7` gösteriliyorsa Y6'dan sonra.
- [ ] Her bölümün `run_id`, config hash ve calibration hash'i kayıtlı.
- [ ] Video saat aralıkları telemetri event ID'leriyle eşleşiyor.
- [ ] Gerçek fiziksel çıkış kullanılan bölümler ayrı güvenlik tutanağına bağlı.
- [ ] YouTube linki liste dışı/farklı cihaz testinden geçti.
