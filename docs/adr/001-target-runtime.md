# ADR-001 — Hedef Çalışma Ortamı ve Dil Sınırları

- Durum: **Kabul edildi**
- Tarih: **25.07.2026**
- İlgili işler: `ADR-001`, `ENV-003`–`ENV-006`, `CORE-001`–`CORE-005`

## Bağlam

Sistem; kamera işleme, görev mantığı, kullanıcı arayüzü, telemetri ve gerçek
zamanlı motor/emniyet görevlerini birlikte yürütür. Raspberry Pi üzerinde sanal
makine, ROS 2 veya tüm sistemi Rust ile yeniden yazma seçenekleri geliştirme
maliyetini ve entegrasyon yüzeyini büyütür. KTR de yüksek seviye Linux yükünü
Raspberry Pi 5’e, gerçek zamanlı motor/emniyet görevlerini Raspberry Pi
Pico/RP2040’a ayırmaktadır.

## Karar

1. **Hedef bilgisayar:** Raspberry Pi 5 üzerinde doğrudan 64-bit Raspberry Pi OS.
   Hedefte VM/hypervisor bulunmaz. Geliştirici bilgisayarları macOS veya Linux
   olabilir; hedef davranışı Linux CI ve Pi üzerinde ayrıca doğrulanır.
2. **Servis yönetimi:** Backend, perception, UI/static server ve recorder ayrı
   `systemd` servisleri olur. Kesin imaj/sürüm ve paket manifesti `ENV-003`
   kapsamında kilitlenir.
3. **Yüksek seviye yazılım:** Backend ve perception Python; operatör paneli
   React/Vite/TypeScript olarak kalır.
4. **Firmware:** Raspberry Pi Pico/RP2040 üzerinde Pico SDK ile C/C++ kullanılır.
   Firmware, Pico’nun motor darbeleri, enkoder, watchdog, Acil Durdur ve güvenli
   çıkış durumlarını yöneten programıdır; Raspberry Pi’a kurulan ayrı bir işletim
   sistemi veya ROS dağıtımı değildir.
5. **ROS 2 kullanılmaz.** Mevcut ihtiyaçlar yerel süreçler, açık adapter sınırları,
   HTTP/state stream ve CAN/UART ile karşılanır.
6. **Tam Rust yeniden yazımı yapılmaz.** Thread güvenliği; tek sahipli Mission
   Core, immutable snapshot, queue/event köprüsü ve process sınırıyla çözülür.
   Gerçek zamanlı emniyet Linux dil seçimine değil MCU ve fiziksel kesme zincirine
   dayanır.
7. **Runtime profilleri:** Varsayılan `SIM`, sanal CAN için `HIL`, fiziksel çıkış
   için `LIVE` kullanılır. `LIVE`; backend config, fiziksel interlock preflight ve
   readiness olmadan adapter oluşturamaz. Operatör arm zinciri ayrıca kapalıdır.

## Yeniden değerlendirme koşulları

ROS 2 yalnız aşağıdakilerden biri ölçümlü olarak ortaya çıkarsa yeniden görüşülür:

- Birden fazla bilgisayar/robot düğümünde discovery, QoS ve ortak zaman yönetimi
  mevcut adapter yaklaşımını sürdürülemez kılarsa;
- TF benzeri çoklu dinamik koordinat ağacı veya rosbag benzeri kayıt ihtiyacı,
  mevcut kalibrasyon/replay katmanından belirgin biçimde büyük hâle gelirse;
- Gecikme, paket kaybı veya bakım maliyeti ölçümleri ROS 2 geçişinin maliyetini
  haklı çıkarırsa.

Rust yalnız profiler ile belirlenmiş bir CPU hotspot’u, Python sınırında
giderilemeyen bellek güvenliği riski veya testle tekrarlanan concurrency problemi
için küçük bir native modül olarak değerlendirilir. Ölçüm olmadan mimari yeniden
yazılmaz.

## Sonuçlar

- Ekip tek bir anlaşılır ana stack üzerinde ilerler.
- Linux thread’leri güvenlik garantisi sayılmaz.
- Pico firmware ve fiziksel E-Stop zinciri zorunlu kalır.
- Pi imaj sözleşmesi, `systemd` birimleri ve temiz kurulum scripti Faz 2’de
  `deploy/` ve `scripts/bootstrap_pi.sh` altında oluşturulmuştur. Fiziksel Pi
  host doğrulaması hâlâ donanım üzerinde çalıştırılmalıdır.

## Kaynaklar

- [`docs/sartname_v1_3.pdf`](../sartname_v1_3.pdf), §4.2 ve §6.
- [`reports/Gökkalkan Kritik Tasarım Raporu.pdf`](../../reports/Gökkalkan%20Kritik%20Tasarım%20Raporu.pdf), §4.2.1–4.2.2.
- [`docs/tech_stack.md`](../tech_stack.md).
