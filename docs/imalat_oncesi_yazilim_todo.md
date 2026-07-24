# Gökkalkan İmalat Öncesi Yazılım TODO

> Amaç: Mekanik imalat tamamlandığında yazılımı ilk kez bir araya getirmek yerine; görev mantığı, güvenlik, firmware, donanım haberleşmesi, algı, telemetri, operatör arayüzü ve hata senaryolarını imalat öncesinde simülasyon ve düşük güçlü HIL masasında doğrulamak.

## Kullanım

- Bu dosya imalat öncesi yazılım işlerinin kanonik takip listesidir.
- İşler yukarıdan aşağıya bağımlılık sırasıyla ele alınmalıdır.
- Bir görev tamamlandığında kutusu işaretlenmeli ve altına PR/commit/test kanıtı eklenmelidir.
- Donanım üzerinde doğrulanmayan davranış için “tamamlandı” değil, “mock/HIL üzerinde doğrulandı” ifadesi kullanılmalıdır.
- Her iş mümkünse `WP-01`–`WP-05` etiketlerinden biriyle ilişkilendirilmelidir.
- Büyük görevler ayrı issue’lara bölünebilir; bu dosyadaki kimlikler issue başlığında korunmalıdır.

## Değiştirilmeyecek temel kararlar

- Hedef bilgisayar: Raspberry Pi 5 üzerinde doğrudan 64-bit Raspberry Pi OS; hedefte sanal makine yok.
- Bu fazda ROS 2 yok. Ölçülmüş ve belgelenmiş bir ihtiyaç oluşmadan ROS workspace eklenmeyecek.
- Tam Rust yeniden yazımı yok. Backend ve algı Python, arayüz React/TypeScript, Pico firmware C/C++ kalacak.
- Safety Gate’in sahibi backend’dir. UI yalnız yüksek seviyeli komut niyeti gönderir.
- Gerçek zamanlı E-Stop/watchdog güvenliği Linux thread’lerine değil Pico firmware ve fiziksel emniyet zincirine dayanır.
- Görev state’inin tek sahibi olacak; HTTP, CAN ve sensör thread/process’leri ortak state’i doğrudan değiştirmeyecek.
- Replay modu fiziksel çıkış adapter’ını yükleyemeyecek.
- Ana menzil sensörü adayı **Benewake TFA50-L tek nokta LiDAR**’dır. Sensör, yaw ile dönen fakat silah pitch hareketine katılmayan iki yan plaka arasındaki merkezî köprü/profil üzerine yerleştirilecek; merkezî düşey kızak/direk aynı kinematiği sağladığı sürece mekanik alternatiftir.
- LiDAR yüksekliği yalnız kurulum/kalibrasyon sırasında elle ayarlanacak ve mekanik olarak kilitlenecek; bu köprü/kızak için motor, eksen veya çalışma zamanı hareket komutu yazılmayacak. Yükseklik değişikliği mevcut kalibrasyonu geçersiz kılacak.
- TFA50-L yazılımı adapter sınırının arkasında kalacak. 2D tarayıcı ancak gerçek hedef bench testinde yaw ile eşlenmiş tek nokta ölçümünün güvenilir olmadığı kanıtlanırsa fallback olarak yeniden değerlendirilecek.
- Şartname ile repo belgeleri çelişirse şartname esas alınır.

## LiDAR mekanik referansları

- `gokkalkan_izometrik_cizim.png`: Taretin temel izometrik görünümü; dış yan plakalar yaw tablasıyla döner, iç mekanizma pitch ekseninde hareket eder.
- `gokkalkan_izometrik_cizim_uzerinde_lidar_konumu.png`: Öncelikli çözüm; iki pitch-sabit yan plakayı birleştiren, yüksekliği elle ayarlanıp kilitlenen köprü/profil ve merkezde TFA50-L.
- `gokkalkan_izometrik_cizim_lidar_konumu_2.png`: Alternatif çözüm; yaw tablasına bağlı, merkezî ve elle yükseltilip alçaltılabilen kızak/direk.
- Her iki çözümde de LiDAR taret yaw açısını takip eder, silahın yukarı-aşağı pitch hareketini takip etmez. Böylece silah hedefin üstüne nişan alırken menzil huzmesi hedef yüksekliğinde kalabilir.

## Her görev için tamamlanma standardı

Bir kutu ancak aşağıdakiler sağlandığında tamamlanır:

1. Davranış testle veya tekrarlanabilir komutla doğrulanmıştır.
2. Güvenlik etkisi değerlendirilmiştir; hata yolu fail-safe davranır.
3. Yeni config/protokol/schema belgelenmiştir.
4. İlgili log/telemetri olayı üretilmektedir.
5. Lint/typecheck/test çıktısı okunmuş ve başarısızlık bırakılmamıştır.
6. Commit mesajı repo Lore Commit Protocol biçimine uygundur.

---

# Faz 0 — Canlı çıkışı güvenli biçimde dondur

**Kapı:** Bu faz bitmeden gerçek motor veya imha çıkışı bağlanmaz.

- [x] **SAFE-001 — Client kaynaklı `dryRun` bypass’ını kapat** `[WP-04]`
  - `dryRun`, `physicalOutputEnabled` ve canlı arm kararı yalnız backend konfigürasyonundan gelmeli.
  - İstek payload’ı güvenlik koşullarını gevşetememeli.
  - Kabul: canlı servis + payload `dryRun=true` fiziksel adapter çağrısı üretmez.
  - Kanıt: `tests/test_operator_api.py::OperatorServiceTest::test_live_service_ignores_client_dry_run_override`; backend çalışma modu `OperatorService.dry_run` üzerinden sunucu-otoritatif hâle getirildi.

- [ ] **SAFE-002 — Fiziksel adapter’ı varsayılan kapalı yap** `[WP-04]`
  - Açıkça seçilmiş backend live config, fiziksel interlock ve readiness olmadan gerçek adapter yüklenmemeli.
  - Başlangıç logu çalışma modunu `SIM`, `HIL` veya `LIVE` olarak açıkça yazmalı.

- [ ] **SAFE-003 — Kritik bypass regresyon testlerini ekle** `[WP-04]`
  - UI/config/payload kombinasyonları denenmeli.
  - Test spy adapter ile “sıfır fiziksel çağrı” invariant’ını kanıtlamalı.

**Faz kanıtı:** Güvenilmeyen istemci girdilerinin hiçbir kombinasyonu canlı çıkışı etkinleştiremiyor.

---

# Faz 1 — Kaynakları ve arayüz kararlarını sabitle

- [ ] **DOC-001 — Güncel şartname yolunu ve sürümünü kanonikleştir**
  - README, AGENTS, teknik dokümanlar ve rapor bağlantıları mevcut PDF adına yönelmeli.
  - Aranabilir metin çıktısı üretilmeli; PDF son otorite olarak kalmalı.

- [ ] **DOC-002 — Takvim ve video yükümlülüklerini senkronize et**
  - `TARIHLER.md`, rapor notları ve görev traceability matrisi aynı tarihleri kullanmalı.
  - Video yetenekleri şartnamedeki sırayla test kimliklerine bağlanmalı.

- [ ] **ADR-001 — Hedef çalışma ortamı ADR’ını yaz**
  - Raspberry Pi OS, Python/React/Pico C++, `systemd`, no-ROS2 ve no-full-Rust kararları kaydedilmeli.
  - ROS 2’yi yeniden değerlendirme koşulları belirtilmeli.

- [ ] **ADR-002 — MCU ve saha haberleşmesini kesinleştir**
  - Pico/Arduino çelişkisi kapatılmalı.
  - CAN veya CAN-FD tek karar olarak seçilmeli.
  - Bitrate, frame biçimi, transceiver ve hata davranışı tanımlanmalı.

- [ ] **ADR-003 — Kamera/LiDAR yerleşim kararını kaydet**
  - Yukarıdaki üç CAD görseli karar kanıtı olarak bağlanmalı.
  - Sabit geniş kamera, nişan kamerası, yaw ekseni, silah pitch ekseni ve TFA50-L referans koordinatları tanımlanmalı.
  - Köprü/profil öncelikli, merkezî kızak/direk mekanik alternatif olarak kaydedilmeli; ikisinin de yaw’ı izlediği fakat silah pitch’ini izlemediği belirtilmeli.
  - TFA50-L’nin elle ayarlanan yükseklik aralığı, merkezleme toleransı, kilitleme yöntemi ve kablo güzergâhı mekanik ekiple kesinleştirilmeli.
  - TFA50-L gerçek hedef testini geçemezse fallback sırası: optik/algoritmik iyileştirme → ikinci tek nokta sensör değerlendirmesi → 2D tarayıcı değerlendirmesi.

- [ ] **DOC-003 — Şartname traceability matrisini oluştur**
  - Her zorunlu yetenek için requirement ID, modül, test, telemetri olayı ve video kanıtı alanları bulunmalı.

**Faz kanıtı:** Aktif belgelerde OS, MCU, protokol, sensör rolü, kamera sayısı ve tarih çelişkisi kalmıyor.

---

# Faz 2 — Tekrarlanabilir geliştirme ve Pi çalışma ortamı

- [ ] **ENV-001 — Backend’i gerçek Python paketi hâline getir**
  - `pyproject.toml`, paket metadata’sı, test config’i ve giriş noktaları eklenmeli.
  - Geçici `PYTHONPATH` gereksinimi kaldırılmalı.

- [ ] **ENV-002 — Python bağımlılıklarını eksiksiz ve kilitli tanımla**
  - Backend, test ve perception bağımlılıkları ayrıştırılmalı.
  - OpenCV, NumPy ve hedef Pi’de kullanılan kamera bağımlılıkları belgelenmeli.
  - Büyük model dosyaları repoya eklenmemeli.

- [ ] **ENV-003 — Raspberry Pi kurulum manifestini oluştur**
  - OS sürümü, sistem paketleri, kullanıcı/grup izinleri, CAN ve kamera ayarları yazılmalı.
  - Temiz imaj kurulumunun tekrarlanabilir kontrolü bulunmalı.

- [ ] **ENV-004 — Runtime config şeması oluştur**
  - `SIM`, `HIL`, `LIVE` profilleri açıkça ayrılmalı.
  - Soft limit, timeout, port, kayıt kotası ve sensör eşikleri doğrulanmalı.
  - Eksik güvenlik config’i live başlangıcını engellemeli.

- [ ] **ENV-005 — `systemd` servislerini ekle**
  - Backend/Mission Core, perception, UI/static server ve telemetry recorder servisleri hazırlanmalı.
  - Restart politikası, dependency sırası, graceful shutdown ve log yönlendirmesi tanımlanmalı.

- [ ] **ENV-006 — Tek komutlu geliştirme ve dry-run başlatma ekle**
  - Mevcut frontend scriptleri korunmalı.
  - Backend + simulator + UI health kontrolü tek akışta doğrulanmalı.

- [ ] **ENV-007 — `gokkalkan doctor` tanılama komutunu ekle**
  - Kamera, disk, saat, config, API, Pico/CAN ve kayıt dizini durumunu raporlamalı.
  - Tanılama fiziksel çıkış üretememeli.

**Faz kanıtı:** Temiz bir Pi imajı ve temiz bir Linux CI ortamı belgelenmiş adımlarla kurulup dry-run çalıştırılabiliyor.

---

# Faz 3 — Tek sahipli görev çekirdeği ve mesaj sözleşmeleri

- [ ] **CORE-001 — Mission Core state modelini ayır** `[WP-01][WP-02][WP-03]`
  - Mod, aşama, tur, hedef, arm, bakım ve fault state’leri tek modelde tanımlanmalı.
  - State değişikliği yalnız Mission Core tarafından yapılmalı.

- [ ] **CORE-002 — `CommandEnvelope` ve `EventEnvelope` şemalarını tanımla**
  - En az `run_id`, `event_id`, `sequence`, UTC/monotonic zaman, source, schema version, command/causation ID ve target/track ID alanları bulunmalı.
  - Şema sürümü ve geriye uyumluluk politikası yazılmalı.

- [ ] **CORE-003 — HTTP komutlarını kuyruğa taşı**
  - HTTP handler’ları paylaşılan state’i veya donanım adapter’ını doğrudan çağırmamalı.
  - Kabul/red cevabı command ID ile izlenebilmeli.

- [ ] **CORE-004 — CAN/sensör thread’lerini event köprüsüne taşı**
  - Thread’ler state değiştirmemeli.
  - `loop.call_soon_threadsafe` veya eşdeğer güvenli köprü kullanılmalı.

- [ ] **CORE-005 — CPU-ağır perception’ı ayrı process yap**
  - Process sınırı, health heartbeat’i, queue backpressure ve kapanış davranışı tanımlanmalı.
  - Perception çökmesi Mission Core’u çökertmemeli; angajman kapanmalı.

- [ ] **CORE-006 — Immutable state snapshot yayını ekle**
  - UI ve kayıt katmanı tutarlı snapshot okumalı.
  - Polling yerine SSE veya WebSocket state stream tercih edilmeli.

- [ ] **CORE-007 — Concurrency ve ordering testlerini ekle**
  - Aynı anda komut, CAN ve sensör olaylarıyla sequence bütünlüğü test edilmeli.
  - Duplicate/out-of-order olaylar deterministik işlenmeli veya reddedilmeli.

**Faz kanıtı:** Aynı anda yoğun komut/sensör yükünde state ve event sırası deterministik kalıyor.

---

# Faz 4 — Safety Gate ve canlı arm zinciri

- [ ] **SAFE-010 — Safety kararını saf ve merkezi bir fonksiyon yap** `[WP-04]`
  - Hareket ve imha kararları aynı sunucu-otoriter kapıdan geçmeli.
  - Karar `allowed`, reason code ve kullanılan input snapshot’ını üretmeli.

- [ ] **SAFE-011 — Fail-closed hata politikasını uygula** `[WP-04]`
  - Exception, eksik config, stale sensör, geçersiz paket ve health kaybı izin üretmemeli.
  - Soft-limit kontrolü hata aldığında hareketi serbest bırakmamalı.

- [ ] **SAFE-012 — Bütün sağlık girdilerini Safety Gate’e bağla** `[WP-04]`
  - E-Stop, Pico heartbeat, CAN, encoder, kamera, track, LiDAR, disk/kayıt ve runtime mode.

- [ ] **SAFE-013 — Hareket ve imha yasak bölgelerini backend’de uygula** `[WP-04]`
  - Bölgeler sürümlü config olmalı.
  - Sınır, dış bölge ve geçersiz geometri testleri bulunmalı.

- [ ] **SAFE-014 — Live arm state machine’i oluştur** `[WP-04]`
  - Fiziksel interlock, backend readiness, operatör hold-to-arm ve kısa timeout birlikte gerekli olmalı.
  - Arm bağlantı/heartbeat kaybında otomatik düşmeli.

- [ ] **SAFE-015 — E-Stop reset zincirini güvenli yap** `[WP-04]`
  - HTTP çağrısı tek başına fiziksel E-Stop’u temizleyememeli.
  - Fiziksel bırakma, Pico safe durumu ve kontrollü reset birlikte gerekli olmalı.

- [ ] **SAFE-016 — API erişim sınırlarını daralt** `[WP-04]`
  - Saha profili localhost/izinli arayüzle sınırlanmalı.
  - State değiştiren komutlar session/token ve audit identity taşımalı.
  - CORS wildcard live profilde bulunmamalı.

- [ ] **SAFE-017 — Safety invariant test paketini oluştur** `[WP-04]`
  - E-Stop, stale input, heartbeat loss, invalid zone, client bypass ve restart senaryoları fiziksel çağrı üretmemeli.

**Faz kanıtı:** Fault-injection matrisindeki hiçbir hata, fiziksel adapter’a izinli komut ulaştıramıyor.

---

# Faz 5 — Pico firmware ve CAN protokolü

- [ ] **FW-001 — Pico SDK firmware yapısını ekle** `[WP-04]`
  - Build, flash ve host-side test yönergeleri bulunmalı.
  - Firmware sürümü backend health çıktısında görünmeli.

- [ ] **FW-002 — Pico güvenlik durum makinesini uygula** `[WP-04]`
  - `BOOT → SAFE → READY → ARMED → FIRING/FAULT`.
  - Reset ve boot çıkışları enerjisiz/güvenli başlamalı.

- [ ] **FW-003 — Donanımsal E-Stop ve watchdog davranışını uygula** `[WP-04]`
  - Linux’tan bağımsız çıkış kesme.
  - Heartbeat kaybı ve Pico fault durumunda motor/imha hattını kapatma.

- [ ] **FW-004 — Sürümlü CAN ICD oluştur**
  - Command/status/fault frame’leri, ölçekler, endian, bitrate ve timeout tanımlanmalı.
  - Sequence, CRC/checksum, ACK/NACK ve command ID bulunmalı.

- [ ] **FW-005 — Backend CAN codec’ini ICD ile uyumlu yap**
  - Status checksum doğrulanmalı.
  - Duplicate, out-of-order, corrupt ve timeout paketleri reddedilmeli.

- [ ] **FW-006 — Firmware/simulator contract testlerini ortaklaştır**
  - Aynı input vektörleri aynı state transition ve reason code’ları üretmeli.
  - Simülatör E-Stop ve fault sırasında komutları gerçek firmware gibi reddetmeli.

- [ ] **FW-007 — Encoder ve limit geri bildirimlerini bağla**
  - Yön, sıfır, overflow, kopukluk ve beklenen/gerçek açı farkı fault’a dönüşmeli.

**Faz kanıtı:** Reset, heartbeat kaybı, bozuk paket ve enkoder hatası güvenli stop ile sonuçlanıyor.

---

# Faz 6 — Donanım simülasyonu ve dijital ikiz

- [ ] **SIM-001 — MCU simülatörünü gerçek protokol davranışına yükselt**
  - State machine, ACK/NACK, gecikme, timeout ve fault injection desteklemeli.

- [ ] **SIM-002 — Pan/tilt dinamik mock’u ekle**
  - Hız, ivme, soft limit, basit backlash ve encoder feedback modellenmeli.
  - Parametreler resmî donanım ölçümü gibi sunulmamalı.

- [ ] **SIM-003 — Sensör fixture ve replay adapter’ları ekle**
  - Kamera track, TFA50-L tek nokta menzil/no-detection, bozuk UART frame, stale/dropout ve zaman kayması senaryoları üretilebilmeli.

- [ ] **SIM-004 — Güvenli imha çıkışı mock’u ekle**
  - Gerçek çıkış yerine event/lamba/yapay yük davranışı.
  - Fire command yalnız Safety Gate kararından sonra kabul edilmeli.

- [ ] **SIM-005 — Senaryo çalıştırıcısı oluştur**
  - Aşama 1/2/3, E-Stop, bağlantı kaybı ve yanlış hedef senaryoları komut satırından tekrarlanabilmeli.

**Faz kanıtı:** Gerçek donanım olmadan kritik görev ve hata akışları deterministik biçimde tekrar edilebiliyor.

---

# Faz 7 — Telemetri, kayıt, kanıt ve replay

- [ ] **TEL-001 — Tek-yazarlı telemetry pipeline kur** `[WP-05]`
  - Producer’lar kuyruğa yazar; yalnız recorder kalıcı depoya yazar.
  - Event ID ve sequence process/thread güvenli olmalı.

- [ ] **TEL-002 — SQLite WAL event index’i ekle** `[WP-05]`
  - JSONL taşınabilir export olarak korunabilir.
  - `/state` veya health istekleri bütün logu baştan okumamalı.

- [ ] **TEL-003 — Session manifest oluştur** `[WP-05]`
  - Git SHA, build ID, OS/paket sürümleri, config/calibration/BOM hash’leri, operatör ve dosya hash’leri kaydedilmeli.

- [ ] **TEL-004 — Kamera ve ham sensör kayıtlarını session’a bağla** `[WP-05]`
  - Segmentli video/frame index’i, LiDAR paketleri ve CAN frame’leri ortak zaman tabanında ilişkilendirilmeli.

- [ ] **TEL-005 — Disk yönetimi ve bozulma davranışı ekle** `[WP-05]`
  - Rotation, kota, retention, düşük disk alarmı ve graceful degradation.
  - Eksik/bozuk session açıkça `invalid evidence` olmalı.

- [ ] **TEL-006 — Güvenli replay motorunu oluştur** `[WP-05]`
  - Replay fiziksel adapter yükleyememeli.
  - Aynı session aynı karar ve event sırasını üretmeli.

- [ ] **TEL-007 — Kanıt paketi üreticisi ekle** `[WP-05]`
  - Şartname yeteneği, video zaman aralığı, ilgili event’ler ve hash manifest birlikte export edilmeli.

- [ ] **TEL-008 — Doğrulama CLI’larını ekle** `[WP-05]`
  - `gokkalkan replay verify <session>`
  - `gokkalkan evidence verify <session>`

**Faz kanıtı:** Bir komut; kamera karesi, Safety kararı, CAN ACK’i ve sonuç olayıyla birlikte yeniden oynatılabiliyor.

---

# Faz 8 — Görev state machine ve operatör paneli

- [ ] **MIS-001 — Aşama 1 state machine’ini tamamla** `[WP-01]`
  - Hedef sırası, 300 saniye, manuel yönelim, deadman ve kullanıcı komutlu FireIntent.

- [ ] **MIS-002 — Aşama 2 state machine’ini tamamla** `[WP-02]`
  - Gerçek track’lerle otonom tespit/takip, hedef önceliği ve tur ilerlemesi.
  - Hedef tipi sınıflandırması zorunlu varsayılmamalı.

- [ ] **MIS-003 — Aşama 3 state machine’ini tamamla** `[WP-03]`
  - Dost/düşman, hedef tipi, ölçülmüş menzil ve hedef tipine bağlı menzil kapısı.

- [ ] **MIS-004 — Bakım/stop/resume/E-Stop akışlarını tekleştir** `[WP-04]`
  - UI local state’i gerçek backend state’inden ayrışmamalı.
  - Bakım bütçesi ve geçiş nedenleri loglanmalı.

- [ ] **UI-001 — Manuel aim ve deadman kontrolünü bağla** `[WP-01]`
  - UI yalnız niyet gönderir; backend limit/Safety kararını verir.

- [ ] **UI-002 — Sentetik hedefleri gerçek track’lerle değiştir** `[WP-02][WP-03]`
  - UI hedef kimliği üretmemeli.
  - Hedef seçimi backend/perception kaynaklı track ID kullanmalı.

- [ ] **UI-003 — Health, arm ve blok nedenlerini görünür yap** `[WP-04]`
  - `SIM/HIL/LIVE`, physical output, E-Stop, Pico/CAN, kamera, LiDAR, kayıt ve Safety reason aynı yüzeyde anlaşılmalı.
  - Kritik anlam yalnız renkle verilmemeli.

- [ ] **UI-004 — Backend state stream’e geç**
  - UI optimistik güvenlik state’i üretmemeli.
  - Reconnect ve backend restart sonrası state yeniden senkronize olmalı.

- [ ] **UI-005 — Büyük panel sorumluluklarını böl**
  - Mevcut tasarım dilini koruyarak görev, güvenlik, donanım, sensör ve event yüzeyleri ayrıştırılmalı.
  - Yeni dependency eklemeden önce mevcut bileşen ve yardımcılar kullanılmalı.

**Faz kanıtı:** Aşama 1/2/3, bakım ve E-Stop akışları gerçek backend cevaplarıyla E2E testlerinden geçiyor.

---

# Faz 9 — Perception ve LiDAR/kamera füzyonu

- [ ] **PER-001 — Gerçek kamera adapter’ını ekle** `[WP-02]`
  - Picamera2 frame’i kamera timestamp’i ve receive monotonic zamanı ile üretilmeli.
  - Kamera yokluğu/crash/stale health’e yansımalı.

- [ ] **PER-002 — Sabit geniş kamera track hattını oluştur** `[WP-02]`
  - Hedef adayı, track ID, merkez, bbox, confidence, velocity ve freshness.

- [ ] **PER-003 — Nişan kamerası ince merkezleme hattını oluştur** `[WP-02]`
  - Seçili track ile taret koordinatı arasındaki hata üretimi kalibre edilmeli.

- [ ] **PER-004 — Track lifecycle kurallarını tamamla** `[WP-02]`
  - TTL, boş frame update’i, kayıp/yeniden edinim ve duplicate association.
  - Tek update sonrası bağlantı durumu sonsuza kadar true kalmamalı.

- [ ] **PER-005 — Gerçek hedef veri seti ve değerlendirme aracını oluştur** `[WP-02][WP-03]`
  - Renk/şekil/tip sınıflandırması gerçek görsellerle ölçülmeli.
  - Confusion matrix, precision/recall, FPS ve gecikme raporlanmalı.
  - Gereksiz YOLO/DeepSORT eklenmemeli; ihtiyaç ölçümle gösterilmeli.

- [ ] **LID-001 — TFA50-L UART protokolünü ve adapter’ını tamamla** `[WP-03]`
  - Protokol kaynağı: [TFA50-L Datasheet](https://www.e-kom.com/Datasheet/Benewake/TFA50-L_Datasheet.pdf); runtime vendor uygulamasına bağımlı olmamalı.
  - [x] Dört baytlık `0x5C` menzil frame’i, little-endian santimetre, checksum ve `0xFFFF` no-detection ayrıştırıcısı eklendi.
  - [x] Parçalı/noisy UART akışı için yeniden senkronize olan bağımlılıksız stream decoder ve unit testleri eklendi.
  - [ ] UART portu, baud rate ve örnekleme frekansı config’ten gelmeli; bağlantı kesilmesi/stale/yeniden bağlanma health’e yansımalı.
  - [ ] Alınan ham frame, receive monotonic timestamp, geçerli/geçersiz nedeni ve kabul edilen metre değeri telemetriye yazılmalı.
  - [ ] Sensör seri numarası/firmware bilgisi ve etkin config session manifestine kaydedilmeli.

- [ ] **LID-002 — Mekanik hizalama ve kalibrasyon iş akışını ekle** `[WP-03]`
  - Config: `mount_height_m`, `yaw_offset_deg`, `pitch_offset_deg`, kabul edilen hedef düşey bandı, kalibrasyon ID/hash/tarih/operatör.
  - Köprü/kızak elle değiştirildikten sonra eski kalibrasyon otomatik olarak “doğrulanmamış” sayılmalı; live arm kapanmalı.
  - Görünür hizalama noktası yalnız güvenli kurulum prosedüründe kullanılmalı; çalışma zamanı algoritmasının zorunlu girdisi olmamalı.
  - 5/10/15 m sabit hedef ölçümleriyle ofset, tekrar edilebilirlik ve no-detection oranı kaydedilmeli.

- [ ] **LID-003 — Yaw-to-track menzil eşlemesini uygula** `[WP-03]`
  - LiDAR yaw açısı, taret encoder yaw’ı ve kalibre edilmiş `yaw_offset_deg` ile hesaplanmalı; silah pitch’i bu ölçüm doğrultusuna eklenmemeli.
  - Yalnız seçili kamera track’inin bearing’i LiDAR doğrultu toleransı içindeyken ölçüm o track’e atanmalı.
  - Timestamp yakınlığı, art arda örnek sayısı, menzil değişim hızı ve aykırı değer filtresi kullanılmalı.
  - TFA50-L menzil frame’i kalite/sinyal gücü taşımadığı için sahte bir “quality” alanı üretilmemeli; kabul/ret nedeni açıkça kaydedilmeli.

- [ ] **LID-004 — Menzil güvenlik kapısını gerçek sensöre bağla** `[WP-03][WP-04]`
  - Bbox alanından üretilen kaba menzil Safety Gate’te kullanılmamalı.
  - UART health, kalibrasyon geçerliliği, yaw hizası, track freshness ve kararlı menzil birlikte sağlanmadan imha izni açılmamalı.
  - Stale/checksum hatalı/no-detection/ambiguous LiDAR ölçümü fail-safe biçimde imha iznini kapatmalı.

- [ ] **LID-005 — TFA50-L mekanik ve optik kabul testini yap** `[WP-03]`
  - Köprü/profil ve merkezî kızak/direk seçenekleri titreşim, merkezleme, kablo hareketi ve kilit kaçırma açısından karşılaştırılmalı.
  - Silah pitch hareket ederken LiDAR’ın hedef yüksekliğinde kaldığı; yaw hareketinde ise seçili hedefi takip ettiği doğrulanmalı.
  - Gerçek yarışma hedef malzemesi/renkleriyle 5/10/15 m ve sağ/merkez/sol yaw noktalarında algılama oranı ölçülmeli.
  - Kabul kriteri karşılanmazsa ADR-003 fallback sırası işletilmeli; 2D LiDAR’a ölçümsüz geçilmemeli.

- [ ] **PER-006 — Kayıtlı veri replay eşitliğini doğrula**
  - Aynı kayıt canlı ve replay pipeline’da deterministik track/range kararları üretmeli.

**Faz kanıtı:** Stale veya belirsiz hedefe hareket/imha mümkün değil; menzil kararı gerçek sensör verisine dayanıyor.

---

# Faz 10 — CI, kalite kapıları ve saldırgan testler

- [ ] **QA-001 — Linux CI workflow ekle**
  - Python unit/integration, frontend unit, typecheck, build ve seçili E2E testleri.

- [ ] **QA-002 — Mevcut Playwright sapmasını düzelt**
  - Landing beklentisi güncel ürün kararıyla senkronize edilmeli.

- [ ] **QA-003 — Hardware adapter ve HTTP coverage’ını artır**
  - Özellikle error/timeout/invalid-input yolları kapsanmalı.

- [ ] **QA-004 — Safety test marker/gate ekle**
  - `pytest -m safety`; başarısızsa merge/release engellenmeli.

- [ ] **QA-005 — Protocol contract test gate’i ekle**
  - `pytest -m protocol`; firmware/simulator/backend vektörleri aynı olmalı.

- [ ] **QA-006 — Replay determinism test gate’i ekle**
  - `pytest -m replay`; fiziksel adapter import/yükleme denetimi içermeli.

- [ ] **QA-007 — Fault-injection senaryo paketi ekle**
  - Corrupt checksum, duplicate sequence, heartbeat loss, CAN disconnect, E-Stop, stale sensör, disk full, process restart ve UI/backend ayrışması.

- [ ] **QA-008 — Uzun süreli dry-run/soak testi ekle**
  - En az 30 dakika olay, video segmenti, disk kullanımı ve reconnect davranışı izlenmeli.

- [ ] **QA-009 — Performans bütçelerini tanımla ve ölç**
  - Kamera FPS, frame drop, algı gecikmesi, command-to-ACK, state stream ve recorder queue derinliği.
  - Ölçülmeden Rust/native/ROS 2 optimizasyonu yapılmamalı.

**Faz kanıtı:** P0/P1 güvenlik ve görev invariant’ları başarısızken merge veya live release üretilemiyor.

---

# Faz 11 — İmalat öncesi HIL yazılımı ve release adayı

- [ ] **HIL-001 — HIL profilini oluştur**
  - Pi + Pico + gerçek CAN + güvenli test motoru/encoder + E-Stop/röle + kamera/LiDAR + lamba/yapay yük.
  - HIL hiçbir koşulda gerçek imha elemanını kullanmamalı.

- [ ] **HIL-002 — HIL senaryo otomasyonunu ekle**
  - Boot/safe, Pico reset, heartbeat loss, CAN çıkarma, encoder ters/kopuk, kamera/LiDAR stale ve E-Stop.

- [ ] **HIL-003 — HIL sonuç raporunu otomatik üret**
  - Test kimliği, run ID, config/calibration hash, event özeti ve pass/fail.

- [ ] **HIL-004 — Süreç restart/session recovery doğrula**
  - Backend, perception ve recorder ayrı ayrı yeniden başlatıldığında güvenli state ve kayıt bütünlüğü korunmalı.

- [ ] **HIL-005 — Operatör panelinden bütün blok nedenlerini doğrula**
  - Her Safety reason görünür, anlaşılır ve telemetriyle aynı olmalı.

- [ ] **REL-001 — İmalat öncesi yazılım release adayı oluştur**
  - Sürümlü config, firmware, backend, UI, simulator, test fixture ve kurulum manifesti aynı release’e bağlanmalı.

- [ ] **REL-002 — Software Gate’i kapat**
  - Safety, görev, replay, UI, fault-injection ve clean-install testleri yeşil.

- [ ] **REL-003 — Sensor Gate’i kapat**
  - Kamera + TFA50-L çözümünün kayıtlı 5/10/15 m, sağ/merkez/sol yaw verileri ve adapter/replay yolu yeşil.

- [ ] **REL-004 — HIL Gate’i kapat**
  - Pico, CAN, encoder, E-Stop, röle ve yapay yük senaryoları yeşil.

**İmalat öncesi stop koşulu:** Software Gate, Sensor Gate ve HIL Gate birlikte geçmeden “imalat sonrası yalnız montaj ve kalibrasyon kalacak” denmez.

---

# Yazılım dışında kalan fakat yazılımı bloke eden kararlar

Bu maddeler yazılım görevi değildir; ilgili ekip tarafından sonuçlandırılmadan bazı adapter ve kalibrasyon işleri kapatılamaz:

- [ ] TFA50-L’nin 5/10/15 m gerçek hedef testi ve nihai satın alma kabulü.
- [ ] Köprü/profil veya merkezî kızak/direk seçimi; manuel yükseklik aralığı, ölçü skalası, merkezleme toleransı ve mekanik kilit.
- [ ] TFA50-L için 9–36 V besleme, UART elektrik seviyesi/izolasyonu, konnektör ve Raspberry Pi bağlantı devresi.
- [ ] CAN/CAN-FD transceiver ve bitrate kararı.
- [ ] Enkoder tam modeli, çözünürlüğü ve elektriksel arayüzü.
- [ ] Motor sürücüsü ve limit switch arayüzleri.
- [ ] E-Stop, emniyet rölesi/kontaktör ve reset devresi.
- [ ] İki kamera lens/FOV ve kablo yerleşimi.
- [ ] Taret yaw, silah pitch, kamera ve TFA50-L referans koordinatları/extrinsic ölçüleri ile hedeflerin düşey merkez bandı.
- [ ] İmha mekanizmasının menzil–pitch kalibrasyon yöntemi ve güvenli yapay yük arayüzü.

---

# Mevcut ve hedef doğrulama komutları

Mevcut repo komutları:

```bash
PYTHONPATH=backend/src python3 -m pytest tests -q
npm run typecheck
npm run test:unit
npm run build
npm run test:desktop
npm run test:competition
npm run desktop:check
```

Plan sonunda bulunması beklenen komutlar:

```bash
pytest -m safety
pytest -m protocol
pytest -m replay
pytest -m hil
gokkalkan doctor
gokkalkan replay verify <session>
gokkalkan evidence verify <session>
```

## Agent için son kontrol

Her çalışma turunun sonunda:

- [ ] Hangi TODO kimliklerinin kapandığını yaz.
- [ ] Değişen dosyaları listele.
- [ ] Çalıştırılan testleri ve sonuçlarını kaydet.
- [ ] Donanım olmadan doğrulanamayan noktaları açıkça belirt.
- [ ] Yeni risk veya çelişki bulduysan bu TODO’ya ekle.
- [ ] Güvenlik kapısını geçici olarak bypass eden test/debug kodu bırakma.
