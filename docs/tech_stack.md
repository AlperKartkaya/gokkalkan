# Gökkalkan Teknik Yönelim ve Yazılım Mimarisi

Bu doküman, Gökkalkan yazılımının teknik yönünü `docs/sartname_v4.pdf` şartnamesine göre belirler. Şartname ile bu doküman arasında çelişki olursa şartname geçerlidir. PDF’in metin kopyası `docs/sartname_v4.txt` dosyasında tutulur.

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
- Aşama geçiş eşiği: en az `20 puan`.
- Aşama 1 ve Aşama 2 hedef maketlerini kırmızı hedef olarak algılama; imha değerlendirmesinin maket değil maketin altındaki kırmızı balon üzerinden yapıldığını operatöre gösterme.

### 2.2. Aşama 2 — Sürü Saldırısı ve Hedeflerin İmhası

Bu aşama Otonom Mod ile yapılır. Sistem açıldıktan sonra kullanıcı sistemi otonom moda alır; otomatik hedef tespit, takip ve imha görevleri çalışır. Şartname bu aşamada hedef tipi sınıflandırması beklemez.

Yazılım gereksinimleri:

- Üç koldan yaklaşan hedefleri tespit ve takip etme.
- Her turda parkurdaki hedefleri tur tamamlanmadan imha etmeye yönelik önceliklendirme.
- Hedef vuramama durumlarını tur başına `-5 puan` olarak kaydetme; v1.4’te Aşama 2 için ardışık isabetsiz tur nedeniyle bütün aşamayı sıfırlayan ayrı bir koşul bulunmaz.
- Aşama geçiş eşiği: en az `20 puan`.

### 2.3. Aşama 3 — Farklı Katmanlardaki Hareketli Hedeflerin İmhası

Bu aşama Otonom Mod içinde dost-düşman ayrımı gerektirir. Her turda 1 düşman hedef ve 2 dost unsur yaklaşır; sistem düşman hedefi tespit edip hedef tipine göre uygun menzilde imha etmelidir.

Yazılım gereksinimleri:

- Dost hedefi vurmamak için hedef tipi, maket rengi/şekli ve görev bağlamını birlikte değerlendirme; bütün balonlar kırmızı olduğundan balon rengini dost/düşman kanıtı saymama.
- Hedef tipine göre menzil kapısı uygulama:
  - F16: `10–15 m` aralığında imha puanlanır.
  - Helikopter ve Balistik Füze: `5–15 m` aralığında imha puanlanır.
  - Mini/Micro İHA: `0–15 m` aralığında imha puanlanır.
- Dost hedef vurma ve düşman hedef vuramama durumlarını ceza olarak kaydetme.
- 4 ardışık tur boyunca düşman hedef vuramama başarısızlık sebebidir.
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

Gerçek operatör panelinin yazılım yüzeyi, backend/perception/sensör/donanım katmanlarına bağlanan canlı kontrol istasyonu olarak uygulanmıştır. Simülatörle aynı tasarım dilinden yararlanır; ancak simülasyon puanı veya varsayımsal sensör verisi gerçek görev durumuyla karıştırılmaz. Backend bağlantısı yoksa hedef, güvenlik durumu veya hazırlık yüzdesi uydurmaz ve fail-closed kalır.

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

**Mevcut concurrency sınırı:** `MissionCore`, frozen `MissionState` modelinin tek
yazarıdır. HTTP, CAN/GPIO callback ve sensör üreticileri bounded kuyruğa
`CommandEnvelope` bırakır; reducer sıralı `EventEnvelope` ve immutable snapshot
üretir. UI snapshot’ı SSE üzerinden izler ve yalnız stream kesilirse düşük hızlı
REST polling kullanır. Ayrıntılar: ADR-004 ve `docs/message_contracts.md`.

### 4.2. `backend/hardware_mock/` — Donanım Simülasyonu

Gerçek donanım bağlanmadan önce pan/tilt hareketi, Acil Durdur, atış izni, hedef menzili ve görev akışları burada denenmelidir. Mock katmanı gerçek donanım gibi davranan ama fiziksel çıkış üretmeyen adaptör olmalıdır.

**Mevcut durum:** `mcu_simulator.py`, ortak firmware güvenlik modelini kullanarak
E-Stop/FAULT sırasında komutları reddeder. Aktif `docs/usb_serial_mcu_protocol.md`,
`usb_serial_protocol.py`, `usb_serial_adapter.py` ve legacy `firmware/pico/` altında
COBS, CRC16, sequence, ACK/NACK, encoder geri bildirimi ve host-testli Pico
güvenlik çekirdeği vardır. Tarihsel CAN payload codec'i regresyon uyumu için
korunur. Bu, fiziksel Arduino flash/USB/E-Stop/motor hattı kabulünün tamamlandığı anlamına
gelmez; söz konusu kanıtlar imalat sonrası HIL ve saha testinde üretilecektir.

### 4.3. `perception/` — Algı, Takip ve Sınıflandırma

`perception/` tek Raspberry Pi Camera Module 3 Standard verisinden hedef
adaylarını üretir. Kamera ve TFA50-L, yaw'ı izleyen fakat silah pitch'ini
izlemeyen sensör köprüsündedir; LiDAR optik merkezi en alt noktadan 700 mm
yukarıdadır. Kesin mekanik model
[`taret_mekanik_ve_sensor_yerlesimi.md`](taret_mekanik_ve_sensor_yerlesimi.md)
içinde tutulur.

**Mevcut durum:** `camera_node.py` (Pi'de Picamera2, geliştirmede açıkça işaretli
OpenCV fallback),
`frame_processor.py` (HSV renk filtresi + CentroidTracker),
`accelerator.py` (AI HAT+ 26 TOPS/Hailo-8 ve HEF hazırlık health sınırı),
`perception_bridge.py` (ayrı `systemd` process’i; bounded latest-wins queue,
heartbeat ve POST `/tracks/update`). Aşama 2 renk-nötr, Aşama 3
kırmızı=Düşman/camgöbeği (`#00A3E0`)=Dost. Bütün maketlerin altındaki kırmızı
balon ayrı imha nesnesidir; maket→balon ilişkisi kurulmadan ateş yetkisi yoktur.
Heartbeat kaybı Mission Core’da perception fault’u
oluşturup canlı arm iznini kapatır.

Önerilen öncelik:

1. Kamera kalibrasyonu, görüntü sabitleme ve gecikme ölçümü.
2. Renk/şekil tabanlı hedef aday çıkarımı. ✅ Uygulandı.
3. Basit takip: merkez noktası, hız tahmini, hedef geçmişi. ✅ CentroidTracker uygulandı.
4. Aşama 2 için sınıflandırmasız takip ve önceliklendirme. ✅ Uygulandı.
5. Aşama 3 için dost-düşman ayrımı ve menzil kapısı. ✅ Renk sınıflaması,
   TFA50-L UART adapterı ve kamera-yaw-menzil ilişkilendirme hattı uygulandı;
   gerçek 5/10/15 m kalibrasyon kanıtı imalat sonrası açık.
6. Hedef tip modeli: dört özgün maket geometrisinden üretilen altı kanonik sunum varyantı
   `perception/assets/target_prints/` altında sürümlenmiştir. Gerçek Camera
   Module 3 baskı kayıtları ana veri olacak; SAHI-sliced YOLOv8s birincil aday,
   YOLOv8n throughput fallback'i, klasik HSV/template ise tanısal baseline olarak
   aynı grup-split testinde karşılaştırılacaktır. Kazanan model HEF'e
   çevrilip AI HAT+ üzerinde doğrulanana kadar tip `Bilinmeyen` kalır. Ayrıntı:
   `docs/hedef_gorseli_yolo_veri_plani.md`.

### 4.4. `frontend/` — Simülatör ve Operatör Arayüzleri

`frontend/` React/Vite/TypeScript eğitim simülatörü ile gerçek operatör panelini birlikte içerir. İki yüzey görsel/UX kalıplarını paylaşır; görev state’i ve güvenlik yetkisi paylaşmaz. Eğer saha koşulları native/kiosk UI gerektirirse mevcut web paneli masaüstü/kiosk kabuğunda paketlenebilir; ikinci bir UI teknoloji yığını zorunlu değildir.

Arayüz hedefleri:

- Simülatörde: görev eğitimi, puan/menzil/tur görselleştirme, kullanıcı onboarding’i.
- Gerçek panelde: aşama/tur görev bağlamı, gerçek MJPEG kamera görüntüsü, merkez nişangâh, canlı TFA50-L 1D menzil değeri, seçilebilir manuel pan/tilt adımı, aktif taret kalibrasyon kimliği, kalibre edilmiş balistik holdover, backend `MissionFlow`, FireIntent, görev duraklatma/devam, bakım, Safety Gate gerekçesi, hardware health ve JSONL kanıt/replay çekmecesi bulunur. Hedef, Safety ve görev state'i backend SSE/REST snapshot'ından gelir; UI sentetik hedef kimliği, kamera görüntüsü veya optimistik güvenlik state'i üretmez.
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
| Operatör Paneli → Backend | `StageRequest`, `ManualAimCommand`, `FireIntent`, `MissionStop`, `MissionResume`, `MaintenanceStart/End` | localhost/LAN HTTP → bounded Mission Core queue | Komutlar niyettir; görev ve Safety yetkisi backend’dedir |
| Backend → Operatör Paneli | `MissionState`, `SafetyState`, `TrackState`, `SensorFrame`, `CommandResult`, `TelemetryEvent` | SSE state stream + REST snapshot fallback | UI her blok nedenini Türkçe gösterir |
| Perception → Backend | `TrackState`, `Classification`, `FrameHealth` | ayrı process, bounded latest-wins queue, REST + heartbeat | Process çökmesi core’u çökertmez; angajman kapanır |
| Backend → Hardware Adapter | `HardwareCommand`, `FireAuthorization`, `StopMotion` | Python adapter interface | Sadece Safety Gate sonrası çağrılır |
| Hardware Adapter ↔ MCU | pan/tilt, imha hattı enable/disable, durum geri bildirimi | **Uygulanan:** USB CDC Serial + COBS + CRC16 | `UsbSerialMcuAdapter`, `usb_serial_mcu_protocol.md` ve ADR-005 aktiftir; fiziksel HIL/EMI kabulü bekliyor |
| TFA50-L Adapter → Backend/Perception | tek nokta menzil, health, receive timestamp | UART; adapter sınırı | Protokol decoder mevcut, gerçek serial/kalibrasyon bekliyor |

### 5.3. Elektronik / güç / sinyal arayüzleri

Kesin gerilim, konnektör ve protokol değerleri elektronik tasarım netleşmeden resmiymiş gibi yazılmamalıdır. KTR’de şu formatla verilmesi önerilir:

| Arayüz | Durum | KTR’de yazılacak bilgi |
| --- | --- | --- |
| Ana güç | **Onaylandı / fiziksel kabul açık** | Mean Well RSP-500-24: 220V AC → 24V DC, 500W, 21A. RSP +24 V → 20 A ana sigorta → 6 yollu ATO/ATC kutu → LP1K1210BD ana kutupları → PAN/TILT DM542 yükleri. 1 A kontrol dalı kontaktör ana kutuplarından önce alınır |
| Logic güç | **Onaylandı** | 24V→5V DC-DC reg. (×4): RPi5, Arduino, fan. 24V→12V reg. (×2): yardımcı hat |
| Acil Durdur | **Zorunlu / asgari tek kanal** | Mevcut kilitlemeli Gwest LAY2-KSE542E tek NK → LP1K1210BD 24 VDC kontaktör + anlık 1NA START mühürleme + LA4KE1B. E-Stop bırakılınca START olmadan kontaktör çekmez. `X` noktası izole giriş üzerinden Arduino güvenli duruşuna gelir. Bu mimari çift kanallı/SIL olarak tanımlanmaz |
| Koruyucu toprak | **Onaylandı / fiziksel ölçüm açık** | Şebeke PE, RSP FG ve erişilebilir metal şasi ayrı ring pabuçlarla M5 yıldız noktasında birleşir; DC 0 V ile PE aynı sinyal değildir |
| MCU haberleşmesi | **Yazılım uygulandı / fiziksel kabul açık** | Pi 5 ↔ Arduino Uno USB seri; 115200 baud satır tabanlı STEP/JOG/STOP/STATUS komutları ve kararlı `/dev/serial/by-id/...` seçimi. Ayrıntı ADR-006'dadır |
| Kamera | **Onaylandı** | Tek Raspberry Pi Camera Module 3 Standard (12MP, AF, HDR, nominal 66° yatay FoV), CSI bağlantı, Picamera2 API; LiDAR merkezi 700 mm olan yaw köprüsünde, weapon pitch'ten bağımsız |
| LiDAR | **Yazılım hazır / fiziksel kabul açık** | Benewake TFA50-L tek nokta UART LiDAR; decoder, yeniden bağlanabilen serial adapter ve kamera-yaw füzyon kapısı uygulanmıştır. Gerçek 5/10/15 m kabul testi bekliyor |
| AI hızlandırıcı | **Onaylandı / model açık** | Raspberry Pi AI HAT+ 26 TOPS, Hailo-8, PCIe; `hailo-all` + `hailortcli` health sözleşmesi hazır. HEF model artefaktı ve saha metrikleri bekliyor |
| İmha hattı | **Güvenlik-kritik / DC kesme elemanı doğrulanacak** | APS PER701 kendi 7,4 V T-Plug alanında kalır; 24 V baraya bağlanmaz. Ayrı kapaklı sigorta + motor kalkış akımına uygun DC kesme elemanı + galvanik izole normalde açık kuru tetik kontağı gerekir. YL-314-C-T yalnız bobin ve DC motor/inrush değerleri doğrulanırsa adaydır. Yalnız Safety Gate + Arduino interlock sonrası enable edilir; patlayıcı yasak |

## 6. Teknoloji Seçimi

Şartname belirli bir programlama dili veya yapay zekâ modeli zorunlu kılmaz. Bu repo için teknik yön şu şekilde güncellenmiştir:

- **Simülatör UI:** React + Vite + TypeScript (`frontend/`).
- **Gerçek operatör paneli:** React/Vite içinde ayrı sayfa + Backend API. Yazılım yüzeyi backend-otoriter `MissionFlow`, aşama/tur seçimi, SSE/REST state eşitlemesi, gerçek track kimliği, MJPEG kamera, TFA50-L 1D menzil, taret kalibrasyonu, balistik holdover, deadman'li manuel pan/tilt niyeti, FireIntent, bakım, Safety/health ve kanıt/replay için tamamlanmıştır. `npm run desktop` launcher’ı backend API + UI + desktop app-window akışını Linux/macOS/Windows geliştirme makinelerinde tek komutla başlatır; gerçek paketleme hedefi saha bilgisayarına göre AppImage/kiosk veya `.exe` olarak ayrıca kilitlenmelidir.
- **1D LiDAR teşhis stratejisi:** TFA50-L bir tarama/point-cloud sensörü değildir. Görev paneli boresight menzilini canlı sayısal değer olarak gösterir; seri port, firmware, health, hizalama ve 5/10/15 m kalibrasyon ayrıntıları bakım/telemetri yüzeyinde kalır.
- **Hedef runtime:** Raspberry Pi 5 üzerinde doğrudan 64-bit Raspberry Pi OS + `systemd`; hedefte VM yok. Ayrıntı: ADR-001.
- **Kurulum/paketleme:** Backend `pyproject.toml` ile kurulur; exact Python
  kilitleri `requirements/`, doğrulanan çalışma profilleri `config/runtime/`,
  Pi manifesti ve servisler `deploy/` altındadır. Frontend Pi’de Node.js yerine
  önceden üretilmiş `dist` + bağımlılıksız static/proxy server ile çalışır.
- **Backend / görev çekirdeği:** Python 3.x; tek sahipli reducer thread,
  sürümlü immutable mesajlar ve bounded queue. Tam Rust yeniden yazımı yerine
  ölçülebilir, test edilen sahiplik sınırı kullanılır.
- **Backend API dry-run geçişi:** bağımlılıksız dry-run HTTP iskeleti
  (`gokkalkan_backend.operator_http_server`); canlı donanım çıkışı üretmez.
  Mutasyonlar Mission Core kuyruğuna girer; `GET /state/stream` SSE snapshot,
  `GET /commands/{id}` komut izleme, SQLite WAL + segmentli JSONL telemetri, `/readiness`,
  `/telemetry/export` ve `/replay` kanıt yüzeyleri uygulanmıştır.
- **Görüntü işleme:** OpenCV motion/renk adayları hızlı yol olarak korunur;
  doğruluk yolu `2304×1296` main görüntüde SAHI tabanlı sekiz örtüşmeli
  `768×768` tile araması ve kare track ROI'sidir. Aynı sliced veri/split üzerinde
  YOLOv8s birincil doğruluk adayı, YOLOv8n throughput fallback'i olarak
  karşılaştırılır; doğrulanmış kazanan HEF model AI HAT+ 26 TOPS üzerinde
  çalıştırılır. Motion/HSV/model sonucunun Safety Gate veya atış yetkisi yoktur.
- **Kamera:** Tek Raspberry Pi Camera Module 3 Standard, Picamera2, üretici
  nominali 66° yatay FoV; intrinsics imalat sonrası kalibrasyonla değiştirilir.
- **AI hızlandırıcı:** Raspberry Pi AI HAT+ 26 TOPS / Hailo-8. Donanım yoksa Pi
  perception heartbeat'i fail-closed sağlıksız olur; model ağırlıkları repoya
  eklenmez.
- **Donanım haberleşmesi:** Aktif Pi–Arduino yolu USB seri satır protokolüdür. Backend `ArduinoUnoMotorAdapter`, STEP/JOG/STOP komutlarını güvenli sınırlar sonrasında gönderir. LIVE yalnız kararlı `/dev/serial/by-id/...`, fiziksel interlock/readiness ve HIL kabulüyle açılır. COBS/CAN/Pico codec'leri legacy regresyon bağlamında tutulur. TFA50-L pySerial/UART kullanmaya devam eder.
- **Test:** pytest + frontend için Vitest/Playwright.
- **Log formatı:** Tek writer thread/process sınırı, SQLite WAL event index’i,
  segmentli JSONL export, session manifest, ortak monotonic zaman tabanlı medya
  index’i, güvenli replay ve hash’li kanıt paketi uygulanmıştır. Düşük disk,
  retention veya eksik medya session’ı açıkça geçersiz kanıt yapar. Gerçek saha
  quota değerleri ile video segment süreleri depolama ve kamera ölçümlerinden
  sonra kalibre edilmelidir.

ROS 2 ve tam Rust yeniden yazımı bu fazın parçası değildir. Yeniden değerlendirme
eşikleri ADR-001’de tanımlıdır. Hailo-8 donanım kararı kesindir; kullanılacak
detector/classifier mimarisi ancak veri seti precision/recall, gecikme ve FPS
ölçümleriyle kabul edilir.

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
