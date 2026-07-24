# ADR-004 — Tek Sahipli Mission Core ve Concurrency Sınırı

- Durum: **Kabul edildi**
- Tarih: **25.07.2026**
- İlgili işler: `CORE-001`–`CORE-007`, `WP-01`–`WP-05`

## Bağlam

HTTP handler’ları, CAN receive callback’leri ve kamera/perception döngüsü aynı
değişkenleri doğrudan güncellerse olay sırası, telemetri ve Safety Gate kararı
yük altında tekrarlanabilir olmaz. Her erişime kilit eklemek state’in gerçek
sahibini belirsiz bırakır. Tüm backend’i Rust ile yeniden yazmak ise mevcut
Python adapter/test yatırımını böler ve fiziksel gerçek zaman güvenliğini Linux
process’ine taşımadığı için temel emniyet problemini çözmez.

## Karar

1. Görev state’inin tek yazarı Python `MissionCore` reducer thread’idir.
2. Mod, aşama, tur, seçili hedef, arm, bakım, Acil Durdur, perception health,
   fault ve lifecycle alanları frozen `MissionState` içinde yayınlanır.
3. HTTP handler’ı, CAN/GPIO callback’i ve sensör üreticisi yalnız bounded kuyruğa
   sürümlü `CommandEnvelope` bırakır. İş tamamlandığında tek sıralı
   `EventEnvelope` oluşur.
4. `OperatorService` üretimde owner thread’e bağlanır; başka thread’den doğrudan
   mutasyon programlama hatasıdır.
5. CAN/GPIO callback’leri `publish_threadsafe` köprüsünü kullanır. Bu,
   `loop.call_soon_threadsafe` ile aynı sahiplik ilkesinin queue tabanlı
   karşılığıdır.
6. CPU-ağır perception `gokkalkan-perception.service` altında ayrı OS
   process’idir. Process içinde bounded latest-wins çıkış kuyruğu ve ayrı HTTP
   sender thread’i bulunur. Heartbeat kaybı Mission Core’u çökertmez; angajman
   fail-closed kapanır.
7. UI state’i immutable snapshot olarak okur. Ana yayın SSE, kesinti yedeği REST
   snapshot’tır. Görev/bakım saatleri donmasın diye reducer en geç saniyede bir
   fresh snapshot yayınlar; okuyucu thread state hesaplamaz.
8. Kapanışta önce yeni komut kabulü kesilir, mevcut kuyruk boşaltılır, sonra core
   `STOPPED` olur. Perception `SIGINT` ile thread’lerini ve kamerayı kapatır.

Mesaj alanları, sürüm ve idempotency politikası
[`docs/message_contracts.md`](../message_contracts.md) belgesindedir.

## Reddedilen seçenekler

- **Her paylaşılan nesneye ayrı lock eklemek:** Deadlock/race yüzeyini büyütür;
  olay sırasını ve tek yazarı açıkça tanımlamaz.
- **Tüm backend/perception’ı Rust ile yeniden yazmak:** Ölçülmüş bir hotspot veya
  Python ile giderilemeyen bellek güvenliği sorunu yoktur; entegrasyon yükü
  faydasından büyüktür. ADR-001’deki profiler eşiği geçerli kalır.
- **Perception’ı Mission Core thread/process’inde çalıştırmak:** CPU/kamera
  arızasının komut otoritesini durdurmasına neden olur.
- **UI’da 300 ms REST polling:** Gereksiz yük ve birbirinden farklı anlarda
  okunmuş state üretir; SSE + düşük hızlı fallback seçilmiştir.

## Sonuçlar ve sınırlar

- Aynı anda gelen HTTP, CAN ve sensör mesajları tek, izlenebilir olay sırasına
  dönüşür.
- Immutable snapshot okuyucuları reducer state’ini değiştiremez.
- Backpressure davranışı açık ve test edilebilirdir.
- Python Mission Core gerçek zamanlı motor emniyet sistemi değildir. Pico
  watchdog, fiziksel Acil Durdur, interlock ve canlı arm zinciri Faz 4’te
  tamamlanmadan fiziksel çıkış açılmaz.
- Gerçek kamera, CAN ve TFA50-L ile yük/gecikme ölçümü henüz yapılmamıştır.

## Kanıt

- `tests/test_mission_core.py`: owner thread, eşzamanlı komut sırası,
  idempotency, duplicate/out-of-order sensör olayları, external thread bridge,
  perception watchdog, kapanış ve SSE.
- `tests/test_perception_bridge.py`: bounded latest-wins queue, heartbeat ve temiz
  thread kapanışı.
