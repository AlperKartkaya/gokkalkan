# Gökkalkan Frontend UI/UX Durumu ve Sonraki Plan

Bu doküman, eski “debug operatör konsolu” iyileştirme planının güncel durumunu ve bundan sonraki UI yönünü özetler. Şartname (`docs/sartname_v5.txt`) nihai otoritedir.

## 1. Durum

Önceki UI/UX planındaki ana problem, neredeyse tüm debug ve sistem bilgilerini aynı anda gösteren kalabalık bir ekran olmasıydı. Güncel frontend artık yarışmacıya “TEKNOFEST final fazını çalışıyorum” hissi veren bir **yarışma eğitim simülatörü** olarak konumlanmıştır.

Güncel ana kaynaklar:

- `frontend/src/App.tsx` — landing, simülatör ekranı, aşama rehberi, parkur, sağ yarışma rehberi, alt eylem çubuğu, debug çekmecesi.
- `frontend/src/competitionSimulation.ts` — Aşama 1/2/3 kural ve simülasyon parametreleri.
- `frontend/src/competitionCourse.ts` — ölçeklenebilir parkur, 5/10/15 m bantları, A→B yolları.
- `frontend/src/missionConfig.ts` — aşama metinleri, hedef sıraları ve görev yapılandırması.
- `frontend/src/safetyGate.ts` — menzil kapısı ve güvenlik değerlendirmeleri.
- `frontend/tests/` — unit ve Playwright görev akışı testleri.

## 2. Tamamlanan tasarım yönü

- Parkur/map ana görsel öğe haline getirildi; debug panelleri gizlenebilir çekmeceye taşındı.
- Üst başlık; aşama, mod, süre, skor, tur ve güvenlik özetine indirildi.
- Sağ taraf “Competition Guidance” yerine Türkçe yarışma rehberi mantığıyla mevcut hedef, sonraki aksiyon, ateş durumu, puan etkisi ve kural hatırlatmasına odaklandı.
- FIRE / Otonom Angajman durumu alt eylem çubuğunda daha merkezi hale getirildi.
- Aşama 1 durağan hedef pratiği; beklenen hedef sırası, seçili hedef ve manuel ateş ilişkisiyle anlatıldı.
- Aşama 2 ve Aşama 3 için A→B hareket, üç kol, menzil bantları, yön okları ve hedef izleri daha görünür hale getirildi.
- Balistik Füze, Helikopter, F16 ve Mini/Micro İHA geometrik placeholder yerine silüet temelli sembollerle temsil edilmeye başlandı.
- Onboarding aşama bazlı atlanabilir hale geldi; bir aşamada atlanan rehber diğer aşamalarda tekrar gösterilebilir.

## 3. Simülatör ve gerçek panel ayrımı

Bu frontend iki farklı yüzeyi destekleyecek şekilde düşünülmelidir:

1. **Simülatör / eğitim ekranı**
   - Puan, onboarding, simülasyon varsayımı, eğitim amaçlı hedef davranışı içerir.
   - Gerçek donanım komutu göndermez.
2. **Gerçek operatör paneli**
   - Backend, perception, sensör ve hardware adapter durumlarını canlı izler.
   - UI yalnızca niyet gönderir; Safety Gate ve Hardware Adapter backend tarafındadır.
   - Simülasyon puanı veya eğitim senaryosu göstermez.

Gerçek panel tasarımı için ana yol haritası: `docs/operator_panel_interfaces_roadmap.md`.

## 4. Bundan sonraki öncelikli UI işleri

### Faz A — Landing’e gerçek panel girişi

- `Simülasyona Başla` butonunun altına `Operatör Paneli` butonu ekle.
- Backend bağlı değilse panel `Bağlantı yok / Dry-run` durumuyla açılmalı; canlı komut butonları kilitli kalmalı.
- Kullanıcı simülatör ile gerçek paneli karıştırmamalı.

### Faz B — Operatör paneli sayfa iskeleti

- Üst durum şeridi: backend, perception, sensör, Safety Gate, E-stop.
- Canlı görüntü/sensör paneli: kamera görüntüsü placeholder, hedef izleri, radar/LiDAR ölçümü placeholder.
- Komut paneli: mod seçimi, manuel pan/tilt, FireIntent, blok nedeni.
- Olay akışı: `SafetyState`, `CommandResult`, `TelemetryEvent`.

### Faz C — Backend API dry-run entegrasyonu

- UI gerçek backend endpoint’lerine bağlanır; backend yoksa komut gönderilemez.
- İlk entegrasyon `hardware_mock` ile yapılır.
- Dry-run modda fiziksel çıkış üretildiği iddia edilmez.

### Faz D — Canlı sensör ve hardware adapter entegrasyonu

- Perception ve radar/LiDAR adapter’ları `TrackState` / `SensorFrame` sözleşmeleriyle bağlanır.
- Hardware adapter `CommandResult` ve `HardwareFault` üretir.
- UI sadece backend’in yetkilendirdiği canlı durumu gösterir.

## 5. Güncel kabul ölçütleri

Simülatör tarafı için:

- `npm run typecheck`, `npm run build`, `npm run test` geçmeli.
- Aşama 1/2/3 akışları 1366×768 ve 1920×1080 çözünürlüklerde yatay taşma olmadan görülebilmeli.
- FIRE hazır/bloklu/otonom durumları metinle açıklanmalı.
- Dost/düşman ve hedef tipi yalnız renkle değil silüet + etiketle anlaşılmalı.
- Debug/ham veri ana ekranı boğmamalı.

Gerçek operatör paneli için:

- Backend bağlantısı olmadan canlı komutlar kapalı olmalı.
- UI doğrudan ateşleme/imha hattını enerjilendirmemeli.
- Safety Gate blok nedeni her komut denemesinde görünmeli ve loglanmalı.
- E-stop durumu UI’dan bağımsız fiziksel güvenlik katmanını temsil etmeli.

## 6. Riskler ve önlemler

| Risk | Etki | Önlem |
| --- | --- | --- |
| Simülatör gerçek panel sanılır | Güvenlik ve KTR güvenilirliği düşer | Landing ve başlıkta yüzey ayrımı açık yazılmalı |
| UI safety karar kaynağı gibi tasarlanır | Kritik güvenlik açığı | Safety Gate backend ownership altında kalmalı |
| Radar/LiDAR değerleri resmiymiş gibi yazılır | Yanlış KTR iddiası | Donanım seçilene kadar TBD/adaptör denmeli |
| Operatör ana ekranı tekrar debug ile dolar | Yarışma aksiyonu anlaşılmaz | Debug çekmecesi ayrı kalmalı |
| FIRE butonu canlı sistemde yanlış affordance verir | Operatör hatası | Dry-run/live/blocked durumu açık ve büyük gösterilmeli |

## 7. Not

Bu doküman artık eski mock-console backlog’u değil, simülatörün güncel UI doğrultusu ve gerçek operatör paneline geçiş planıdır. Eski tamamlanmış işlerin ayrıntıları git geçmişinden izlenebilir; yeni planın ayrıntılı arayüz sözleşmeleri `docs/operator_panel_interfaces_roadmap.md` ve `docs/tech_stack.md` içindedir.
