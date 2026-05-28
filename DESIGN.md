# Design

## Source of truth

- Status: Active
- Last refreshed: 2026-05-25
- Primary product surfaces:
  1. `frontend/` yarışma eğitim simülatörü.
  2. Planlanan gerçek operatör paneli.
  3. KTR/rapor arayüz ve mimari kanıtları.
- Evidence reviewed:
  - `docs/sartname_v5.txt:430-463` — Manuel/Otonom Mod, bakım, Acil Durdur ve patlayıcı yasağı.
  - `docs/sartname_v5.txt:513-540` — Aşama 2: 4 tur, üç kol, A→B hareket, sınıflandırma beklenmez.
  - `docs/sartname_v5.txt:543-568` — Aşama 3: 8 tur, 1 düşman + 2 dost, hedef tipine göre menzil kapısı.
  - `frontend/src/App.tsx`, `frontend/src/competitionSimulation.ts`, `frontend/src/competitionCourse.ts`, `frontend/src/safetyGate.ts` — mevcut React/Vite simülatör uygulaması.

## Brand

- Personality: ciddi, görev odaklı, yarışma eğitimi hissi veren ama güvenlik uyarılarını saklamayan teknik arayüz.
- Trust signals: şartname kaynak notları, açık simülasyon varsayımları, Türkçe blok nedenleri, olay/telemetri kaydı, görünür Acil Durdur durumu.
- Avoid: gerçek donanım bağlıymış gibi yanıltıcı simülasyon metni, patlayıcı imha dili, yalnız renge dayalı kritik anlam, debug panellerini ana ekrana yığmak.

## Product surfaces

### Yarışma eğitim simülatörü

Amaç, yarışmacının final fazı mantığını güvenli ortamda pratik etmesidir. İlk bakışta parkur ve mevcut aksiyon anlaşılmalıdır; ikinci bakışta kullanıcı ateş etmeli mi beklemeli mi sorusunun cevabını görmelidir.

- Aşama 1: durağan hedef pratiği; beklenen hedef sırası ve manuel FIRE eylemi merkezde.
- Aşama 2: otonom sürü saldırısı; üç kolda A→B hareket ve tur puanı görünür.
- Aşama 3: otonom dost/düşman + menzil; dost hedefler korunur, düşman hedef uygun menzilde vurgulanır.
- Onboarding: aşama bazlı atlanabilir; rehber açıkken hareket, sayaç ve skor durur.
- Debug/ham veri: ana ekranda değil, `Advanced / Debug` çekmecesinde.

### Gerçek operatör paneli

Amaç, final fazında backend/perception/hardware katmanlarına bağlanan güvenlik-kritik kontrol istasyonu oluşturmaktır. Simülatörden farklı olarak canlı kamera/sensör, gerçek mod durumu, gerçek Safety Gate ve donanım geri bildirimi kullanmalıdır.

- UI yalnızca `FireIntent`, `ModeRequest`, `ManualAimCommand` gibi yüksek seviye niyetler gönderir.
- Backend Safety Gate onayı olmadan hareket veya imha hattı komutu üretilmez.
- Acil Durdur, yasak alan, bağlantı sağlığı ve hakem/operatör kilitleri UI’dan bağımsız güvenlik katmanında uygulanır.
- Simülasyon ve gerçek panel aynı tasarım dilini paylaşabilir; canlı panelde simülasyon varsayımı veya eğitim puanı gerçek durumla karıştırılmamalıdır.

## Goals / non-goals

### Goals

- Şartnamedeki Aşama 1/2/3 akışını Türkçe ve yarışma diliyle anlatmak.
- Parkuru ana görsel öğe yapmak; hedefleri silüet, renk ve etiketle ayırt edilebilir kılmak.
- FIRE / Otonom Angajman durumunu kullanıcı açısından tereddütsüz yapmak.
- KTR için arayüz, yazılım mesajlaşması, sensör/veri aktarımı ve elektronik sınırları belgelendirmek.
- Gerçek operatör paneline geçişte simülatör UI bilgisini yeniden kullanılabilir ama safety-kritik kararları backend’e ait tutmak.

### Non-goals

- Şartnamede verilmeyen hedef hızı, parkur koordinatı, fiziksel hedef ölçüsü veya radar/LiDAR modelini resmi değer gibi göstermek.
- Simülatörden gerçek motor veya imha hattı komutu göndermek.
- UI’yı Safety Gate yerine geçirmek.

## Information architecture

- Landing:
  - Birincil eylem: `Simülasyona Başla`.
  - Planlanan ikincil eylem: `Operatör Paneli` / `Gerçek Sistem Paneli` butonu. İlk sürümde güvenli geliştirme etiketiyle backend bağlantı durumunu göstermeli.
- Simülatör ekranı:
  1. Kompakt yarışma başlığı: uygulama adı, aşama, mod, süre, tur, skor, güvenlik özeti.
  2. Ana parkur: 5/10/15 m bantları, üç kol, A→B yönü, hedef silüetleri, geçerli menzil vurgusu.
  3. Sağ rehber: mevcut görev, sonraki aksiyon, ateş durumu, neden, puan etkisi, aktif kural hatırlatması.
  4. Alt eylem çubuğu: FIRE / Otonom mantık, mod ve bakım kontrolleri.
  5. Gelişmiş/Debug çekmecesi: ham telemetri, config, güvenlik JSON’u.
- Gerçek operatör paneli ekranı:
  1. Canlı görev başlığı: mod, bağlantı, Safety Gate, E-stop, enerji/hardware sağlık özeti.
  2. Canlı görüntü/sensör alanı: kamera, hedef izi, radar/LiDAR izleri, takip kilidi.
  3. Finale Hazırlık göstergesi: `/readiness` raporu, hazır/kısmi/TBD/kilitli arayüz kartları ve sıradaki kritik entegrasyon adımı. Bu yüzde resmi yarışma uygunluk skoru olarak sunulmamalıdır.
  4. Komut paneli: mod geçişi, manuel pan/tilt, güvenli arming, FireIntent.
  5. Olay kayıtları ve kanıt çekmecesi: command_result, safety_block, track_update, hardware_fault, JSONL export/replay kanıtı.

## Visual language

- Color:
  - yeşil = güvenli/hazır/başarılı,
  - kırmızı = düşman/tehlike/ceza,
  - mavi = dost/bilgi,
  - sarı/turuncu = uyarı/geçerli aksiyon.
- Typography: önemli görev metinleri büyük ve okunaklı; debug bilgisi küçük ama gizlenebilir.
- Motion: hedef hareketi ve taret yönelimi sürekli olmalı; rehber highlight ve FIRE hazır durumu kısa pulse kullanabilir; `prefers-reduced-motion` altında azaltılır.
- Iconography: Balistik Füze, Helikopter, F16 ve Mini/Micro İHA için silüet temelli ikonlar; geometrik placeholder tek başına kullanılmaz.
- Parkur: özgün PDF görselini arka plan olarak gömmek yerine şartnamedeki A→B, üç kol ve menzil bandı yapısını yeniden çizen ölçeklenebilir görsel kullanılmalıdır.

## Components and states

- Simulator components to preserve/evolve:
  - `CompetitionHeader`, `CourseMap`, `GuidancePanel`, `StageChecklist`, `BottomActionBar`, `DebugDrawer`, `TutorialOverlay`.
- Real panel components to add later:
  - `OperatorPanelPage`, `LiveVideoPanel`, `SensorFusionPanel`, `SafetyAuthorityPanel`, `CommandConsole`, `HardwareStatusPanel`, `EventStream`.
- Critical states:
  - Safe/Manuel/Otonom/Bakım/Kilitli modları.
  - Aşama 1 hedef yok / doğru hedef / yanlış hedef ceza riski.
  - Aşama 2 tur içi otonom takip / hedef kaçtı / tur tamam.
  - Aşama 3 dost kilidi / düşman uygun menzil / geçersiz menzil.
  - E-stop aktif / hareket yasak / atış yasak / bağlantı hatası.

## Accessibility and operator usability

- Kritik kontroller klavye ve fareyle erişilebilir olmalı; disabled nedenleri metinle yazılmalıdır.
- Renkler ikon/etiket/metinle desteklenmelidir.
- FIRE veya canlı panel arming durumu tek bir renge değil metin + durum + blok gerekçesine dayanmalıdır.
- Ana yarışma ekranı 1366×768 ve 1920×1080 çözünürlüklerde yatay taşma üretmemelidir.

## Implementation constraints

- Current frontend: React + Vite + TypeScript; yeni bağımlılık eklemeden ilerlemek tercih edilir.
- Backend/perception gerçek sistemde Python ağırlıklı kalır; UI protokolü backend API üzerinden soyutlanır.
- Safety Gate backend ownership altındadır; UI güvenlik kararının kaynağı değildir.
- Simülasyon parametreleri `.env` ve config değerleriyle değiştirilebilir; resmi değer gibi belgelenmez.
- Gerçek operatör panelinde canlı donanım entegrasyonu dry-run/sim/live modlarıyla kademeli açılmalıdır.

## Open questions

- [ ] Radar/LiDAR donanımı ve haberleşme protokolü seçilecek / owner: elektronik + backend / impact: sensor adapter.
- [ ] MCU arayüzü UART, RS422, CAN veya Ethernet seçeneklerinden hangisi olacak netleşecek / owner: elektronik + backend / impact: Hardware Adapter.
- [ ] Gerçek operatör paneli React/Vite içinde yeni route olarak mı kalacak, yoksa native kiosk/PySide6 alternatifi mi istenecek / owner: yazılım / impact: UI runtime.
- [ ] Şartname veya hakem açıklaması kesin parkur ölçüsü/hız verirse simülasyon config’i güncellenecek / owner: UI + backend / impact: eğitim doğruluğu.
