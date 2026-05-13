# Gökkalkan Frontend UI/UX İyileştirme Planı

Bu doküman, `frontend/` operatör konsolunun UI/UX iyileştirme işlerini TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması şartnamesiyle uyumlu şekilde planlar. Şartname (`docs/sartname_v5.txt`) nihai otoritedir; bu plandaki her karar görev akışı, güvenlik, mod yönetimi ve video/KTR kanıt ihtiyacına hizmet etmelidir.

## 1. Dayanaklar

- `docs/sartname_v5.txt`
  - Manuel ve otonom mod geçişleri kullanıcı denetimindedir.
  - Aşama-1 tamamen Manuel Mod ile yapılır; yönlendirme ve ateş emri kullanıcı komutuyla gerçekleşir.
  - Aşama-2 Otonom Mod ile yapılır; hedef tipi sınıflandırması beklenmez.
  - Aşama-3 Otonom Mod ile yapılır; dost/düşman ayrımı ve hedef tipine göre menzil kapısı gerekir.
  - Sistemlerde Acil Durdur bulunması zorunludur; basıldıktan sonra yarışmaya devam hakem değerlendirmesine bağlıdır.
  - Sistemlerin hem harekete yasak alan hem de atışa yasak alan tanımlama fonksiyonlarının olması beklenir.
  - Görev Kabiliyeti Gösterimi Videosu tek YouTube linki, en az 720p, 2-5 dakika ve şartnamedeki yetenek sırasına uygun olmalıdır.
- `docs/tech_stack.md`
  - Arayüz Türkçe, yarışma/rapor diliyle uyumlu ve sadece izleme ekranı değil görev kontrol ekranı olmalıdır.
  - Arayüz; mod, pan/tilt, atış izni, güvenlik kilidi nedeni, canlı görüntü, hedef etiketi, takip durumu, aşama/tur/süre/hedef sırası/menzil ve telemetri olaylarını göstermelidir.
- `TARIHLER.md`
  - KTR teslimi: 02.06.2026 17:00.
  - Video teslimi: 10.08.2026 17:00.

## 2. Mevcut Durum Özeti

Mevcut frontend React/Vite tabanlı bir mock operatör konsoludur. Başlıca dosyalar:

- `frontend/src/App.tsx` — landing ekranı, operatör konsolu, Aşama 1/2/3 panelleri, güvenlik şeridi, video kanıtı, bakım/zaman, ayar/kalibrasyon, telemetri ve komut kuyruğu.
- `frontend/src/safetyGate.ts` — menzil kapısı ve güvenlik kapısı değerlendirmeleri.
- `frontend/src/missionMock.ts` — Aşama 1/2/3 için mock hedef izleri.
- `frontend/src/types.ts` — mod, aşama, hedef, dost/düşman, menzil kapısı ve telemetri tipleri.
- `frontend/src/styles.css` — koyu tema, responsive yerleşim ve konsol görsel sistemi.
- `frontend/tests/e2e/operator-console.spec.ts` — temel Playwright görev akışı testleri.
- `frontend/src/safetyGate.test.ts` — güvenlik kapısı birim testleri.

Hazırlık sırasında baseline doğrulama olarak şu komutlar başarıyla çalıştırıldı:

```bash
cd frontend
npm run build
npm run test
```

Sonuç: build başarılı, 8 unit assertion başarılı, 6 Playwright testi başarılı.

## 3. Tasarım İlkeleri

1. **Güvenlik önce gelir.** Acil Durdur, harekete yasak alan, atışa yasak alan, bağlantı durumu, mod uyumu ve hedef/menzil kapısı UI içinde açık görünmeli; ancak gerçek engelleme backend/safety gate mantığında kalmalıdır.
2. **Operatör hatasını azalt.** Ateş ve mod geçişlerinde yanlış hedef, yanlış sıra, dost hedef, geçersiz menzil ve mod uyumsuzluğu önceden anlaşılır olmalıdır.
3. **Şartname diliyle konuş.** Arayüzde `Aşama`, `Manuel Mod`, `Otonom Mod`, `Acil Durdur`, `Harekete Yasak Alan`, `Atışa Yasak Alan`, `Dost`, `Düşman`, `Menzil Kapısı`, `Görev Kabiliyeti` gibi terimler korunmalıdır.
4. **Mock ile gerçek ayrımını net tut.** Mock kamera, mock telemetri veya simülasyon durumları kullanıcıya açıkça gösterilmelidir; gerçek donanım bağlıymış gibi iddia edilmemelidir.
5. **Video/KTR kanıtı üret.** Arayüz yalnızca görev yürütmek için değil, KTR ve Görev Kabiliyeti Gösterimi Videosu için kanıt toplamayı kolaylaştırmak için de tasarlanmalıdır.
6. **Renk tek başına anlam taşımasın.** Dost/düşman, tehlike ve güvenlik durumlarında renk yanında metin, ikon, şekil veya etiket kullanılmalıdır.
7. **Dar ekran güvenliği.** 1366x768 görünümde yatay taşma olmamalı; Acil Durdur, güvenlik nedeni, görev paneli, komut kuyruğu ve telemetri erişilebilir kalmalıdır.

## 4. Uygulama Fazları

### Faz 0 — Davranışı Kilitle ve UI Kaynağını Ayır

Amaç: Mevcut davranışı bozmadan iyileştirme yapılabilecek bir yapı hazırlamak.

İşler:

- `frontend/src/missionConfig.ts` ekle.
  - Aşama hedefleri, mod beklentileri, tur sayıları, eşikler, hedef sıra bilgisi, menzil kapıları ve video yetenek sırası tek kaynaktan beslensin.
- `App.tsx` içindeki şartname sabitlerini `missionConfig.ts` içine taşı.
- `safetyGate.test.ts` kapsamını menzil kapısı sınır değerleriyle genişlet:
  - F16: 10-15 m uygun.
  - Helikopter/Balistik Füze: 5-15 m uygun.
  - Mini/Micro İHA: 0-15 m uygun.
- Playwright testlerinde kritik mevcut davranışları koru:
  - Landing konsola geçer.
  - Aşama 1 yanlış sıra cezası ilerleme yaptırmaz.
  - Aşama 2 atışa yasak alan angajmanı bloklar.
  - Aşama 3 dost hedef atışı bloklar.
  - Acil Durdur görünür ve kaçırılması zordur.

Kabul ölçütleri:

- `npm run build` geçer.
- `npm run test` geçer.
- Şartname kaynaklı UI metinleri tek dosyadan izlenebilir.

### Faz 1 — Üst Durum Şeridi ve Güvenlik Anlamını Netleştir

Amaç: Operatörün sistem durumu ile komut kapısı kilidini karıştırmasını engellemek.

İşler:

- Üst bölümde iki ayrı gösterge kullan:
  - `Sistem Sağlığı`: kamera/mock, bağlantı, safety gate, telemetri.
  - `Komut Kapısı`: hareket izni, atış izni, blok nedeni.
- Safe modda `BLOCKED_MODE` kırmızı hata gibi gösterilmemeli. Bunun yerine:
  - Sistem durumu: `Hazır`.
  - Komut kapısı: `Safe mod nedeniyle kilitli`.
- Acil Durdur aktif olduğunda overlay metni korunmalı ve daha açıklayıcı olmalı:
  - `ACİL DURDUR AKTİF — hareket ve atış kesildi — MOCK`.
- `Harekete Yasak Alan` ve `Atışa Yasak Alan` ayrı chip olarak kalmalı; seçili blok nedeni özet metninde sade Türkçe ile görünmeli.
- Mock blok senaryosu seçici, operatör kullanımı ile test/simülasyon kullanımı ayrışacak şekilde etiketlenmeli.

Kabul ölçütleri:

- Safe mod, donanım arızası veya güvenlik ihlali gibi algılanmaz.
- Acil Durdur ve atış/hareket blok nedenleri 1366x768 görünümde görünürdür.
- Playwright testleri Safe mod kilidi, Acil Durdur ve blok nedeni metinlerini kontrol eder.

WP eşlemesi: WP-04 Güvenlik Katmanı, WP-05 Log/Telemetri.

### Faz 2 — Aşama 1 / Manuel Mod Görev Paneli

Amaç: Şartnameye göre Aşama-1’in tamamen kullanıcı komutuyla yürütüldüğünü netleştirmek ve yanlış hedef/sıra riskini azaltmak.

İşler:

- Hedef sırası panelini daha belirgin hale getir:
  - `Şu an beklenen hedef` ayrı kartta gösterilsin.
  - Tamamlanan hedefler ve sıradaki hedefler ayrı görsel durum alsın.
- Seçili hedef beklenen hedef değilse `ATEŞ` öncesinde açık uyarı göster:
  - `Seçili hedef beklenen sırada değil: -5 ceza riski`.
- `Basılı Kur` davranışını gerçek arming affordance olarak modelle:
  - Basılı değil: `Kurulu değil`.
  - Basılı tutuldu: `Atış hattı kuruldu`.
  - Bırakıldı/timeout: `Kurulum düştü`.
- Pan/tilt kontrol alanında klavye kısayolları göster:
  - Ok tuşları: kaba hareket.
  - `Shift` + ok: ince hareket.
  - `Space`: dur/hold.
- Puan ön izlemesi ekle:
  - Doğru hedefte tahmini puan.
  - Yanlış sırada ceza uyarısı.

Kabul ölçütleri:

- Kullanıcı hangi hedefin beklediğini bakışta anlar.
- Yanlış hedef seçiliyken risk açıkça görünür.
- Manuel hareket ve ateş olayları telemetriye yazılır.
- Kullanıcı komutu olmadan ateş olayı oluşmaz.

WP eşlemesi: WP-01 Manuel Mod, WP-04 Güvenlik Katmanı, WP-05 Log/Telemetri.

### Faz 3 — Aşama 2 / Otonom Tespit ve Takip Paneli

Amaç: Aşama-2’nin sürü saldırısı, tur, takip ve imha akışını sadeleştirmek; bu aşamada sınıflandırma beklenmediğini net göstermek.

İşler:

- Panel başlığına şartname notu ekle:
  - `Aşama 2: Otonom · 4 tur · hedef tipi sınıflandırması beklenmez`.
- Karar izini Türkçeleştir:
  - `Tespit → Takip → Öncelik → Güvenlik Kapısı → Angajman/Blok`.
- Her kol için hedef ilerleme/tehdit kartı göster:
  - Kol numarası.
  - Yaklaşma yönü.
  - Güven skoru.
  - Angajman uygunluğu.
- `Turu Bitir` butonunu simülasyon/test aksiyonu olarak etiketle; gerçek yarışma akışındaki tur mantığını açıklayan küçük not ekle.
- 3 ardışık tur isabetsizlik durumunu erken uyarı olarak göster.

Kabul ölçütleri:

- Aşama-2 ekranı yanlışlıkla dost/düşman sınıflandırması bekliyormuş gibi görünmez.
- Tur, isabet, boş seri ve puan bilgisi tek bakışta okunur.
- Atışa yasak alan veya Acil Durdur aktifken angajman butonu devre dışı kalır.

WP eşlemesi: WP-02 Otonom Tespit ve Takip, WP-04 Güvenlik Katmanı, WP-05 Log/Telemetri.

### Faz 4 — Aşama 3 / Dost-Düşman + Menzil Paneli

Amaç: Aşama-3’te yanlış hedef ve yanlış menzil riskini UI seviyesinde azaltmak.

İşler:

- Seçili hedef kartında şu bilgileri bir arada göster:
  - `Dost/Düşman/Bilinmeyen`.
  - Hedef tipi.
  - Mevcut menzil.
  - Geçerli imha menzil aralığı.
  - Menzil kapısı sonucu.
- Dost hedefte büyük kilit mesajı göster:
  - `DOST HEDEF — ATEŞ KİLİTLİ`.
- Bilinmeyen hedefte ayrı durum göster:
  - `Bilinmeyen hedef — angajman için sınıflandırma bekleniyor`.
- Menzil kapısını hedef tipine göre açıklayıcı yap:
  - F16: `10-15 m`.
  - Helikopter/Balistik Füze: `5-15 m`.
  - Mini/Micro İHA: `0-15 m`.
- Ceza/risk alanını açıklaştır:
  - Dost hedef vurma veya düşman hedef vuramama cezası.
  - 3 ardışık tur düşman hedef vuramama başarısızlık riski.

Kabul ölçütleri:

- Dost hedef seçiliyken ateş veya otonom angajman yapılamaz.
- Geçersiz menzilde düşman hedef seçiliyken angajman bloklanır.
- UI, blok nedenini `BLOCKED_TARGET_GATE` kodunun yanında sade Türkçe ile açıklar.

WP eşlemesi: WP-03 Dost-Düşman + Menzil, WP-04 Güvenlik Katmanı, WP-05 Log/Telemetri.

### Faz 5 — Görev Kabiliyeti Kanıt Paneli

Amaç: KTR sonrası video kapısı ve rapor kanıt ihtiyacını doğrudan arayüzden desteklemek.

İşler:

- `VideoEvidencePanel` adını kullanıcıya görünen metinde `Görev Kabiliyeti Kanıtı` olarak güncelle.
- Yetenek sırasını şartnameye göre sabitle:
  1. Kullanıcı komut arayüzleri.
  2. 15 m durağan hedef imhası.
  3. Hareket sırasında Acil Durdur ile durma.
  4. Ateş sırasında Acil Durdur ile ateşi kesme.
  5. Yan/yükseliş ekseninde hareketli hedef takibi.
  6. Opsiyonel: 5/10/15 m hedef tipi tespit/sınıflandırma.
- Her madde için:
  - Eksik/tamamlandı durumu.
  - İlk kanıt zaman damgası.
  - İlgili telemetri olayı.
- JSONL dışa aktarmada kanıt etiketlerini koru.
- Panelde video kısıtlarını göster:
  - `720p+`, `2-5 dk`, `tek YouTube linki`, `sıra eksiksiz`.

Kabul ölçütleri:

- Kanıt paneli Y1-Y6 sırasını şartnameyle aynı tutar.
- Her tamamlanan madde telemetri olayına bağlanır.
- Eksik kanıtlar açık görünür.

WP eşlemesi: WP-05 Log/Telemetri, WP-01, WP-02, WP-03, WP-04.

### Faz 6 — Bileşenlere Ayırma ve Bakım Kolaylığı

Amaç: UI iyileştirmelerini sürdürülebilir hale getirmek.

Önerilen dosya yapısı:

```text
frontend/src/
  App.tsx
  missionConfig.ts
  components/
    Landing.tsx
    CameraViewport.tsx
    SafetyStrip.tsx
    ModeBar.tsx
    ManualStagePanel.tsx
    AutonomousStagePanel.tsx
    Stage3IntelPanel.tsx
    VideoEvidencePanel.tsx
    MaintenancePanel.tsx
    SettingsPanel.tsx
    TelemetryPanel.tsx
    CommandQueue.tsx
  safetyGate.ts
  missionMock.ts
  telemetry.ts
  types.ts
  styles.css
```

Kurallar:

- Yeni dependency eklenmeyecek.
- Refactor sırasında davranış değişikliği ayrı commit/diff olarak yapılacak.
- Önce testler, sonra bileşen ayırma.
- Güvenlik mantığı UI bileşenlerinin içine gömülmeyecek; `safetyGate.ts` ve ileride backend safety gate kaynak kabul edilecek.

Kabul ölçütleri:

- `App.tsx` ana state/orchestration dosyası olarak sadeleşir.
- Paneller bağımsız test edilebilir hale gelir.
- Build/test sonuçları değişmez.

### Faz 7 — Responsive, Erişilebilirlik ve Görsel Polish

Amaç: Hakem/operatör kullanımı için okunabilir, tutarlı, güvenilir ve gösterime hazır konsol hissi oluşturmak.

İşler:

- 1366x768 ve 1920x1080 ekranlar için ayrı görsel QA yap.
- Yatay scroll oluşmamasını test et.
- Focus state ekle; klavyeyle mod, aşama ve temel komutlara ulaşılabilsin.
- Küçük ekranlarda sağ panel bölümleri katlanabilir ya da tek kolon düzeninde sıralı olsun.
- Dost/düşman ve güvenlik renklerine metin/ikon desteği ekle.
- Animasyon yoğunluğunu azaltmak için `prefers-reduced-motion` desteği ekle.
- Canlı/mock kamera alanında gereksiz dekor ile görev bilgisi çakışmasın.

Kabul ölçütleri:

- 1366x768 görünümde yatay taşma yoktur.
- 1920x1080 görünümde önemli bilgiler dağınık veya aşırı yoğun görünmez.
- Klavye ile temel akışlar denenebilir.
- Renk körlüğü veya düşük kontrast durumlarında kritik güvenlik bilgileri metinle anlaşılır.

## 5. Test Planı

### Unit testler

- `rangeGateFor` sınır değerleri.
- `evaluateSafety` için:
  - Acil Durdur tüm komutları bloklar.
  - Donanım bağlantısı yoksa komut bloklanır.
  - Harekete yasak alan hareketi bloklar.
  - Atışa yasak alan ateşi bloklar.
  - Safe/bakım/bloklu mod ateşi bloklar.
  - Aşama-3 dost hedef ve geçersiz menzil ateşi bloklar.

### E2E testler

- Landing ekranından konsola geçiş.
- Aşama 1 doğru ve yanlış sıra akışı.
- Aşama 2 Otonom Başlat, atışa yasak alan blok testi.
- Aşama 3 dost hedef ve geçersiz menzil blok testi.
- Acil Durdur overlay görünürlüğü.
- Görev Kabiliyeti Kanıt Paneli Y1-Y6 event bağlama testi.
- 1366x768 ve 1920x1080 viewport smoke testi.
- Yatay scroll kontrolü.

### Manuel QA

- Şartnamedeki Y1-Y6 video sırasına göre mock prova.
- Operatörün yanlış hedef/yanlış menzil/yanlış mod durumlarını anlayıp anlamadığına yönelik kısa takım içi kullanım testi.
- KTR ekran görüntüleri için 1366 ve 1920 çözünürlükte screenshot üretimi.

## 6. Riskler ve Önlemler

| Risk | Etki | Önlem |
| --- | --- | --- |
| UI, gerçek donanım bağlıymış gibi algılanır | Hakem/rapor güvenilirliği düşer | Mock/sim etiketleri açık tutulmalı |
| Safe mod kırmızı hata gibi görünür | Operatör yanlış alarm algılar | Sistem sağlığı ve komut kapısı ayrılmalı |
| Şartname sabitleri UI içinde dağılır | Gelecekte metin/kurallar drift eder | `missionConfig.ts` tek kaynak olmalı |
| Dost/düşman sadece renkle ayrılır | Kritik güvenlik bilgisi kaçabilir | Metin, ikon ve kilit durumu kullanılmalı |
| Görsel polish güvenlik mantığını gölgeler | Tehlikeli yanlış anlaşılma | Güvenlik şeridi ve blok nedeni her zaman üst öncelikli kalmalı |
| Yeni UI testleri kırılgan olur | Bakım maliyeti artar | Role/text tabanlı seçiciler ve görev odaklı testler kullanılmalı |

## 7. Öncelikli İş Sırası

1. `missionConfig.ts` ve test kapsamı.
2. Safe mod / sistem sağlığı / komut kapısı ayrımı.
3. Aşama 1 yanlış hedef ve arming deneyimi.
4. Aşama 3 dost/düşman + menzil görünürlüğü.
5. Aşama 2 sürü/tur akışı sadeleştirmesi.
6. Görev Kabiliyeti Kanıt Paneli.
7. Bileşen refactor.
8. Responsive, erişilebilirlik ve görsel polish.

## 8. Tamamlandı Sayılma Ölçütü

Bu planın uygulaması tamamlandı sayılmadan önce:

- `npm run build` başarılı olmalı.
- `npm run test` başarılı olmalı.
- 1366x768 ve 1920x1080 ekran görüntüleri üretilmeli.
- Aşama 1/2/3 mock görev akışları manuel olarak denenmeli.
- Acil Durdur, harekete yasak alan ve atışa yasak alan blokları hem unit hem e2e seviyesinde doğrulanmalı.
- Görev Kabiliyeti Kanıt Paneli şartnamedeki Y1-Y6 sırasını korumalı.
- UI metinlerinde Türkçe karakterler ve yarışma terimleri doğru kullanılmalı.
