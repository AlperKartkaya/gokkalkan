# Design

## Source of truth
- Status: Active
- Last refreshed: 2026-05-14
- Primary product surfaces: `frontend/` operatör konsolu; yarışma provası/sensör simülasyonu; telemetri ve video kanıt panelleri.
- Evidence reviewed:
  - `docs/sartname_v5.txt:272-281` — Görev Kabiliyeti Gösterimi Videosu yetenekleri; UI ve hedef sınıflandırma kanıtı.
  - `docs/sartname_v5.txt:430-463` — Manuel/Otonom Mod, Acil Durdur, bakım ve patlayıcı yasağı.
  - `docs/sartname_v5.txt:469-511` — Aşama 1 süre, puan, 5/10/15 m durağan hedef ve sıra cezası.
  - `docs/sartname_v5.txt:513-540` — Aşama 2, 4 tur, A→B parkur, üç kol, sınıflandırmasız sürü saldırısı.
  - `docs/sartname_v5.txt:543-580` — Aşama 3, 8 tur, 1 düşman/2 dost, menzil kapısı, kırmızı/mavi ok temsili ve hedef maketleri.
  - `docs/tech_stack.md:72-118` — backend güvenlik kapısı, hardware mock, perception/UI gereksinimleri ve test öncelikleri.
  - `frontend/src/App.tsx`, `frontend/src/realWorldSimulation.ts`, `frontend/src/safetyGate.ts`, `frontend/src/styles.css` — mevcut React/Vite mock operatör konsolu.

## Brand
- Personality: ciddi, görev-odaklı, askeri/teknik ama güvenlik uyarılarını saklamayan operatör konsolu.
- Trust signals: açık `MOCK`/simülasyon etiketleri, şartname kaynak notları, blok nedeni kodu + sade Türkçe açıklama, telemetri kaydı.
- Avoid: gerçek donanım bağlıymış gibi yanıltıcı metin; patlayıcı imha dili; sadece renge bağlı kritik anlam.

## Product goals
- Goals:
  - Aşama 1/2/3 yarışma akışını uçtan uca prova ettirmek.
  - Kamera, LiDAR mock, Radar mock ve füzyon izlerini gerçek saha verisi gibi ama açıkça mock olarak göstermek.
  - Atış/angajman görselini güvenlik kapısından sonra üretmek; bloklu durumda strike göstermemek.
  - KTR ve Görev Kabiliyeti Gösterimi Videosu için kanıt toplanmasını kolaylaştırmak.
- Non-goals:
  - Şartnamede verilmeyen kesin parkur ölçüsünü, radar/LiDAR modelini veya hedef hızını gerçekmiş gibi iddia etmek.
  - Gerçek motor veya gerçek imha mekanizması komutu göndermek.
- Success signals:
  - 1366×768’de yatay taşma yok; Acil Durdur, güvenlik nedeni, hedef/menzil ve telemetri görünür.
  - Unit/E2E testleri sensör kanalları, parkur, güvenlik kapısı ve mock strike davranışını doğrular.

## Personas and jobs
- Primary personas:
  - Operatör: Manuel/Otonom Mod geçişi, hedef seçimi, atış/angajman ve Acil Durdur farkındalığı.
  - Yazılım/algı geliştiricisi: sensör mock verisi, füzyon kararı, güvenlik kapısı ve telemetri kontrolü.
  - Rapor/video sorumlusu: şartname kabiliyet sırasına göre kanıt yakalama.
- User jobs:
  - Yarışma aşamasını seçmek, sistemi doğru moda almak, hedefleri izlemek, güvenli angajman yapmak.
  - Mock mekanik/saha parametreleriyle LiDAR/Radar/Kamera davranışını prova etmek.
- Key contexts of use: laboratuvar mock denemesi, KTR hazırlığı, video prova, gerçek donanım öncesi güvenlik kapısı doğrulaması.

## Information architecture
- Primary navigation: üst aşama seçici (`Aşama 1/2/3`), mod çubuğu (`Safe`, `Manuel`, `Otonom`, `Bakım`), global güvenlik şeridi.
- Core routes/screens: landing animasyonu; tek sayfa operatör konsolu; canlı viewport/parkur; görev paneli; video kanıtı; bakım/ayar/telemetri.
- Content hierarchy:
  1. Acil Durdur ve güvenlik kapısı.
  2. Görsel parkur + hedef izleri + sensör füzyonu.
  3. Aşama görevi ve atış/angajman kontrolleri.
  4. Kanıt/telemetri ve ayar bilgisi.

## Design principles
- Principle 1: Güvenlik kapısı görselden bağımsızdır; UI uyarısı tek başına izin değildir.
- Principle 2: Şartname gerçeği ve simülasyon varsayımı ayrıdır; varsayım görülebilir ve test edilebilir olmalıdır.
- Tradeoffs: Yoğun kokpit görünümü korunur, fakat kritik bilgiler metin + renk + konum ile tekrarlanır; küçük ekranlarda panel yoğunluğu yerine kaydırma kabul edilir.

## Visual language
- Color: koyu zemin; camgöbeği sensör/izleme; yeşil güvenli/hazır; kırmızı düşman/tehlike/Acil Durdur; amber uyarı/simülasyon varsayımı.
- Typography: yüksek kontrastlı sans-serif, etiketlerde büyük harf ve kısa mikrocopy.
- Spacing/layout rhythm: kokpit grid; üst güvenlik bandı; viewport ana odak; sağ panel destek bilgisi.
- Shape/radius/elevation: yuvarlatılmış paneller, ince neon sınırlar, kritik eylemlerde daha yüksek kontrast.
- Motion: radar sweep, hedef pulse ve strike animasyonu kısa; `prefers-reduced-motion` altında azaltılır.
- Imagery/iconography: parkur çizgileri Şekil 4/5’in temsili A→B/üç kol mantığını taşır; kırmızı/dost mavi anlamı metinle de açıklanır.

## Components
- Existing components to reuse: `SafetyStrip`, `CameraViewport`, `ManualPanel`, `AutonomousPanel`, `Stage3Intel`, `VideoEvidencePanel`, `SettingsPanel`, `TelemetryPanel`, `CommandQueue`.
- New/changed components: `CourseOverlay`, `SensorReadout`, mock `StrikeEffect` overlay, `competitionCourse.ts`, `generateSensorFusionFrame`.
- Variants and states:
  - Safe/Manuel/Otonom/Bakım/Kilitli modları.
  - Aşama 1 hedef sırası ve yanlış sıra riski.
  - Aşama 2 sınıflandırmasız sürü takibi.
  - Aşama 3 dost kilidi, düşman adayı ve menzil kapısı.
  - İzinli strike, yanlış sıra strike riski, bloklu komutta strike yok.
- Token/component ownership: renk ve grid tokenları `frontend/src/styles.css`; şartname sabitleri `missionConfig.ts`; mekanik/saha parametreleri `.env.example` + config dosyaları.

## Accessibility
- Target standard: pratik WCAG AA hedefi; kritik kontroller klavye/tık erişimine sahip olmalı.
- Keyboard/focus behavior: Aşama 1 pan/tilt ok tuşları, arming tık/basılı tutma; butonların disabled durumları gerçek güvenlik durumunu yansıtmalı.
- Contrast/readability: kırmızı/yeşil/amber durumları metin ve ikon/etiketle desteklenir.
- Screen-reader semantics: hedef kutuları `aria-label` ile id, tip, dost/düşman ve menzil bilgisini taşır.
- Reduced motion and sensory considerations: CSS `prefers-reduced-motion` animasyonları bastırır.

## Responsive behavior
- Supported breakpoints/devices: masaüstü 1366×768 ve üzeri birincil; 1180 altı tek sütun; 760 altı mobil/diagnostic görünüm.
- Layout adaptations: sağ paneller alt/iki sütuna düşer; viewport yüksekliği korunur; yatay taşma kabul edilmez.
- Touch/hover differences: kritik arming hem tık hem basılı tutma ile çalışır; hover bilgisi metin içinde de görünür.

## Interaction states
- Loading: landing boot checks ve progress.
- Empty: seçili hedef yoksa `İz yok`/`bekle` metni.
- Error: `BLOCKED_*` kodu + Türkçe blok nedeni.
- Success: `FIRE_MOCK`/`AUTO_ENGAGE`, görünür `STRIKE`, video kanıt checkbox ilerlemesi.
- Disabled: güvenlik veya mod uyumsuzluğunda ateş/angajman disabled.
- Offline/slow network, if applicable: `hardware_mock`/`real_camera_sim` kaynak etiketi; paket kaybı/gecikme telemetrisi.

## Content voice
- Tone: kısa, görev odaklı, Türkçe ve yarışma terimleriyle uyumlu.
- Terminology: `Aşama`, `Manuel Mod`, `Otonom Mod`, `Acil Durdur`, `Harekete Yasak Alan`, `Atışa Yasak Alan`, `Dost`, `Düşman`, `Menzil Kapısı`, `Görev Kabiliyeti`.
- Microcopy rules: Mock/temsilî varsayımları açıkça yaz; gerçek donanım veya kesin sensör iddiası kullanma.

## Implementation constraints
- Framework/styling system: React + Vite + TypeScript; CSS dosyası; yeni bağımlılık yok.
- Design-token constraints: mevcut koyu tema tokenları korunur.
- Performance constraints: sensör/parkur mockları deterministik ve hafif olmalı; animasyonlar CSS tabanlı olmalı.
- Compatibility constraints: şartname nihai otoritedir; radar/LiDAR modeli şartnamede olmadığı için simülasyon ayarları `.env` ile değiştirilebilir varsayımdır.
- Test/screenshot expectations: `npm run typecheck`, `npm run test`, `npm run build`, Playwright 1366×768 smoke ve görsel inceleme.

## Open questions
- [ ] Final hedef maketi renkleri ve görselleri açıklandığında `competitionCourse.ts` ve hedef kartları güncellenecek / owner: algı + UI / impact: sınıflandırma gerçekçiliği.
- [ ] Gerçek LiDAR/Radar donanımı seçilirse env mock parametreleri gerçek kalibrasyonla değiştirilecek / owner: mekanik-elektronik + backend / impact: sensör füzyonu doğruluğu.
- [ ] Şartname parkur ölçüleri sayısal yayınlanırsa normalize edilmiş A→B çizimi gerçek koordinata taşınacak / owner: UI + backend mock / impact: simülasyon doğruluğu.
