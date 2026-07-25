# Hands-off Yarışma Senaryo Notları

Bu dosya artık ana simülasyon kaynağı değildir. Güncel eğitim simülatöründe yarışma mekaniği `frontend/src/competitionSimulation.ts`, parkur geometrisi `frontend/src/competitionCourse.ts` ve güvenlik/menzil kapısı `frontend/src/safetyGate.ts` üzerinden çalışır.

Buradaki eski `frontend/src/scenarios/` özetleri; demo, replay, QA veya video prova amaçlı **test fixture** olarak değerlendirilebilir. Ürün simülatörü “senaryoda yazdığı için hedef çıktı/vuruldu” mantığına dayanmamalıdır; hedefler aşama, tur, rota, menzil ve Safety Gate kurallarından türemelidir.

Şartname kaynakları:

- `docs/sartname_v1_3.txt:609-637; 491-504` — Manuel/Otonom Mod, Acil Durdur, bakım ve patlayıcı yasağı.
- `docs/sartname_v1_3.txt:475-480,578-585,615-617` — Aşama 1, 5/10/15 m ve Manuel Mod yükümlülükleri.
- `docs/sartname_v1_3.txt:589-595,617-620` — Aşama 2 otonom tespit/takip ve parkurdan çıkmadan imha yükümlülüğü.
- `docs/sartname_v1_3.txt:599-605,621-623` — Aşama 3 doğru hedefi doğru menzilde imha yükümlülüğü.
- `docs/Celikkubbe_Hava_Savunma_Sistemleri_Parkur_Cizim.pdf` — Tur, kol, A→B rota ve hedef yerleşimi ayrıntıları.

> Not: Şartname kesin parkur koordinatı, hedef hız profili veya radar/LiDAR donanım modeli vermediği için rota, hız ve sensör değerleri yapılandırılabilir simülasyon varsayımıdır. Bu değerler resmi veri gibi raporlanmamalıdır.

## Güncel canlı simülasyon kaynakları

- `frontend/src/competitionSimulation.ts`
  - Aşama 1/2/3 tur sayısı, puanlama, menzil tercihleri, hedef tipi dizileri, hız varsayımları.
  - Aşama 2 için resmi 4 tur + eğitim amaçlı genişletilebilir pratik tur sayısı.
  - Aşama 3 için 8 tur, düşman/dost dağılımı ve hedef tipine göre skor.
- `frontend/src/competitionCourse.ts`
  - Üç kol, A→B rota noktaları, sistem konumu, 5/10/15 m bantları ve bearing hesabı.
- `frontend/src/safetyGate.ts`
  - F16 10–15 m, Helikopter/Balistik Füze 5–15 m, Mini/Micro İHA 0–15 m menzil kapısı.
- `frontend/src/scenarios/`
  - Geçmiş hands-off replay/demo fixture’ları. Ana ürün davranışı yerine QA kanıtı veya video script provası için kullanılabilir.

## Fixture özeti

### Aşama 1 fixture

- Manuel Mod otomatik seçilir.
- Balistik Füze → Helikopter → F16 → Mini/Micro İHA sırası gösterilir.
- Yanlış sıra veya kaçan atış durumları demo amaçlı kayıtlanır.
- Bakım molası ve aşama tamamlanma olayı örneklenir.

### Aşama 2 fixture

- Otonom Mod seçilir.
- Dört resmi tur gösterilir; her turda üç kol doludur.
- Bazı turlarda bir hedefin kaçması veya bakım molası gibi durumlar video/demonstrasyon için örneklenir.
- Güncel canlı simülatörde pratik modu daha fazla tur gösterebilir; resmi sıkı mod 4 tur bilgisini korumalıdır.

### Aşama 3 fixture

- Otonom Mod seçilir.
- Sekiz turda bir düşman ve iki dost unsur örneklenir.
- F16, Helikopter, Balistik Füze ve Mini/Micro İHA için farklı menzil pencereleri gösterilir.
- Dost hedef kilidi, düşman kaçırma cezası ve bakım molası demo olayları olarak tutulur.

## Kullanım kuralı

Yeni geliştirmede önce `competitionSimulation.ts` / `competitionCourse.ts` / `safetyGate.ts` güncellenmelidir. `frontend/src/scenarios/` yalnızca replay veya QA fixture’ı gerekiyorsa güncellenir. Böylece ana uygulama yazılı bir hikâyeyi takip etmek yerine yarışma mekaniğini simüle eder.
