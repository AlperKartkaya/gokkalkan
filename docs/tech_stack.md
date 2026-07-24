# Gökkalkan Teknik Yönelim ve Yazılım Mimarisi

Bu doküman, Gökkalkan yazılımının teknik yönünü `docs/sartname_v1_3.pdf` şartnamesine göre belirler. Şartname ile bu doküman arasında çelişki olursa şartname geçerlidir. PDF’in metin kopyası `docs/sartname_v1_3.txt` dosyasında tutulur.

## 1. Şartnameye Göre Sistem Hedefi

Gökkalkan; kullanıcı denetimli Manuel Mod, Otonom Mod, hedef tespit/takip, dost-düşman ayrımı, güvenli hareket/atış izni, Acil Durdur ve görev kaydı özelliklerini birleştiren TEKNOFEST 2026 Çelikkubbe sistemidir.

Yazılım tasarımı şu yarışma gerçeklerine göre optimize edilmelidir:

- Sistem manuel ve otonom modları desteklemelidir; mod geçişleri kullanıcı denetimindedir.
- Aşama 1 tamamen Manuel Mod ile, Aşama 2 Otonom Mod ile, Aşama 3 dost/düşman + menzil kapısı gerektiren otonom akışla yürür.
- Hareket ve atış için ayrı yasak bölgeler tanımlanmalıdır: `harekete yasak alan` ve `atışa yasak alan`.
- Dışarıya çıkan kablo ile güvenli konumda fiziksel `Acil Durdur` butonu zorunludur.
- Patlayıcı hedef imha çözümü yasaktır.
- 5 m, 10 m ve 15 m menzil bantları görev ve puanlamada ana referanstır.

## 2. Yarışma Aşamaları ve Yazılım Gereksinimleri

### 2.1. Aşama 1 — Farklı Menzillerde Duran Hedef İmhası

Bu aşama tamamen Manuel Mod ile yapılır. Kullanıcı arayüzü üzerinden yönlendirme ve ateş emri verilir; her atıştan sonra yeni hedefe yönelme ve yeniden ateşleme kullanıcı komutuyla başlatılır.

Yazılım gereksinimleri:

- Hassas pan/tilt yönlendirme ve kullanıcı komutu ile atış niyeti.
- Yarışma öncesi verilen hedef sırasını operatöre açık gösterme.
- Yanlış hedef/sıra riskini azaltan uyarılar.
- `5 dakika` görev süresi ve kalan süre kaydı.
- Aşama geçiş eşiği: en az `30 puan`.

### 2.2. Aşama 2 — Sürü Saldırısı ve Hedeflerin İmhası

Bu aşama Otonom Mod ile yapılır. Sistem açıldıktan sonra kullanıcı sistemi otonom moda alır; otomatik hedef tespit, takip ve imha görevleri çalışır. Şartname bu aşamada hedef tipi sınıflandırması beklemez.

Yazılım gereksinimleri:

- Üç koldan yaklaşan hedefleri tespit ve takip etme.
- Her turda parkurdaki hedefleri tur tamamlanmadan imha etmeye yönelik önceliklendirme.
- Hedef vuramama durumlarını kaydetme; 3 tur boyunca hedef vuramama başarısızlık sebebidir.
- Aşama geçiş eşiği: en az `20 puan`.

### 2.3. Aşama 3 — Farklı Katmanlardaki Hareketli Hedeflerin İmhası

Bu aşama Otonom Mod içinde dost-düşman ayrımı gerektirir. Her turda 1 düşman hedef ve 2 dost unsur yaklaşır; sistem düşman hedefi tespit edip hedef tipine göre uygun menzilde imha etmelidir.

Yazılım gereksinimleri:

- Dost hedefi vurmamak için hedef tipi, renk/şekil ve görev bağlamını birlikte değerlendirme.
- Hedef tipine göre menzil kapısı uygulama:
  - F16: `10–15 m` aralığında imha puanlanır.
  - Helikopter ve Balistik Füze: `5–15 m` aralığında imha puanlanır.
  - Mini/Micro İHA: `0–15 m` aralığında imha puanlanır.
- Dost hedef vurma ve düşman hedef vuramama durumlarını ceza olarak kaydetme.
- 3 ardışık tur boyunca düşman hedef vuramama başarısızlık sebebidir.
- Başarı eşiği ve ödül sıralamasına girebilme koşulu: Aşama 3’ten en az `10 puan`.

## 3. Ürün Yüzeyleri

### 3.1. Yarışma Eğitim Simülatörü

`frontend/` içinde bulunan mevcut uygulama React + Vite + TypeScript tabanlı bir yarışma eğitim simülatörüdür. Gerçek donanım komutu üretmez. Amacı; parkur, aşama, tur, hedef, dost/düşman, menzil ve puan mantığını yarışmacıya öğretmek ve KTR/video hazırlığına görsel kanıt sağlamaktır.

Mevcut simülatör özellikleri:

- Aşama 1 durağan hedef pratiği ve manuel FIRE akışı.
- Aşama 2 üç kollu A→B sürü hareketi ve otonom angajman görselleştirmesi.
- Aşama 3 düşman/dost ayrımı, menzil kapısı ve dost hedef koruma davranışı.
- Aşama bazlı skippable onboarding; rehber sırasında sayaç, hareket ve skor durur.
- Debug bilgileri ana ekran yerine gelişmiş çekmecede tutulur.

### 3.2. Gerçek Operatör Paneli

Planlanan gerçek operatör paneli, final fazında backend/perception/sensör/donanım katmanlarına bağlanacak canlı kontrol istasyonudur. Simülatörle aynı tasarım dilinden yararlanabilir; ancak simülasyon puanı veya varsayımsal sensör verisi gerçek görev durumuyla karıştırılmamalıdır.

Temel ilke: UI doğrudan motor veya imha hattı sürmez. UI yüksek seviye niyet gönderir; backend Safety Gate onaylarsa Hardware Adapter düşük seviye komuta çevirir.

Önerilen komut zinciri:

```text
Operatör Paneli → Backend API → Mission/Engagement Manager → Safety Gate → Hardware Adapter → MCU / Pan-Tilt / İmha Hattı
```

## 4. Yazılım Mimarisi

### 4.1. `backend/` — Görev Çekirdeği ve Donanım Denetimi

`backend/` sistemin güvenlik-kritik karar katmanıdır. Burada mod yönetimi, görev durum makinesi, atış izni, hareket sınırları, acil durdurma, donanım haberleşmesi ve telemetri üretimi yer almalıdır.

Temel alt bileşenler:

- **Mode Manager:** Manuel/Otonom/Bakım/Safe mod geçişlerini kullanıcı denetimine bağlar.
- **Mission State Machine:** Aşama 1, Aşama 2, Aşama 3 ve video görevlerini ayrı durum makineleri olarak yönetir.
- **Engagement Manager:** seçili/hedeflenen iz, hedef tipi, dost/düşman, menzil ve tur bağlamından angajman isteği üretir.
- **Safety Gate:** Acil Durdur, harekete yasak alan, atışa yasak alan, mod uyumu, hedef/menzil kapısı, bağlantı sağlığı ve hakem/operatör kilidi sağlanmadan hareket veya atış komutu üretmez.
- **Hardware Adapter:** Safety Gate’ten geçen yüksek seviye komutu MCU/protokol düzeyine çevirir.
- **Telemetry Logger:** zaman damgalı mod, hedef, komut, güvenlik, hata ve atış kayıtları üretir.

### 4.2. `backend/hardware_mock/` — Donanım Simülasyonu

Gerçek donanım bağlanmadan önce pan/tilt hareketi, Acil Durdur, atış izni, hedef menzili ve görev akışları burada denenmelidir. Mock katmanı gerçek donanım gibi davranan ama fiziksel çıkış üretmeyen adaptör olmalıdır.

**Mevcut durum:** `mcu_simulator.py` çalışır durumda. Sanal CAN (vcan0/virtual) üzerinden gelen komutları alır, pan/tilt durumunu ASCII olarak görselleştirir, E-stop simüle eder ve periyodik 0x200 durum paketi gönderir. Gerçek Pico firmware yazılmadan CAN protokolü test edilebilir.

### 4.3. `perception/` — Algı, Takip ve Sınıflandırma

`perception/` kamera verisinden hedef adaylarını üretir. Şartname hedeflerin maket, renk/şekil ve balonla temsil edileceğini söylediği için ilk tercih basit, açıklanabilir ve test edilebilir görüntü işleme olmalıdır; yapay zekâ modeli ancak gerçek hedef görselleri ve saha testleri bunu gerektirirse eklenmelidir.

**Mevcut durum:** `camera_node.py` (Picamera2/OpenCV otomatik seçim), `frame_processor.py` (HSV renk filtresi + CentroidTracker), `perception_bridge.py` (10Hz poll → POST /tracks/update). Aşama 2 renk-nötr, Aşama 3 kırmızı=Düşman/mavi=Dost.

Önerilen öncelik:

1. Kamera kalibrasyonu, görüntü sabitleme ve gecikme ölçümü.
2. Renk/şekil tabanlı hedef aday çıkarımı. ✅ Uygulandı.
3. Basit takip: merkez noktası, hız tahmini, hedef geçmişi. ✅ CentroidTracker uygulandı.
4. Aşama 2 için sınıflandırmasız takip ve önceliklendirme. ✅ Uygulandı.
5. Aşama 3 için dost-düşman ayrımı, hedef tipi ve menzil kapısı. ✅ Renk sınıflaması uygulandı; LiDAR menzili TBD.
6. Gerekiyorsa YOLO/DeepSORT/Hailo gibi model tabanlı yaklaşım.

### 4.4. `frontend/` — Simülatör ve Operatör Arayüzleri

`frontend/` bugün React/Vite/TypeScript simülatörünü içerir. Aynı frontend içinde yeni bir gerçek operatör paneli sayfası eklemek önerilir; çünkü mevcut parkur, hedef, safety summary, onboarding ve Türkçe yarışma dili bileşenleri tekrar kullanılabilir. Eğer saha koşulları native/kiosk UI gerektirirse PySide6 alternatifi ayrıca değerlendirilebilir; şu an tek zorunlu seçenek olarak yazılmamalıdır.

Arayüz hedefleri:

- Simülatörde: görev eğitimi, puan/menzil/tur görselleştirme, kullanıcı onboarding’i.
- Gerçek panelde: aşama/tur görev bağlamı, canlı kamera/sensör alanı, radar/LiDAR biçimli `SensorFrame` replay/akış görünümü, backend durumları, mod seçimi, deadman’li manuel pan/tilt niyeti, FireIntent, seçili hedef detayı, hedef tipi + dost/düşman + menzil kapısı yorumu, Safety Gate gerekçesi, hardware mock geri bildirimi, `Finale Hazırlık` arayüz/gap göstergesi, adapter/TBD bakım çekmecesi ve kapalı gelen JSONL kanıt/replay çekmecesi.
- Her iki yüzeyde: Türkçe yarışma terimleri, açık blok nedeni, Acil Durdur farkındalığı ve telemetri olayı.

### 4.5. `tests/` — Senaryo ve Regresyon Testleri

Testler şartname senaryolarına göre yazılmalıdır. Öncelik, güvenlik kapısının asla yanlışlıkla açılmaması ve görev durum makinelerinin beklenen aşama kurallarını uygulamasıdır.

Örnek test sınıfları:

- Manuel modda kullanıcı komutu olmadan ateş niyeti çıkmaması.
- Acil Durdur aktifken hareket ve atış komutlarının kesilmesi.
- Atışa yasak alanda hedef olsa bile ateş izni verilmemesi.
- Aşama 2’de sınıflandırma zorunlu değilken takip/imha akışının çalışması.
- Aşama 3’te dost hedefin vurulmaması ve menzil kapısının uygulanması.
- Gerçek operatör paneli API istemcisinin dry-run modda hardware çıkışı üretmemesi.

## 5. Arayüz Mimarisi ve KTR İçeriği

KTR’de “arayüz” yalnız kullanıcı ekranı olarak anlatılmamalıdır. Aşağıdaki sınırlar ayrıca dokümante edilmelidir.

### 5.1. Kullanıcı arayüzü

| Arayüz | Rol | Önerilen teknoloji | Güvenlik notu |
| --- | --- | --- | --- |
| Eğitim simülatörü | Yarışma provası, onboarding, puan/görev eğitimi | React + Vite + TypeScript | Gerçek donanım komutu göndermez |
| Gerçek operatör paneli | Mod seçimi, canlı izleme, manuel yönlendirme niyeti, ateş niyeti, blok gerekçesi | React/Vite içinde ayrı sayfa + dry-run Backend API | UI doğrudan motor veya ateşleme/imha hattını enerjilendirmez |
| Debug/kalibrasyon görünümü | Geliştirici/entegrasyon teşhisi | Gelişmiş çekmece veya ayrı bakım ekranı | Operatör ana ekranından ayrı tutulur |

### 5.2. Yazılımsal mesaj arayüzleri

| Kaynak → Hedef | Mesaj örnekleri | İlk protokol önerisi | Not |
| --- | --- | --- | --- |
| Operatör Paneli → Backend | `StageRequest`, `ModeRequest`, `ManualAimCommand`, `FireIntent`, `MaintenanceRequest` | localhost/LAN HTTP + WebSocket | Komutlar niyettir; yetki backend’dedir |
| Backend → Operatör Paneli | `MissionState`, `SafetyState`, `TrackState`, `SensorFrame`, `CommandResult`, `TelemetryEvent` | WebSocket stream + REST snapshot | UI her blok nedenini Türkçe gösterir |
| Perception → Backend | `TrackState`, `Classification`, `FrameHealth` | Python içi queue, ZeroMQ/WebSocket veya REST adapter; seçim entegrasyona göre | Saha gecikmesi ölçülmeden kesin protokol dayatılmamalı |
| Backend → Hardware Adapter | `HardwareCommand`, `FireAuthorization`, `StopMotion` | Python adapter interface | Sadece Safety Gate sonrası çağrılır |
| Hardware Adapter ↔ MCU | pan/tilt, imha hattı enable/disable, durum geri bildirimi | Klasik CAN 2.0B, 500 kbit/s | ADR-002; v0 codec fiziksel LIVE release için yeterli değildir |
| TFA50-L Adapter → Backend/Perception | tek nokta menzil, health, receive timestamp | UART; adapter sınırı | Protokol decoder mevcut, gerçek serial/kalibrasyon bekliyor |

### 5.3. Elektronik / güç / sinyal arayüzleri

Kesin gerilim, konnektör ve protokol değerleri elektronik tasarım netleşmeden resmiymiş gibi yazılmamalıdır. KTR’de şu formatla verilmesi önerilir:

| Arayüz | Durum | KTR’de yazılacak bilgi |
| --- | --- | --- |
| Ana güç | **Onaylandı** | Mean Well RSP-500-24: 220V AC → 24V DC, 500W, 21A. Motor sürücüler 24V; RPi5/MCU 5V reg. üzerinden |
| Logic güç | **Onaylandı** | 24V→5V DC-DC reg. (×4): RPi5, Pico, fan. 24V→12V reg. (×2): yardımcı hat |
| Acil Durdur | **Zorunlu** | Schneider XB5AS8442 (Ø40, mantar, 1NK, çevir-çek). Pico GPIO izleme + emniyet rölesi (Schneider XPS) motor güç hattında. CAN 0x201 üzerinden RPi5'e anlık bildirim |
| MCU haberleşmesi | **Onaylandı** | Klasik CAN 2.0B, 500 kbit/s; SN65HVD230 (×3); ISO 11898-2; 0x100 pan/tilt, 0x101 ateş, 0x102 sistem, 0x200 durum, 0x201 E-stop. Ayrıntı: ADR-002 |
| Kamera | **Onaylandı** | Raspberry Pi Camera Module 3 (12MP, OT AF, HDR), CSI bağlantı, Picamera2 API |
| LiDAR | **Aday seçildi** | Benewake TFA50-L tek nokta UART LiDAR; yaw ile dönen/pitch-sabit merkezî köprü. Gerçek 5/10/15 m kabul testi bekliyor |
| İmha hattı | Güvenlik-kritik | Airsoft yay mekanizması (yay seti + şarjör). Yalnız Safety Gate + hardware interlock sonrası enable edilir. Patlayıcı yasak |

## 6. Teknoloji Seçimi

Şartname belirli bir programlama dili veya yapay zekâ modeli zorunlu kılmaz. Bu repo için teknik yön şu şekilde güncellenmiştir:

- **Simülatör UI:** React + Vite + TypeScript (`frontend/`).
- **Gerçek operatör paneli:** React/Vite içinde ayrı sayfa + dry-run Backend API. Yazılım yüzeyi aşama/tur seçimi, radar/LiDAR biçimli `SensorFrame` replay görünümü, hedef tipi + dost/düşman + menzil yorumu, mod seçimi, manuel pan/tilt niyeti, FireIntent, Safety Gate, hardware mock sonucu ve kanıt/replay için tamamlanmıştır. `npm run desktop` launcher’ı backend API + UI + desktop app-window akışını Linux/macOS/Windows geliştirme makinelerinde tek komutla başlatır; gerçek paketleme hedefi saha bilgisayarına göre AppImage/kiosk veya `.exe` olarak ayrıca kilitlenmelidir.
- **Vendor LiDAR viewer stratejisi:** RPLIDAR Viewer, Livox Viewer ve benzeri üretici araçları görev arayüzü değildir. Bunlar bakım, kalibrasyon, firmware/IP/serial doğrulama ve ham point cloud kontrolünde dış diagnostic araç olarak kalır. Görev panelindeki veri yolu `SDK/driver → SensorFrame → Backend → Operatör Paneli` olmalıdır; vendor pencere embed/screen-scrape edilmemelidir.
- **Hedef runtime:** Raspberry Pi 5 üzerinde doğrudan 64-bit Raspberry Pi OS + `systemd`; hedefte VM yok. Ayrıntı: ADR-001.
- **Backend / görev çekirdeği:** Python 3.x.
- **Backend API dry-run geçişi:** bağımlılıksız dry-run HTTP iskeleti (`gokkalkan_backend.operator_http_server`); canlı donanım çıkışı üretmez, `POST /stage`, `POST /mode`, `POST /manual-aim`, `POST /fire-intent`, `GET /sensor-frames`, JSONL telemetri, `/readiness` entegrasyon hazırlığı endpoint’i ve `/telemetry/export` + `/replay` kanıt endpoint’leri sağlar.
- **Görüntü işleme:** OpenCV; gerçek hedef görselleri netleşirse model tabanlı algı eklenebilir.
- **Kamera:** Raspberry Pi uyumlu kamera hattı için Picamera2 değerlendirilebilir.
- **Donanım haberleşmesi:** MCU için python-can/SocketCAN ile klasik CAN; TFA50-L için pySerial/UART. Vendor aracı runtime bağımlılığı değildir.
- **Test:** pytest + frontend için Vitest/Playwright.
- **Log formatı:** dry-run operatör API için JSONL uygulanmıştır (`telemetry_data/operator-api-dry-run.jsonl`, git’e eklenmez). Canlı saha log saklama politikası ve elektronik entegrasyon metrikleri donanım seçimiyle netleştirilmelidir.

ROS 2 ve tam Rust yeniden yazımı bu fazın parçası değildir. Yeniden değerlendirme
eşikleri ADR-001’de tanımlıdır. Hailo veya derin öğrenme tabanlı algı da yalnızca
gecikme/doğruluk testleri ihtiyaç gösterirse eklenir.

## 7. İş Paketi Eşlemesi

- **WP-01 Manuel Mod:** Aşama 1, kullanıcı arayüzü, manuel pan/tilt ve kullanıcı komutlu ateş niyeti.
- **WP-02 Otonom Tespit ve Takip:** Aşama 2, hareketli hedef tespiti, takip ve tur içinde imha kararı.
- **WP-03 Dost-Düşman + Menzil:** Aşama 3, dost-düşman ayrımı, hedef tipi ve menzil kapısı.
- **WP-04 Güvenlik Katmanı:** Acil Durdur, harekete yasak alan, atışa yasak alan, güvenli varsayılan durum.
- **WP-05 Log/Telemetri:** Görev olayları, video kanıtı, rapor kanıtları, hata ayıklama ve tekrar oynatma kayıtları.

## 8. Doğrulama Önceliği

Kod eklendiğinde doğrulama sırası şu olmalıdır:

1. Güvenlik kapısı ve Acil Durdur birim testleri.
2. Mock donanımla manuel mod ve otonom mod senaryo testleri.
3. Backend API dry-run testleri: UI komutu hardware çıkışı üretmeden CommandResult döndürmeli; `/readiness` final fazı boşluklarını resmi uygunluk skoru gibi göstermemeli; `/telemetry/export` ve `/replay` kayıtları fiziksel çıkışsız olmalı.
4. Kamera/perception kayıtlarıyla algı ve takip tekrar testleri.
5. Operatör arayüzünde gerçek görev akışı denemesi.
6. Gerçek donanımda düşük güç/güvenli koşul testi.
7. Şartnamedeki video yetenek sırasına göre uçtan uca prova.

Her teknik karar, şartnamedeki görev başarısı ve güvenlik kurallarıyla gerekçelendirilebilmelidir.
