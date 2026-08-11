# Gökkalkan Yazılım–Donanım Uçtan Uca Entegrasyon Planı

> **Durum:** Uygulanacak ana çalışma planı — nihai BOM ve tek kanallı mühürleme devresiyle hizalı
>
> **Son güncelleme:** 11 Ağustos 2026
>
> **Kapsam:** WP-01 Manuel Mod, WP-02 Otonom Tespit ve Takip, WP-03 Dost-Düşman + Menzil, WP-04 Güvenlik Katmanı, WP-05 Log/Telemetri
>
> **Ana hedef:** Nihai mekanik ve elektrik imalat tamamlandığında Raspberry Pi 5, Pico, DM542 sürücüler, enkoderler, limit anahtarları, Camera Module 3, AI HAT+, TFA50-L ve airsoft arayüzünün fail-closed ve izlenebilir biçimde birlikte çalışması.

> **Revizyon tabanı:** `Gökkalkan Malzeme Listesi - Nihai Kablolama.xlsx`, `docs/IMALAT_EK_MALZEME_SIPARIS_LISTESI.html`, `docs/IMALAT_KOMPONENT_BAGLANTI_REHBERI.html`, `docs/adr/005-pi-pico-usb-serial.md` ve `docs/usb_serial_mcu_protocol.md`. İmalat sırasında oluşacak imzalı as-built şema ve fiziksel cihaz etiketleri, satın alma bağlantılarından üstündür.

---

## 1. Planın kullanımı

Bu belge yalnızca bir eksik listesi değildir. Her faz tamamlandıkça:

1. Faz içindeki görev kutuları işaretlenir.
2. Belirtilen testler gerçekten çalıştırılır.
3. Test komutu, tarih, donanım revizyonu ve sonuç kanıt dosyasına yazılır.
4. Fazın **çıkış kriterleri** eksiksiz karşılanmadan sonraki fiziksel yetki seviyesi açılmaz.
5. Fiziksel çıkış oluşturmayan host/mock testleri, fiziksel HIL veya saha kabulü yerine geçmez.

### Durum işaretleri

- `[ ]` Başlanmadı
- `[-]` Devam ediyor
- `[x]` Tamamlandı ve kanıtı kaydedildi
- `[!]` Bloke; nedeni ve sorumlusu yazılmalı

### Kanıt dosyası adlandırma

Her fiziksel kabul oturumu için aşağıdaki biçim kullanılmalıdır:

```text
evidence/<YYYY-MM-DD>/<faz>/<kart-revizyonu>/<test-adi>.json
evidence/<YYYY-MM-DD>/<faz>/<kart-revizyonu>/<test-adi>.md
```

Video, fotoğraf ve büyük loglar git'e eklenmemelidir. Repo içinde bunların hash'i, dosya adı ve haricî saklama konumu tutulmalıdır.

### Bu revizyonda kilitlenen kararlar

- Pi 5 ↔ Pico hattı **USB CDC Serial**'dır; fiziksel CAN donanımı kullanılmayacaktır.
- Acil Durdur mimarisi, mevcut kilitlemeli **tek NK** Gwest buton + **LP1K1210BD** + anlık **1NA START** + **LA4KE1B** mühürleme devresidir.
- Siemens 3SK, ikinci E-Stop kontağı, LP1K1201BD ve ayrı bir “manuel reset” butonu aktif mimaride yoktur.
- `X` noktası **24 V girişli PC817/EL817 modülü** üzerinden Pico'ya `ESTOP_SAFE_SENSE` olarak gelir. Bu sinyal E-Stop hattının kapalı olduğunu gösterir; kontaktör ana kutuplarının gerçekten kapandığını kanıtlamaz.
- 24 V ana dağıtım: RSP +24 V → 20 A ana sigorta → 6 yollu ATO/ATC kutu → LP1K1210BD ana kutupları → tehlikeli motor yükleri. 1 A kontrol dalı kontaktör ana kutuplarından önce alınır.
- Airsoft, 24 V baradan ayrı 7,4 V T-Plug alanında kalır; ayrı kapaklı sigorta ve DC motor kalkış akımına uygun fiziksel kesme elemanı doğrulanmadan LIVE atış açılmaz.
- Bu asgari mimari çift kanallı veya SIL dereceli bir emniyet sistemi olarak tanımlanmayacaktır.

---

## 2. Bağlayıcı sistem hedefi

Şartnameye göre:

- Aşama 1 tamamen manuel olmalıdır; hareket ve ateş operatör komutuyla gerçekleşir (`docs/sartname_v4.txt:723-730`).
- Aşama 2 otomatik hedef tespit, takip ve imha gerçekleştirmelidir (`docs/sartname_v4.txt:730-734`).
- Aşama 2'de hedef tipi sınıflandırması beklenmez (`docs/sartname_v4.txt:847-857`).
- Aşama 3 dost/düşman, hedef tipi ve hedef tipine uygun menzil kararı ister (`docs/sartname_v4.txt:862-903`).
- Yazılımdan bağımsız haricî Acil Durdur zorunludur (`docs/sartname_v4.txt:749-752`).

### Uçtan uca başarı tanımı

Sistem ancak aşağıdaki koşulların tamamı sağlandığında **uçtan uca entegre** sayılır:

1. Pi, Pico'yu kararlı `/dev/serial/by-id/...` yolu ile bulur.
2. Pico açılışta motor ve FIRE çıkışlarını pasif tutar.
3. USB kopması, heartbeat kaybı, limit, enkoder, airsoft interlock veya tetik geri bildirim hatasında Pico motor/FIRE çıkışlarını fail-closed kapatır; E-Stop ayrıca kontaktör üzerinden tehlikeli 24 V hareket enerjisini yazılımdan bağımsız keser.
4. E-Stop bırakıldığında kontaktör kendiliğinden çekmez. Önce fiziksel START, ardından ayrı yazılım reset/arm işlemi gerekir; bunlardan hiçbiri diğerinin yerine geçmez.
5. Manuel pan/tilt komutu gerçek motorda uygulanır ve enkoder geri bildirimiyle doğrulanır.
6. FIRE komutu yalnız backend Safety Gate, taze Pico durumu, airsoft fiziksel kesme izni ve tetik geri bildirimi birlikte sağlandığında kuru kontağı sınırlı süreyle kapatır.
7. LiDAR menzili doğru kamera track'i ve gerçek taret yaw açısıyla eşleştirilir.
8. Aşama 2'de sistem operatörün tek tek aim/fire komutu olmadan angajman döngüsünü ilerletir.
9. Aşama 3'te dost unsur ateş yetkisi alamaz; düşman hedef yalnız tipi için geçerli menzilde yetki alır.
10. Her komut, blok nedeni, sensör durumu, ACK/NACK, fault ve operatör işlemi telemetride yeniden oynatılabilir.

---

## 3. Kararlaştırılmış fiziksel mimari

```text
Operatör Paneli
    ↓ HTTP / SSE
Raspberry Pi 5
    ├─ Backend Mission Core + Safety Gate
    ├─ Camera Module 3 → Perception → TrackState
    ├─ AI HAT+ 26 TOPS / Hailo-8 → detector/classifier
    ├─ TFA50-L UART → calibrated range fusion
    └─ USB-A → Micro-USB / USB CDC
             ↓
         Raspberry Pi Pico
             ├─ izole STEP/DIR/ENA → DM542 PAN → NEMA23 PAN
             ├─ izole STEP/DIR/ENA → DM542 TILT → NEMA23 TILT
             ├─ receiver/izolasyon ← PAN/TILT enkoderleri
             ├─ NC giriş ← PAN/TILT limit anahtarları
             ├─ 3,3 V izole giriş ← PC817 ← 24 V `X`/E-Stop güvenli durum hattı
             └─ PhotoMOS/izole NO kuru kontak → airsoft stok tetik girişi

24 V tek kanallı mühürleme devresi:
RSP +24 V → 1 A kontrol sigortası → E-Stop NK → X
X → START 1NA → LP1K1210BD A1
LP1K1210BD yardımcı 1NA → START'a paralel mühürleme
LP1K1210BD A2 → kontrol 0 V; LA4KE1B → A1/A2
X → PC817 24 V giriş → izole Pico `ESTOP_SAFE_SENSE`

Tehlikeli 24 V hareket enerjisi:
RSP +24 V → 20 A ana sigorta → 6 yollu ATO/ATC kutu
→ LP1K1210BD ana kutupları → PAN/TILT DM542 yükleri

Airsoft enerji alanı:
7,4 V batarya → T-Plug ara uzatma → ayrı sigorta
→ DC değeri doğrulanmış fiziksel kesme elemanı → stok ETU/gearbox
```

Aktif Pi–Pico taşıması USB CDC Serial'dır. CAN fiziksel katmanı satın alma ve imalat kapsamında değildir. Tarihsel CAN mesaj kimlikleri yalnız USB içindeki payload semantiğinde korunur (`docs/adr/005-pi-pico-usb-serial.md:11-25`).

`ESTOP_SAFE_SENSE`, kontaktörün çektiği veya ana kontakların sağlıklı olduğu anlamına gelmez. Mevcut LP1K1210BD'nin tek yardımcı 1NA kontağı mühürleme için kullanıldığından bağımsız kontaktör geri bildirimi yoktur. Bu nedenle START/kontaktör fonksiyonu fiziksel kabulde ayrıca gözlenir; yazılım bu sinyalden kontaktör durumunu uydurmaz.

---

## 4. Mevcut yazılım tabanı ve başlangıç kanıtı

### Hazır olan yapılar

- Backend-otoriter Safety Gate ve görev durumu
- Operatör API'si, SSE state stream ve React operatör paneli
- USB COBS + CRC16 framing, sequence ve ACK/NACK
- Pi tarafında `UsbSerialMcuAdapter`
- Pico host-testli güvenlik durum makinesi
- 100 ms host heartbeat ve 250 ms Pico watchdog sözleşmesi
- TFA50-L decoder, serial adapter ve yaw-range association sınıfları
- Kamera, HSV aday çıkarma, centroid tracking ve perception bridge
- Telemetri, replay ve release-gate altyapısı

### 11 Ağustos 2026'da yeniden alınan yerel kanıt

```text
.venv/bin/python -m pytest
→ 263 passed, 4 skipped

.venv-perception/bin/python -m pytest \
  tests/test_phase9_sensor_fusion.py tests/test_dataset_pipeline.py
→ 23 passed

cmake -S firmware/pico -B build/firmware-host -G Ninja
cmake --build build/firmware-host
ctest --test-dir build/firmware-host --output-on-failure
→ 1/1 passed

npm run dev:check
→ passed

python3 scripts/verify_pi_manifest.py --manifest-only
→ PASS
```

Ana `.venv` koşusundaki dört skip, `numpy` bulunmayan perception testleridir; aynı hedefler `.venv-perception` içinde 23/23 geçmiştir. İki `python-can` deprecation uyarısı tarihsel vCAN test yolundadır ve fiziksel taşımanın USB olduğu kararını değiştirmez.

### Bu kanıtın sınırı

Yukarıdaki sonuçlar fiziksel motor, enkoder, limit, E-Stop, LiDAR, USB EMI, PhotoMOS veya airsoft kabulü değildir. `firmware/pico/src/pico_main.cpp:62-64` fiziksel aktüatör GPIO'larını bilerek kapatır ve `firmware/pico/src/pico_main.cpp:112-114` PAN/TILT komutunu NACK eder.

---

## 5. Bağımlılık ve kilometre taşı haritası

```text
M0 Mimari/pin freeze
 └─→ M1 Pico safe I/O
      ├─→ M2 Motor + enkoder HIL
      ├─→ M3 Airsoft safe-load HIL
      └─→ M4 USB status + LIVE bootstrap
                    ├─→ M5 Manuel Mod fiziksel kabul
                    ├─→ M6 LiDAR + kamera fusion
                    └─→ M7 Otonom aim/engage
                              ├─→ M8 Aşama 2 kabul
                              └─→ M9 Hedef tipi + Aşama 3 kabul
                                         └─→ M10 Release kanıtı
```

### Yetki seviyeleri

| Seviye | İzin verilen | Yasak |
|---|---|---|
| L0 Host/Mock | Unit, simülasyon, loopback | Fiziksel GPIO |
| L1 Monitor-only HIL | USB, status, E-Stop/limit/enkoder okuma | Motor, arm, FIRE |
| L2 Safe-load HIL | Düşük hız motor, lamba/yapay FIRE yükü | BB ve dolu şarjör |
| L3 Mekanik HIL | Pan/tilt mekanik hareket, boş airsoft arayüzü | Hedefe atış |
| L4 Kontrollü saha | Onaylı prosedür ve fiziksel güvenlik alanı | Onaysız LIVE |

---

# FAZ 0 — As-built elektronik ve pin haritasını kilitleme

## Amaç

Firmware'in tahminle değil imal edilen kart/pano revizyonuyla aynı pin, gerilim, polarite ve güvenli başlangıç durumunu kullanması.

## Bağımlılıklar

- Nihai izole STEP/DIR/ENA arayüz devresi
- Enkoderin kesin model/etiket ve elektriksel çıkış bilgisi
- Limit switch'lerin NC bağlantısı
- PhotoMOS/izole kuru kontak arayüzü
- E-Stop sonrası `X` noktasından Pico'ya gelecek 24 V girişli PC817/EL817 modülü
- Tek NK E-Stop + START + LP1K1210BD yardımcı 1NA mühürleme devresinin imzalı bağlantı şeması
- Airsoft 7,4 V dalındaki ayrı sigorta ve DC uygun kesme elemanının model/değerleri
- Pico'nun USB ve haricî besleme topolojisi

## Görevler

- [ ] Pano/kart revizyonuna benzersiz kimlik ver: örn. `GKK-IO-REV-A`.
- [ ] Pico GPIO pinlerini imzalı as-built şemadan aktar.
- [ ] Her pin için yön, aktif seviye, pull-up/down ve boot durumu yaz.
- [ ] PAN ve TILT `STEP/DIR/ENA` pinlerinin çakışmadığını doğrula.
- [ ] PAN/TILT encoder A/B/Z pinlerini ve receiver seviyesini kaydet.
- [ ] PAN/TILT limit NC girişlerini kaydet.
- [ ] `ESTOP_SAFE_SENSE`, `FIRE_INTERLOCK`, `TRIGGER_FEEDBACK`, `FIRE_OUT` pinlerini kaydet.
- [ ] `ESTOP_SAFE_SENSE` için PC817 çıkış polaritesini ölç: `X=24 V`, `X=0 V` ve kablo kopuk durumlarında Pico GPIO seviyelerini kaydet.
- [ ] `ESTOP_SAFE_SENSE=true` ifadesinin yalnız E-Stop hattının kapalı olduğunu, kontaktör geri bildirimi olmadığını pin haritasına yaz.
- [ ] START butonunun yazılım girişi olmadığını; fiziksel mühürlemeyi başlattığını şemada ayır.
- [ ] 24 V, 5 V/Pico ve 7,4 V airsoft elektrik alanlarını ve hangi noktalarda galvanik izolasyon bulunduğunu kaydet.
- [ ] YL-314-C-T kullanılacaksa bobin gerilimi ile 7,4 V DC motor/inrush kesme değerini üretici belgesi veya ölçümle doğrula; doğrulanmazsa as-built listesine ekleme.
- [ ] GPIO 3,3 V sınırını aşan saha sinyali olmadığını elektrik ekibiyle doğrula.
- [ ] Pico USB VBUS/VSYS backfeed kararını şemaya ve dokümana yaz.
- [ ] Boot/reset/USB kopmasında arayüzün fiziksel olarak pasif kaldığını lojik tabloyla göster.

## Oluşturulacak/güncellenecek dosyalar

- `firmware/pico/include/board_config.hpp`
- `docs/hardware/GKK-IO-REV-A_PIN_MAP.md`
- `Gökkalkan Malzeme Listesi - Nihai Kablolama.xlsx`
- `docs/IMALAT_EK_MALZEME_SIPARIS_LISTESI.html`
- `docs/IMALAT_KOMPONENT_BAGLANTI_REHBERI.html`
- `config/runtime/hil-physical.toml`

`board_config.hpp` içinde gerçek pin numaraları imzalı şemadan gelene kadar aktüatör build'i derlenmemelidir. `TODO` pinlerle fiziksel çıkış oluşturulmamalıdır.

## Testler

- Pin çakışma ve eksik kritik pin için compile-time `static_assert`
- Boot seviyesi için masa üstü multimetre/osiloskop kontrolü
- USB bağlı/bağlı değil durumlarında backfeed kontrolü
- E-Stop için dört adımlı süreklilik testi: bırakılmış-kapalı, basılmış-açık, mekanik kilitli, çevrilince yeniden kapalı
- START için üç adımlı test: bırakılmış-açık, basılmış-kapalı, bırakınca tekrar açık
- START ile çekme/mühürleme, E-Stop ile düşme ve E-Stop bırakıldığında START'sız yeniden çekmeme testi
- PC817 iki elektrik alanı arasında izolasyon, 3,3 V çıkış seviyesi ve aktif polarite ölçümü

## Çıkış kriterleri

- [ ] Kart revizyonu ve pin haritası iki kişi tarafından kontrol edildi.
- [ ] Hiçbir kritik pin `UNVERIFIED`, `TODO` veya varsayılan değil.
- [ ] Boot/reset sırasında STEP, ENA ve FIRE pasif ölçüldü.
- [ ] Kontaktör E-Stop bırakıldığında START olmadan çekmiyor; START bırakılınca mühürleme sürüyor; E-Stop'ta düşüyor.
- [ ] PC817 polaritesi ve `ESTOP_SAFE_SENSE` anlamı imzalı pin haritasına işlendi.
- [ ] Airsoft DC kesme elemanı ve sigorta değeri doğrulanmadıysa FIRE fiziksel yetkisi kapalı işaretlendi.
- [ ] Pin haritası firmware ve imalat dokümanında aynı revizyonu gösteriyor.

---

# FAZ 1 — Pico donanım soyutlama ve fail-closed girişleri

## Amaç

Güvenlik durum makinesinin varsayılan `Inputs` nesnesi yerine PC817 üzerinden gerçek `ESTOP_SAFE_SENSE`, airsoft interlock, trigger feedback, limit ve enkoder sağlığıyla beslenmesi.

## Mevcut boşluk

`firmware/pico/src/pico_main.cpp:68` varsayılan bir `Inputs` oluşturur; fiziksel GPIO'lardan güncellenmez. Mevcut yapıda limit switch alanları bulunmaz (`firmware/pico/include/safety_state_machine.hpp:9-17`).

## Görevler

- [ ] `PicoIo`/HAL sınıfı oluştur.
- [ ] Tüm kritik girişleri fail-closed polariteyle oku.
- [ ] NC limit hattında kopuk kabloyu fault kabul et.
- [ ] PC817 çıkışını `safety_chain_ok` olarak oku; `estop = !safety_chain_ok` dönüşümünü tek yerde ve testli uygula.
- [ ] `ESTOP_SAFE_SENSE` değişimini edge event olarak raporla; periyodik status ile kayıp edge'i telafi et.
- [ ] Mekanik kontaklar için zaman tabanlı debounce uygula.
- [ ] Girişlerin ham ve debounce edilmiş durumunu ayrı tut.
- [ ] Limit aktifken ilgili yöne hareketi yasakla; ters yönde kontrollü uzaklaşmaya izin kuralını ayrı test et.
- [ ] E-Stop veya interlock fault sonrası açık bir yazılım `RESET` ve yeni `ARM` olmadan READY/ARMED durumuna dönme. Fiziksel START yalnız kontaktör mühürlemesidir; yazılım reset'i değildir.
- [ ] Pico açılışında PC817 polaritesi/config'i eksik veya çelişkiliyse `FAULT` durumunda kal.
- [ ] Girişlerin kaybında GPIO çıkışlarını aynı kontrol döngüsünde pasifleştir.

## Dosyalar

- `firmware/pico/include/io_hal.hpp` (yeni)
- `firmware/pico/src/io_hal.cpp` (yeni)
- `firmware/pico/include/safety_state_machine.hpp`
- `firmware/pico/src/safety_state_machine.cpp`
- `firmware/pico/src/pico_main.cpp`
- `firmware/pico/tests/host_tests.cpp`
- `firmware/pico/CMakeLists.txt`

## Birim testleri

- [ ] E-Stop boot anında aktif → `FAULT`, tüm çıkışlar kapalı
- [ ] E-Stop çalışma sırasında aktif → aynı tick'te çıkışlar kapalı
- [ ] E-Stop bırakılır → otomatik arm yok
- [ ] `X=24 V`/`X=0 V`/PC817 çıkış kablosu kopuk → kaydedilen polariteye göre doğru `estopActive`, kopukta fail-closed
- [ ] Interlock açık → ARM ve FIRE reddedilir
- [ ] Trigger feedback takılı → FIRE reddedilir/fault
- [ ] PAN limit aktif ve PAN+ komutu → reddedilir
- [ ] PAN limit aktif ve güvenli PAN− kurtarma komutu → yalnız belirlenen düşük hızda izin
- [ ] Limit kablosu kopuk → fault
- [ ] Debounce sınır değerlerinin altındaki darbe → durum değişmez

## Çıkış kriterleri

- [ ] Kritik girişlerin hiçbiri sabit varsayılan değerden gelmiyor.
- [ ] E-Stop güvenli-durum sinyali, airsoft interlock ve limit fault'ları motor/FIRE yetkisini fiziksel çıkış eklenmeden önce lojik olarak kapatıyor.
- [ ] Host testleri ve GPIO-in-the-loop monitor-only testi geçiyor.

---

# FAZ 2 — Pan/tilt hareket firmware'i

## Amaç

Pico'nun USB'den gelen hedef açı komutunu DM542 için sınırlı STEP/DIR/ENA darbelerine çevirmesi ve gerçek açıyı enkoderle doğrulaması.

## Tasarım ilkeleri

- Backend hedef açı/niyet gönderir; gerçek zamanlı pulse üretimi Pico'da kalır.
- Step sayısı tek başına konum gerçeği sayılmaz; enkoder geri bildirimi otoritatiftir.
- Soft limit ve hard limit birlikte uygulanır.
- Heartbeat kaybında pulse üretimi durur ve ENA güvenli duruma geçer.
- Boot veya reconnect otomatik hareket oluşturmaz.

## Görevler

- [ ] PAN/TILT payload'undaki mutlak hedef centidegree alanlarını decode et.
- [ ] Motor adım açısı, mikrostep ve dişli oranından step/degree dönüşümü yap.
- [ ] Donanım timer/alarm tabanlı pulse üretimi uygula; ana USB döngüsünü bloklama.
- [ ] Hız ve ivme sınırlı profil uygula.
- [ ] Her eksen için ayrı durum makinesi oluştur: `DISABLED`, `HOMING/REFERENCE`, `IDLE`, `MOVING`, `SETTLING`, `FAULT`.
- [ ] ENA aktif seviyesini board config'ten al.
- [ ] PAN/TILT soft limitlerini firmware tarafında da uygula.
- [ ] Limit ve enkoder sapmasında hareketi durdur.
- [ ] Encoder count wrap/overflow kontrolü ekle.
- [ ] A/B yönü ve gerçek hareket yönünü karşılaştır.
- [ ] Komut hedefi ile enkoder hedefi arasındaki sapmayı zaman ve açı eşiğiyle fault yap.
- [ ] Sıfır referans prosedürü ekle; referanslanmamış eksende LIVE hareketi reddet.
- [ ] TILT enerjisi kesildiğinde mekanik düşme riskini donanım tasarımıyla birlikte ele al; yazılım tek koruma sayılmasın.

## Dosyalar

- `firmware/pico/include/motion_controller.hpp` (yeni)
- `firmware/pico/src/motion_controller.cpp` (yeni)
- `firmware/pico/include/encoder_monitor.hpp` (yeni)
- `firmware/pico/src/encoder_monitor.cpp` (yeni)
- `firmware/pico/src/pico_main.cpp`
- `firmware/pico/tests/host_tests.cpp`
- `backend/src/gokkalkan_backend/can_protocol.py`
- `backend/src/gokkalkan_backend/hardware_adapter.py`
- `tests/test_hardware_adapter.py`
- `tests/test_usb_serial_transport.py`

## Test sırası

1. Host unit test
2. Osiloskopla STEP/DIR/ENA, DM542 bağlı değil
3. DM542 + motor, mekanizmadan ayrı/düşük akım
4. Tek eksen mekanik HIL
5. İki eksen eşzamanlı HIL
6. Enkoder ve limit fault injection

## Zorunlu senaryolar

- [ ] `+1°`, `-1°`, sıfır hareket, maksimum izinli tek komut
- [ ] Hedef soft limit dışında
- [ ] Hard limit hareket sırasında aktif
- [ ] Encoder ters yön
- [ ] Encoder kablosu kopuk
- [ ] Motor sıkışmış, encoder hedefe ilerlemiyor
- [ ] USB hareket ortasında kopuyor
- [ ] Pico reset hareket ortasında oluşuyor
- [ ] Backend process yeniden başlıyor
- [ ] Komut sequence tekrarı veya eski komut

## Çıkış kriterleri

- [ ] PAN ve TILT komutları artık NACK değil, geçerli durumda ACK üretiyor.
- [ ] ACK yalnız komutun kabulünü, `completed` ise gerçek yerleşmeyi temsil ediyor; ikisi karıştırılmıyor.
- [ ] Encoder sıfır referansı olmadan fiziksel hareket yetkisi açılmıyor.
- [ ] USB/heartbeat kaybında hareket güvenli biçimde duruyor.
- [ ] Enkoder ve limit fault'ları telemetride ayrı kodlarla görülüyor.

---

# FAZ 3 — Airsoft kuru kontak ve fiziksel geri bildirim firmware'i

## Amaç

Pico'nun stok airsoft motor/ETU güç hattına dokunmadan yalnız galvanik izole normalde açık kuru kontağı, iki katmanlı yetki sonrası ve sınırlı süreyle sürmesi.

## Değişmez güvenlik kuralları

- Pico GPIO airsoft motoruna veya bataryasına doğrudan bağlanmaz.
- 24 V sistem barası airsoft ETU'ya bağlanmaz.
- Stok ETU/motor korumaları baypas edilmez.
- Kuru kontak normalde açıktır.
- 7,4 V airsoft dalı ayrı kapaklı sigorta ve T-Plug ara uzatma kullanır.
- E-Stop, DC motor/inrush değeri doğrulanmış ayrı kesme elemanı üzerinden yazılımdan bağımsız fiziksel kesme uygular.
- LP1K1210BD ana kontağı, airsoft 7,4 V DC hattında DC kesme değeri kanıtlanmadan kullanılmaz.
- İlk kabulde BB ve şarjör kullanılmaz.

## Görevler

- [ ] `FireOutput` sınıfını fiziksel GPIO'dan soyutla.
- [ ] Boot ve reset sırasında FIRE pinini pasif kur.
- [ ] Yetkili teknisyenin cihaz üzerinde doğruladığı stok SDU 2.0 düşük-akım tetik uçlarını as-built kayda işle; kamuya açık olmayan pinleri tahmin etme.
- [ ] Airsoft DC kesme elemanının modelini, bobin/sürücü gerilimini ve motor kalkış akımına uygun DC kontak değerini kaydet.
- [ ] Mevcut YL-314-C-T yalnız bu değerler kanıtlanırsa adaydır; aksi durumda fiziksel FIRE kapalı kalır.
- [ ] Airsoft stok sigorta değerini tespit et; bulunursa önce aynı değeri kullan. 20 A yalnız kontrollü ilk doğrulama değeridir ve ısınma ölçülmeden yükseltilmez.
- [ ] FIRE için `ARMED`, interlock kapalı, trigger released, encoder/motion sağlıklı koşullarını zorunlu tut.
- [ ] Mevcut 120 ms üst sınırını donanım zamanlayıcısı/monotonic zamanla uygula; ETU kuru test sonucu daha kısa süre yeterliyse kalibrasyonla azalt, doğrulama olmadan artırma.
- [ ] Ana döngü gecikse bile çıkışın 120 ms üstünde kalamayacağı ikinci koruma ekle.
- [ ] Trigger feedback'i FIRE öncesi, sırası ve sonrası kontrol et.
- [ ] Feedback beklenen sürede dönmezse `TRIGGER_FEEDBACK_STUCK` fault üret.
- [ ] Tek komutta tek pulse uygula; tekrar/duplicate sequence ikinci pulse üretmesin.
- [ ] Disarm, E-Stop, heartbeat kaybı ve Pico fault'unda FIRE'ı aynı tick'te kapat.
- [ ] Atış denemesi ile hedefin gerçekten imha edildiği bilgisini ayrı durumlar olarak modelle.

## Dosyalar

- `firmware/pico/include/fire_output.hpp` (yeni)
- `firmware/pico/src/fire_output.cpp` (yeni)
- `firmware/pico/src/pico_main.cpp`
- `firmware/pico/src/safety_state_machine.cpp`
- `backend/src/gokkalkan_backend/hardware_adapter.py`
- `backend/src/gokkalkan_backend/operator_api.py`
- `backend/src/gokkalkan_backend/mission_flow.py`
- `tests/test_hardware_adapter.py`
- `tests/test_phase4_safety.py`
- `tests/test_phase8_mission_flow.py`

## Mevcut mantık hatasının düzeltilmesi

`backend/src/gokkalkan_backend/operator_api.py:1403-1407`, hardware adapter FIRE'ı reddetse bile `record_engagement()` çağırabilir. Bu akış ayrılmalıdır:

```text
Safety Gate izin verdi
  → COMMAND_AUTHORIZED
MCU ACK verdi
  → FIRE_COMMAND_ACCEPTED
Pulse ve feedback tamamlandı
  → FIRE_PULSE_CONFIRMED
Hedef sonucu ayrı kanıtlandı
  → TARGET_RESULT_CONFIRMED
```

Hardware NACK, ACK timeout veya feedback fault durumunda hedef tamamlanmış sayılmamalıdır.

## Safe-load testleri

- [ ] PhotoMOS yerine LED/lamba ile pulse süresi
- [ ] FIRE öncesi interlock açık
- [ ] FIRE sırasında E-Stop
- [ ] FIRE sırasında USB kopması
- [ ] Trigger feedback baştan takılı
- [ ] Trigger feedback pulse sonrası serbest kalmıyor
- [ ] Aynı sequence iki kez geliyor
- [ ] Pico reset sonrası otomatik pulse olmadığı
- [ ] Gerçek kuru kontak, airsoft bağlı fakat BB/şarjör yok
- [ ] Ayrı 7,4 V sigorta ve DC kesme elemanı ile E-Stop fiziksel kesme
- [ ] YL-314-C-T kullanılıyorsa belgelenmiş DC değer + ilk kalkışta akım/sıcaklık kaydı

## Çıkış kriterleri

- [ ] FIRE fiziksel pulse süresi osiloskopla en fazla 120 ms ölçüldü.
- [ ] E-Stop ve heartbeat kaybı pulse'ı fiziksel olarak kesiyor.
- [ ] Duplicate/reconnect/reset ikinci istemsiz pulse oluşturmuyor.
- [ ] Hardware NACK görev akışını ilerletmiyor.
- [ ] BB ve şarjör olmadan kuru kontak/ETU kabulü kaydedildi.
- [ ] Airsoft sigorta değeri, DC kesme elemanı, T-Plug ara kablo ve stok tetik uçları as-built kayıtta tanımlı.

---

# FAZ 4 — USB status, encoder, E-Stop ve fault telemetrisi

## Amaç

Backend'in gerçek fiziksel durumu varsaymadan, Pico tarafından sürekli ve sequence-korumalı olarak alması.

## Mevcut uyumsuzluk

Pico status mesajı yalnız `outputs_enabled` durumunu `0x02` bitiyle gönderir (`firmware/pico/src/pico_main.cpp:53-58`). Backend ise `estopActive`, `motionOk`, `fireReady`, `watchdogOk`, fault ve ayrı encoder mesajı bekler (`backend/src/gokkalkan_backend/can_protocol.py:135-154`, `:194-215`).

## Görevler

- [ ] Status flag'lerini ICD ile birebir doldur.
- [ ] `estopActive` bitini PC817 `ESTOP_SAFE_SENSE` değerinin fail-closed tersinden üret; bu biti kontaktör durumu olarak kullanma.
- [ ] `0x201` E-Stop/`ESTOP_SAFE_SENSE` edge event gönder.
- [ ] `0x202` firmware/protokol sürüm mesajını açılışta ve istek üzerine gönder.
- [ ] `0x203` encoder mesajını PAN/TILT açıları ve health flag'leriyle gönder.
- [ ] Fault kodlarını kararlı enum ve insan-okunur açıklamayla eşle.
- [ ] Status ve encoder mesajları için yayın frekansını zaman bütçesine göre sabitle.
- [ ] Stale status/encoder durumunda backend'i fail-closed tut.
- [ ] ACK sonucu ile komutun tamamlanma bilgisini ayrılaştır.
- [ ] USB decoder rejected-frame sayısını health/telemetry'ye ekle.
- [ ] Bağımsız kontaktör geri bildirimi bulunmadığından `contactorEnergized` alanı uydurma; yalnız komut edilen durum ile gözlenen `ESTOP_SAFE_SENSE` değerini ayrı yayınla.

## Dosyalar

- `docs/usb_serial_mcu_protocol.md`
- `docs/can_icd_v1.md` (payload referansı; fiziksel CAN iddiası eklenmez)
- `firmware/pico/src/pico_main.cpp`
- `firmware/pico/include/can_protocol.hpp`
- `backend/src/gokkalkan_backend/can_protocol.py`
- `backend/src/gokkalkan_backend/usb_serial_adapter.py`
- `backend/src/gokkalkan_backend/hardware_adapter.py`
- `tests/test_usb_serial_transport.py`
- `tests/test_phase5_firmware.py`

## Testler

- [ ] Python ve C++ ortak golden vector testi
- [ ] Bit/flag kombinasyonları
- [ ] CRC8 payload + CRC16 stream bozulması
- [ ] Eksik, fazla uzun ve bilinmeyen mesaj
- [ ] Sequence tekrarı ve wrap-around
- [ ] Status stale
- [ ] Encoder stale
- [ ] E-Stop edge event kaybında periyodik status ile toparlama
- [ ] PC817 çıkış kablosu kopuk ve polarite ters-config senaryosu
- [ ] Firmware/protokol major mismatch

## Çıkış kriterleri

- [ ] Backend `fireReady` ve `encoderOk` değerlerini yalnız gerçek Pico mesajından alıyor.
- [ ] `UsbSerialMcuAdapter._fire_preflight_error()` geçerli fiziksel durumda başarılı, her fault senaryosunda bloklu.
- [ ] Python/C++ protokol vektörleri aynı byte dizilerini üretiyor.

---

# FAZ 5 — Gerçek LIVE bootstrap ve readiness kapısı

## Amaç

LIVE modunun bir config anahtarıyla değil, fiziksel kimlik ve sağlık kanıtıyla açılması.

## Mevcut durum

`backend/src/gokkalkan_backend/runtime_mode.py:107-138` LIVE için `LivePreflight` ister. Normal CLI ise bilinçli olarak bu preflight'ı üretmez (`backend/src/gokkalkan_backend/operator_http_server.py:485-487`). `config/runtime/live.toml` fiziksel Pico yolunu placeholder ve `live_output_enabled=false` tutar.

## Görevler

- [ ] Sunucuya kullanıcı girdisinden bağımsız `HardwareBootstrap` ekle.
- [ ] `/dev/serial/by-id/...` Pico kimliğini allowlist ile doğrula.
- [ ] Firmware/protokol sürümünü doğrula.
- [ ] Pico status'ını taze ve `SAFE/READY` durumda doğrula.
- [ ] Pico `ESTOP_SAFE_SENSE` geri bildirimini doğrula; bunun kontaktör ana-kutup geri bildirimi olmadığını readiness şemasında açık tut.
- [ ] Fiziksel START/kontaktör mühürleme kabul kaydını BOM/as-built revizyonuyla eşleştir.
- [ ] LIVE operatör prosedüründe fiziksel START adımını yazılım ARM'dan önce zorunlu sıraya koy; bağımsız runtime kontaktör sensörü olmadığı için bunu “ölçülmüş kontaktör durumu” olarak raporlama.
- [ ] Airsoft ayrı 7,4 V fiziksel kesme elemanı ve tetik feedback readiness'ini doğrula.
- [ ] Encoder, limit, kamera, perception, LiDAR ve disk readiness sağlayıcılarını birleştir.
- [ ] Kalibrasyon dosyaları `UNVERIFIED` ise LIVE arm'ı kapat.
- [ ] Gerçek BOM/as-built/config hash'lerini preflight kaynağına ekle.
- [ ] Preflight sonucunu salt okunur snapshot ve telemetri olayı olarak yayınla.
- [ ] HTTP istemcisinin `physical_interlock_ok` veya readiness değeri enjekte edemediğini test et.
- [ ] Reconnect sonrası yeniden preflight ve manuel arm zorunlu tut.

## Dosyalar

- `backend/src/gokkalkan_backend/hardware_bootstrap.py` (yeni)
- `backend/src/gokkalkan_backend/operator_http_server.py`
- `backend/src/gokkalkan_backend/runtime_mode.py`
- `backend/src/gokkalkan_backend/runtime_config.py`
- `backend/src/gokkalkan_backend/operator_api.py`
- `backend/src/gokkalkan_backend/doctor.py`
- `config/runtime/live.toml`
- `config/runtime/hil-physical.toml`
- `tests/test_runtime_mode.py`
- `tests/test_runtime_config.py`
- `tests/test_phase11_hil_release.py`

## Testler

- [ ] Placeholder serial path → server başlamaz
- [ ] `ttyACM0` → LIVE reddedilir
- [ ] Yanlış USB kimliği → reddedilir
- [ ] Firmware major mismatch → reddedilir
- [ ] E-Stop aktif → reddedilir
- [ ] `ESTOP_SAFE_SENSE` yok/kopuk → reddedilir
- [ ] Fiziksel mühürleme kabul kaydı veya airsoft DC kesme doğrulaması eksik → ilgili fiziksel yetki reddedilir
- [ ] Encoder/limit/perception/LiDAR stale → arm reddedilir
- [ ] `UNVERIFIED` calibration → arm reddedilir
- [ ] Tüm fiziksel kapılar geçerli → adapter oluşur fakat operatör hold-to-arm tamamlanmadan çıkış yok
- [ ] USB reconnect → otomatik arm yok

## Çıkış kriterleri

- [ ] Normal deploy edilen servis gerçek preflight ile LIVE başlatabiliyor.
- [ ] Yalnız config düzenleyerek güvenlik kapıları atlanamıyor.
- [ ] Her preflight girdisi fiziksel kaynak ve hash ile denetlenebilir.

---

# FAZ 6 — TFA50-L production runtime entegrasyonu

## Amaç

Mevcut TFA50-L serial/fusion sınıflarını test yardımcısı olmaktan çıkarıp gerçek Mission Core veri akışına bağlamak.

## Mevcut durum

- `backend/src/gokkalkan_backend/lidar_adapter.py` serial adapter içerir.
- `backend/src/gokkalkan_backend/range_fusion.py` yaw-track association yapar.
- `backend/src/gokkalkan_backend/sensor_pipeline.py` ikisini birleştirir.
- `OperatorService.apply_fused_range()` yalnız owner thread'de güvenilir karar uygular (`backend/src/gokkalkan_backend/operator_api.py:1799-1869`).
- Production `operator_http_server` bu pipeline'ı oluşturup çalıştırmaz.

## Görevler

- [ ] TFA adapter ve associator'ı runtime config'ten oluştur.
- [ ] Serial okuma için kontrollü worker oluştur; Mission Core state'ini worker'dan doğrudan değiştirme.
- [ ] Fusion kararını bounded Mission Core queue mesajına dönüştür.
- [ ] Seçili track bearing ve gerçek turret yaw'ı aynı monotonic zaman tabanında sağla.
- [ ] Stale, ambiguous, yaw-tolerance dışı ve calibration uyuşmazlığını fail-closed tut.
- [ ] Serial disconnect/reconnect durumunu health ve telemetriye aktar.
- [ ] LiDAR identity/firmware/mount revision allowlist kontrolü ekle.
- [ ] Kamera bbox mesafesinin Safety Gate menzili olarak kullanılamadığını sözleşmeyle zorunlu tut.
- [ ] Aynı LiDAR ölçümünün farklı track'lere uygulanmasını engelle.

## Dosyalar

- `backend/src/gokkalkan_backend/sensor_runtime.py` (yeni)
- `backend/src/gokkalkan_backend/sensor_pipeline.py`
- `backend/src/gokkalkan_backend/operator_http_server.py`
- `backend/src/gokkalkan_backend/mission_core.py`
- `backend/src/gokkalkan_backend/operator_api.py`
- `backend/src/gokkalkan_backend/runtime_config.py`
- `tests/test_phase9_sensor_fusion.py`
- `tests/test_mission_core.py`

## Testler

- [ ] `loop://` serial parser ve reconnect
- [ ] Kısmi UART frame
- [ ] CRC/protokol hatası
- [ ] Stale track
- [ ] Stale turret yaw
- [ ] Yaw tolerance dışı hedef
- [ ] Aynı anda iki aday hedef
- [ ] Yanlış mount revision
- [ ] Owner-thread dışı state mutation denemesi
- [ ] 5/10/15 m sabit hedef fiziksel ölçüm seti

## Çıkış kriterleri

- [ ] Production servis TFA50-L verisini otomatik okuyor.
- [ ] Yalnız kabul edilmiş fusion kararı track `rangeM` değerini güncelliyor.
- [ ] LiDAR kopması veya stale veri FIRE yetkisini kapatıyor.
- [ ] 5/10/15 m kalibrasyon raporu `physicalGatePassed=true` olmadan LIVE arm açılmıyor.

---

# FAZ 7 — Kamera kalibrasyonu, aim alignment ve taret geri beslemesi

## Amaç

Kamera piksel merkezinin gerçek taret yaw/pitch hata komutuna izlenebilir ve kalibre edilmiş biçimde dönüştürülmesi.

## Mevcut durum

`perception/src/aim_alignment.py` kalibre yaw/pitch hata hesabı içerir; fakat production angajman akışında kullanılmaz. `FrameProcessor` API'ye yatay `bearingDeg` gönderir, dikey aim hatasını göndermez (`perception/src/frame_processor.py:74-93`).

## Görevler

- [ ] Kamera intrinsics calibration için capture ve evaluation komutu ekle.
- [ ] Principal point, distortion ve yatay/dikey FoV değerlerini versioned calibration dosyasında tut.
- [ ] Kamera–taret boresight yaw/pitch ofsetini ölç.
- [ ] Track mesajına kalibre `yawErrorDeg`, `pitchErrorDeg`, calibration id/hash ve freshness ekle.
- [ ] `receiveMonotonicNs` stale kontrolünü backend'de de uygula.
- [ ] Weapon pitch'i takip etmeyen kamera/LiDAR köprüsü geometrisini taret açısıyla birleştir.
- [ ] Aim komutunu mutlak hedef açıya çevirmeden önce soft zone kontrolü uygula.
- [ ] Kalibrasyon id/hash uyuşmazlığında otonom hareketi kapat.

## Dosyalar

- `config/calibration/camera.toml` (yeni)
- `perception/src/aim_alignment.py`
- `perception/src/frame_processor.py`
- `perception/src/perception_bridge.py`
- `backend/src/gokkalkan_backend/messages.py`
- `backend/src/gokkalkan_backend/operator_api.py`
- `tests/test_phase9_sensor_fusion.py`
- `tests/test_perception_bridge.py`

## Testler

- [ ] Merkez piksel → yaklaşık sıfır yaw/pitch hata
- [ ] Sol/sağ ve yukarı/aşağ işaret yönleri
- [ ] Distortion sınırındaki hedef
- [ ] Stale track
- [ ] Calibration hash mismatch
- [ ] Kamera yaw hareketini izlerken weapon pitch'in ayrı hareketi
- [ ] Basılı hedeflerle farklı uzaklık/açı saha testi

## Çıkış kriterleri

- [ ] Kamera kalibrasyonu `ACTIVE`, id/hash ve ölçüm kanıtına sahip.
- [ ] Aim hatası hem yaw hem pitch için üretiliyor.
- [ ] Stale veya kalibrasyonsuz track otonom hareket/ateş yetkisi alamıyor.

---

# FAZ 8 — Otonom takip ve angajman denetleyicisi

## Amaç

Aşama 2 ve Aşama 3'te operatörün tek tek aim/fire butonuna basmasına ihtiyaç duymayan, Mission Core sahibi ve fail-closed bir kontrol döngüsü oluşturmak.

## Mimari kural

Otonom controller donanım adapter'ını veya global state'i ayrı thread'den doğrudan değiştirmemelidir. Tick/event, mevcut tek-sahipli Mission Core kuyruğunda işlenmelidir.

## Önerilen durum makinesi

```text
IDLE
 → ACQUIRE_TARGET
 → TRACKING
 → AIMING
 → SETTLING
 → RANGE_AND_IDENTITY_GATE
 → FIRE_AUTHORIZATION
 → FIRE_IN_PROGRESS
 → VERIFY_OUTPUT
 → REASSESS_TARGET
 → NEXT_TARGET / FAULT / HOLD
```

Her durumda E-Stop, mission stop, maintenance, health veya stale veri doğrudan `HOLD/FAULT` yoluna gidebilmelidir.

## Görevler

- [ ] Otonom controller'ı saf state transition mantığı ve side-effect executor olarak ayır.
- [ ] Hedef seçiminde `MissionFlow.selected_target_id` kullan.
- [ ] Stage 2'de dost olduğu kesin hedefi koru; hedef tipi gerektirme.
- [ ] Stage 3'te yalnız `Düşman` + bilinen tip + geçerli menzil kombinasyonunu kabul et.
- [ ] Track freshness ve confidence kapıları ekle.
- [ ] Yaw/pitch aim hatasından bounded hareket komutu üret.
- [ ] Her tick'te maksimum açı/hız değişimini sınırla.
- [ ] Encoder yerleşme ve titreşim/settling koşulu sağlanmadan FIRE açma.
- [ ] LiDAR menzili aynı track ile eşleşmeden FIRE açma.
- [ ] Balistik düzeltmeyi yalnız aktif calibration tablosu içinde uygula.
- [ ] Forbidden movement/fire zone'u her yeni hedef açısında yeniden değerlendir.
- [ ] Komut correlation id ile aim → settle → fire zincirini izlenebilir yap.
- [ ] Hardware NACK/timeout durumunda hedefi tamamlanmış sayma.
- [ ] Tek hedefte maksimum deneme/cooldown politikasını config ile sınırla.
- [ ] Mission stop, maintenance ve mode change durumunda controller state'ini temizle ve disarm et.
- [ ] Reconnect sonrası eski hedef/komutu devam ettirme; yeniden acquire zorunlu tut.

## Dosyalar

- `backend/src/gokkalkan_backend/autonomous_controller.py` (yeni)
- `backend/src/gokkalkan_backend/mission_core.py`
- `backend/src/gokkalkan_backend/mission_flow.py`
- `backend/src/gokkalkan_backend/operator_api.py`
- `backend/src/gokkalkan_backend/safety_gate.py`
- `backend/src/gokkalkan_backend/messages.py`
- `config/runtime/*.toml`
- `tests/test_autonomous_controller.py` (yeni)
- `tests/test_phase8_mission_flow.py`
- `tests/test_scenarios.py`
- `tests/test_digital_twin.py`

## Unit ve simülasyon testleri

- [ ] Aşama 2: üç koldan hedef, en yakın geçerli hedef seçimi
- [ ] Aşama 2: hedef tipi `Bilinmeyen`, yine de dost değilse takip edilebilir
- [ ] Aşama 3: dost hedef daha yakın olsa bile seçilmez
- [ ] Aşama 3: F16 10 m altında FIRE yok
- [ ] Aşama 3: Helikopter/Balistik Füze 5 m altında FIRE yok
- [ ] Aşama 3: Mini/Micro İHA 0–15 m kuralı
- [ ] Track aim sırasında stale oluyor
- [ ] LiDAR başka track ile eşleşiyor
- [ ] Encoder settling oluşmuyor
- [ ] Forbidden zone hedefin yolu üzerinde
- [ ] FIRE ACK timeout
- [ ] E-Stop aim sırasında
- [ ] E-Stop fire pulse sırasında
- [ ] Mode autonomous → manual geçişi
- [ ] Maintenance request sırasında otonom hareket
- [ ] Bir hedef için tekrar deneme sınırı

## Çıkış kriterleri

- [ ] Otonom mod operatör aim/fire komutu olmadan dijital ikiz senaryosunu tamamlıyor.
- [ ] Controller yalnız Mission Core owner thread üzerinden state/hardware side effect üretiyor.
- [ ] Her transition ve blok nedeni telemetride correlation id ile izleniyor.
- [ ] Hiçbir hardware ret sonucu hedef tamamlanmış sayılmıyor.

---

# FAZ 9 — Hedef tipi sınıflandırma ve Hailo-8 inference

## Amaç

Aşama 3 için hedef tipini gerçek basılı hedef verisiyle belirlemek ve seçilen modeli AI HAT+ 26 TOPS/Hailo-8 üzerinde çalıştırmak.

## Mevcut durum

`perception/src/frame_processor.py:396-403` hedef tipini bilerek `Bilinmeyen` bırakır. `perception/src/accelerator.py:1-6` yalnız donanım/model varlığını raporlar; inference yapmaz.

## Görevler

- [ ] Gerçek basılı hedef capture oturumlarını farklı mesafe, açı ve ışıkta topla.
- [ ] Train/validation/test ayrımını capture session bazında yap.
- [ ] HSV/template baseline ve YOLOv8n baseline'ı aynı test setinde karşılaştır.
- [ ] Yanlış dost/düşman ve hedef tipi hatalarını ayrı metrikle raporla.
- [ ] Kazanan modeli HEF'e dönüştür ve hash/model card oluştur.
- [ ] `Detector` protocol/interface tanımla.
- [ ] CPU baseline ve `HailoDetector` implementasyonu ekle.
- [ ] Hailo scheduler/stream'i kamera capture döngüsünü bloklamayacak biçimde bounded latest-wins tasarla.
- [ ] Detection sonuçlarını mevcut tracker kimlikleriyle eşle.
- [ ] Model stale/timeout/crash durumunda perception heartbeat'i fail-closed sağlıksız yap.
- [ ] Model hash ve calibration hash'i session manifestine ekle.
- [ ] `deploy/systemd/gokkalkan-perception.service` içindeki sabit `--stage 2` davranışını backend stage state ile senkronize et.

## Dosyalar

- `perception/src/detector.py` (yeni)
- `perception/src/hailo_detector.py` (yeni)
- `perception/src/frame_processor.py`
- `perception/src/perception_bridge.py`
- `perception/src/accelerator.py`
- `perception/models/target_detector_contract.json`
- `perception/models/README.md`
- `perception/tools/train_yolo.py`
- `deploy/systemd/gokkalkan-perception.service`
- `tests/test_accelerator.py`
- `tests/test_perception_bridge.py`
- `tests/test_phase9_sensor_fusion.py`

## Kabul metrikleri

Metrik eşikleri gerçek validation set sonuçlarına göre model card'da kilitlenmelidir. En az aşağıdakiler ayrı raporlanmalıdır:

- Sınıf başına precision/recall
- Dost hedefi düşman olarak işaretleme sayısı
- Hedef tipi confusion matrix
- 5/10/15 m ve açı/ışık dilimlerine göre performans
- Pi 5 + Hailo-8 p50/p95 inference latency
- Capture → backend track update uçtan uca p50/p95 latency
- Dropped frame ve stale track oranı

## Çıkış kriterleri

- [ ] Model yalnız sentetik smoke verisiyle değil gerçek session-separated veriyle doğrulandı.
- [ ] Hailo-8 üzerinde gerçek inference kanıtı alındı.
- [ ] Model crash/timeout FIRE yetkisini kapatıyor.
- [ ] Aşama 3 target type bilgisi artık `Bilinmeyen` sabitinden gelmiyor.

---

# FAZ 10 — Taret ve airsoft fiziksel kalibrasyonu

## Amaç

Kodun varsayım yerine imal edilmiş mekanizmanın ölçülmüş davranışını kullanması.

## Mevcut dosyalar

- `config/calibration/turret.toml` → `UNVERIFIED`, sample count `0`
- `config/calibration/tfa50_l.toml` → `UNVERIFIED`, verified range yok
- `config/calibration/airsoft_trajectory.toml` → `UNVERIFIED`, nokta yok
- Kamera için ayrı aktif calibration dosyası henüz yok

## Görevler

- [ ] PAN motor step/degree ve encoder count/degree ölç.
- [ ] TILT motor step/degree ve encoder count/degree ölç.
- [ ] PAN/TILT sıfır, gain, offset ve mekanik limitleri kaydet.
- [ ] Kamera principal point, distortion ve boresight ofsetini kaydet.
- [ ] TFA50-L 5/10/15 m ölçüm setini kaydet.
- [ ] LiDAR mount revision ve gerçek yaw/pitch ofsetini kaydet.
- [ ] Airsoft trajectory testini güvenli saha prosedürüyle farklı menzillerde kaydet.
- [ ] Menzil–elevation tablosunu en az iki nokta yerine kullanılan tüm kritik menzil bantlarını kapsayacak şekilde oluştur.
- [ ] Calibration id, tarih, operatör, donanım revizyonu ve ham veri hash'ini yaz.
- [ ] Calibration aralığı dışında otomatik extrapolation yapma.
- [ ] Her mekanik değişiklikte calibration'ı `STALE` yapacak revizyon kontrolü ekle.

## Dosyalar

- `config/calibration/turret.toml`
- `config/calibration/tfa50_l.toml`
- `config/calibration/airsoft_trajectory.toml`
- `config/calibration/camera.toml`
- `backend/src/gokkalkan_backend/calibration_workflow.py`
- `backend/src/gokkalkan_backend/turret_calibration.py`
- `backend/src/gokkalkan_backend/ballistic_compensation.py`
- `perception/src/aim_alignment.py`
- `tests/test_turret_calibration.py`
- `tests/test_ballistic_compensation.py`

## Çıkış kriterleri

- [ ] Hiçbir LIVE calibration `UNVERIFIED` değil.
- [ ] Her calibration dosyası ham veri/evidence hash'ine sahip.
- [ ] Kullanılan kart, mekanik ve sensör revizyonları calibration ile birebir eşleşiyor.
- [ ] Tablo aralığı dışı menzil FIRE yetkisi almıyor.

---

# FAZ 11 — Operatör paneli, health ve müdahale edilebilirlik

## Amaç

Fiziksel sistemin neden hareket ettiği, neden hareket etmediği ve hangi sensör/kapının yetkiyi kestiğinin operatör tarafından anında anlaşılması.

## Görevler

- [ ] USB cihaz kimliği, firmware, heartbeat ve rejected-frame sayısını göster.
- [ ] PAN/TILT komut açısı, encoder açısı, sapma ve limit durumunu göster.
- [ ] E-Stop kanalı, interlock, trigger feedback ve FIRE output durumunu göster.
- [ ] LiDAR serial/identity/firmware/range age/fusion reason alanlarını göster.
- [ ] Kamera/perception/model hash, inference health ve track freshness göster.
- [ ] Otonom controller state ve son transition nedenini göster.
- [ ] `COMMAND_AUTHORIZED`, `ACK`, `COMPLETED`, `TARGET_RESULT` ayrı göster.
- [ ] Fault sonrası kontrollü reset adımlarını UI'da sıralı göster.
- [ ] Bakım modunda fiziksel output'un kapalı olduğunu backend-otoriter göster.
- [ ] Blok nedenlerinin Türkçe ve tekil hata kodu eşlemesini test et.

## Dosyalar

- `frontend/src/OperatorPanel.tsx`
- `frontend/src/operatorContracts.ts`
- `frontend/src/operatorApiClient.ts`
- `frontend/src/components/SafetyAuthorityPanel.tsx`
- `frontend/src/components/EventStream.tsx`
- `backend/src/gokkalkan_backend/operator_api.py`
- `backend/src/gokkalkan_backend/messages.py`
- ilgili frontend ve backend testleri

## Çıkış kriterleri

- [ ] Operatör herhangi bir blok için hangi fiziksel/yazılımsal kapının kapandığını tek ekranda görebiliyor.
- [ ] UI hiçbir fiziksel health bilgisini yerel olarak uydurmuyor.
- [ ] UI kapalı olsa bile backend/Pico Safety Gate uygulanmaya devam ediyor.

---

# FAZ 12 — Kademeli HIL ve saha kabulü

## Amaç

Host testlerinden fiziksel sisteme kontrollü geçmek ve her seviyede bir sonraki enerji/tehlike seviyesine geçişi kanıta bağlamak.

## A. Monitor-only HIL

- [ ] Pico USB CDC enumerate oluyor.
- [ ] Kararlı `/dev/serial/by-id/...` yolu kaydedildi.
- [ ] Status/firmware/encoder/E-Stop mesajları geliyor.
- [ ] PC817 `X=24 V`, `X=0 V` ve çıkış-kablo-kopuk durumları doğru `estopActive` üretiyor.
- [ ] USB disconnect/reconnect otomatik arm oluşturmuyor.
- [ ] 250 ms heartbeat fault'u ölçüldü.
- [ ] Pico watchdog reset davranışı kaydedildi.
- [ ] Motor ve FIRE fiziksel olarak ayrı.

## B. Yapay yük HIL

- [ ] STEP/DIR/ENA osiloskopla doğrulandı.
- [ ] FIRE yerine LED/lamba pulse testi yapıldı.
- [ ] E-Stop fiziksel çıkışı yazılımdan bağımsız kesiyor.
- [ ] E-Stop bırakılmışken kontaktör START olmadan çekmiyor.
- [ ] START basılınca kontaktör çekiyor; START bırakılınca yardımcı 1NA mühürleme sürdürüyor.
- [ ] E-Stop basılınca kontaktör düşüyor; E-Stop bırakıldığında START'sız yeniden çekmiyor.
- [ ] START butonu bırakıldığında elektriksel olarak açık ve yayla geri dönüyor; takılı/kapalı buton kabul edilmiyor.
- [ ] Kontaktör bobini devreye girerken USB framing/reconnect testi yapıldı.
- [ ] Motor sürücü enerjilenirken EMI testi yapıldı.

## C. Motor HIL

- [ ] PAN tek eksen düşük hız
- [ ] TILT tek eksen mekanik destekli düşük hız
- [ ] İki eksen eşzamanlı hareket
- [ ] Hard limit ve soft limit
- [ ] Encoder ters yön/kopuk/sapma
- [ ] Motor sıkışma senaryosu
- [ ] Hareket sırasında E-Stop
- [ ] Hareket sırasında backend/Pico reset

## D. Airsoft kuru test

- [ ] Batarya ve 24 V alanlarının ayrılığı ölçüldü.
- [ ] T-Plug ara uzatma, ayrı kapaklı sigorta ve sigorta değeri kaydedildi.
- [ ] DC kesme elemanının motor/inrush değeri doğrulandı; YL-314-C-T kullanılıyorsa kanıtı eklendi.
- [ ] Galvanik izolasyon ölçüldü.
- [ ] BB ve şarjör yok.
- [ ] Kuru kontak pulse ve feedback doğrulandı.
- [ ] E-Stop fiziksel airsoft yetkisini kesiyor.
- [ ] Reset/reconnect istemsiz pulse oluşturmuyor.

## E. Manuel Mod kabulü

- [ ] Aşama 1 mod geçişi operatör denetiminde.
- [ ] Deadman olmadan hareket yok.
- [ ] Manuel aim encoder ile doğrulanıyor.
- [ ] FireIntent yalnız seçili hedef/güvenlik koşullarında iletiliyor.
- [ ] Hardware NACK UI ve telemetride başarısız görülüyor.

## F. Aşama 2 kabulü

- [ ] Sistem tek mod komutundan sonra hedefleri kendisi acquire ediyor.
- [ ] Hedef tipi bilinmese de Aşama 2 kuralı uygulanıyor.
- [ ] Üç koldaki hedefler için takip/aim/fire döngüsü operatör aim/fire olmadan ilerliyor.
- [ ] Track kaybında FIRE kapanıyor.
- [ ] Her tur ve hedef telemetride ayrı izleniyor.

## G. Aşama 3 kabulü

- [ ] Dost hedefler farklı açı/menzillerde FIRE yetkisi alamıyor.
- [ ] Düşman hedef tipi model tarafından belirleniyor.
- [ ] F16, Helikopter/Balistik Füze ve Mini/Micro İHA menzil kapıları doğrulanıyor.
- [ ] Yanlış/kararsız sınıflandırmada FIRE kapanıyor.
- [ ] LiDAR ve track association kaybında FIRE kapanıyor.

## Çıkış kriterleri

- [ ] Her HIL seviyesi için `physicalGatePassed` kanıtı ayrı oluşturuldu.
- [ ] Önceki seviye geçmeden sonraki tehlike seviyesi denenmedi.
- [ ] Testte kullanılan firmware, config, calibration ve model hash'leri kaydedildi.

---

# FAZ 13 — Deploy, soak, release ve geri dönüş

## Amaç

Laboratuvar kabulünden sonra aynı yazılım/firmware/config kombinasyonunun Raspberry Pi üzerinde tekrarlanabilir biçimde kurulması ve geri alınabilmesi.

## Görevler

- [ ] Pico firmware sürümünü release manifestine ekle.
- [ ] Pi package/venv lock ve frontend dist hash'ini kaydet.
- [ ] Runtime config, calibration ve model hash'lerini release manifestine ekle.
- [ ] `systemd` servis sıralamasına sensor runtime ve gerçek bootstrap lifecycle'ını dahil et.
- [ ] Graceful shutdown sırasında disarm/stop doğrula.
- [ ] Process crash/restart sırasında otomatik arm olmadığını doğrula.
- [ ] Disk doluluğu, telemetry rotation ve evidence export testlerini çalıştır.
- [ ] Uzun süreli soak testinde heartbeat, serial reconnect, frame drop ve memory/disk trendlerini kaydet.
- [ ] Bilinen iyi sürüme rollback prosedürü yaz ve test et.
- [ ] Release manifest için software + sensor + HIL kapılarını birlikte zorunlu tut.

## Dosyalar

- `deploy/systemd/*.service`
- `deploy/pi/manifest.toml`
- `scripts/bootstrap_pi.sh`
- `scripts/verify_pi_manifest.py`
- `backend/src/gokkalkan_backend/release_gate.py`
- `backend/src/gokkalkan_backend/hil_runner.py`
- `tests/test_phase10_quality_gates.py`
- `tests/test_phase11_hil_release.py`

## Zorunlu komutlar

```bash
.venv/bin/python -m pytest
.venv-perception/bin/python -m pytest \
  tests/test_phase9_sensor_fusion.py tests/test_dataset_pipeline.py

cmake -S firmware/pico -B build/firmware-host -G Ninja
cmake --build build/firmware-host
ctest --test-dir build/firmware-host --output-on-failure

npm run dev:check
npm run typecheck
npm run build

python3 scripts/verify_pi_manifest.py --manifest-only
.venv/bin/gokkalkan doctor --config <saha-config> --strict
```

Fiziksel cihaz bulunmayan geliştirme makinesinde `doctor --strict` veya LIVE/HIL fiziksel testinin geçmesi beklenmez. Bu testler Pi ve doğru donanım revizyonunda ayrı kanıtlanmalıdır.

## Çıkış kriterleri

- [ ] Release manifestindeki software, sensor ve HIL kapıları `true`.
- [ ] Release bileşenlerinin hash'leri HIL kabulüyle aynı.
- [ ] Rollback prosedürü gerçekten uygulandı ve tekrar ileri sürüm kurulabildi.
- [ ] Fiziksel kabul kanıtı olmadan “LIVE hazır” iddiası üretilmiyor.

---

## 6. Test matrisi

| Alan | Unit | Entegrasyon | HIL | Saha |
|---|---|---|---|---|
| USB framing | C++/Python golden vectors | `loop://`, reconnect | Pi↔Pico USB | Motor/kontaktör EMI |
| Safety state | State transition testleri | Backend + adapter | Tek NK E-Stop, PC817, START/mühürleme, interlock/feedback | Kontrollü saha prosedürü |
| Motion | Step profile/limit/encoder | Digital twin | DM542 + motor + encoder | Hedefleme tekrarı |
| Airsoft | Pulse/duplicate/fault | Adapter ACK state | LED, sonra kuru kontak | Kontrollü menzil testi |
| LiDAR | Parser/association | Mission Core queue | TFA50-L 5/10/15 m | Hareketli hedef association |
| Kamera | Tracking/alignment | Perception bridge | Pi Camera 3 | Işık/açı/mesafe |
| AI HAT+ | Detector contract | Model + tracker | Hailo-8 inference | Gerçek hedef metriği |
| Otonomluk | State transitions | Digital twin stages | Motor/sensor HIL | Aşama 2/3 prova |
| Telemetri | Schema/rotation | Replay/evidence | Fault injection log | Tam görev replay |

---

## 7. Fault injection kontrol listesi

Her release adayında en az aşağıdaki hatalar tekrar denenmelidir:

- [ ] Pi–Pico USB kablosu çekildi
- [ ] Pico resetlendi
- [ ] Backend kapandı/yeniden başladı
- [ ] Perception process kapandı
- [ ] LiDAR seri kablosu çekildi
- [ ] Kamera frame'i stale oldu
- [ ] AI model inference timeout verdi
- [ ] PAN encoder kablosu çekildi
- [ ] TILT encoder ters yön raporladı
- [ ] PAN/TILT limit aktif oldu
- [ ] Tek NK E-Stop hattı açıldı
- [ ] PC817 24 V girişi veya Pico çıkış kablosu kesildi
- [ ] E-Stop bırakıldı fakat START'a basılmadı
- [ ] START basılı tutuldu/takılı kaldı; test durduruldu ve buton reddedildi
- [ ] Airsoft DC kesme interlock'u açıldı
- [ ] Trigger feedback takılı kaldı
- [ ] Kontaktör devreye girdi ve EMI oluştu
- [ ] Telemetri diski minimum boş alan altına indi
- [ ] Calibration/model hash'i config ile uyuşmadı
- [ ] Eski/tekrar USB sequence gönderildi

Her senaryoda beklenen ortak sonuç:

```text
Fiziksel yetki kapanır
→ otomatik yeniden arm olmaz
→ hata kodu ve kaynak health alanında görülür
→ olay telemetriye yazılır
→ kontrollü reset prosedürü olmadan devam edilmez
```

Not: Tek kanallı mühürleme devresi, çift kanal uyuşmazlığı veya kontaktör ana kontak yapışmasını teşhis etmez. START takılı kalma testi bir “güvenle devam” testi değildir; böyle bir durumda enerji kesilir ve buton değiştirilir.

---

## 8. Kod inceleme kontrol listesi

Her faz PR/commit incelemesinde:

- [ ] Safety Gate UI'ya taşınmamış; backend/Pico'da uygulanıyor.
- [ ] Fiziksel komut yetkisi HTTP payload'dan gelmiyor.
- [ ] Monotonic zaman gereken yerde wall-clock kullanılmıyor.
- [ ] Worker thread Mission Core state'ini doğrudan değiştirmiyor.
- [ ] Queue bounded ve overload davranışı tanımlı.
- [ ] ACK, tamamlanma ve hedef sonucu ayrı durumlar.
- [ ] Stale/eksik/geçersiz veri fail-closed.
- [ ] Reconnect/reset otomatik arm oluşturmuyor.
- [ ] Yeni fault kodu test ve UI açıklamasına sahip.
- [ ] Yeni config alanı validasyon ve güvenli varsayılana sahip.
- [ ] Gerçek ölçüm yerine uydurma calibration eklenmemiş.
- [ ] Fiziksel test yapılmadıysa dokümanda yapılmış gibi yazılmamış.

---

## 9. Riskler ve azaltmalar

### R1 — Pin haritası ile imal edilen kartın farklı olması

**Sonuç:** Yanlış motor yönü veya istemsiz FIRE.

**Azaltma:** Board revision + compile-time pin map + iki kişili as-built kontrol + boot osiloskop testi.

### R2 — USB'nin motor/kontaktör EMI ortamında kopması

**Sonuç:** Kontrol kaybı.

**Azaltma:** Kısa veri kablosu, ayrı güzergâh, strain relief, heartbeat fault, otomatik re-arm yasağı, fiziksel EMI HIL. USB kabulü başarısız olursa ADR-005'teki yedek RS-485 kararı ayrı değerlendirilir; test yapılmadan taşıma yeniden değiştirilmez.

### R3 — Step sayısının gerçek açı sanılması

**Sonuç:** Yanlış hedefleme ve güvensiz hareket.

**Azaltma:** Enkoder otoritesi, zero reference, deviation fault, settling kapısı.

### R4 — FIRE ACK'nin hedef imhası sanılması

**Sonuç:** Görev akışı yanlış ilerler.

**Azaltma:** Authorization, ACK, pulse feedback ve target result durumlarını ayır.

### R5 — Kamera bbox menzilinin Safety Gate'te kullanılması

**Sonuç:** Yanlış menzilde atış.

**Azaltma:** Yalnız kalibre TFA50-L fusion sonucu FIRE menzili olabilir; bbox range test/görselleştirme olarak etiketlenir.

### R6 — Sentetik model testinin saha başarısı sanılması

**Sonuç:** Aşama 3'te yanlış hedef tipi/dost-düşman.

**Azaltma:** Gerçek session-separated veri, saha dilimleri, Hailo latency ve confusion matrix release kapısı.

### R7 — Fiziksel calibration'ın mekanik revizyon sonrası geçersiz kalması

**Sonuç:** Sistem eski ofsetlerle çalışır.

**Azaltma:** Calibration dosyasına board/mount/mechanical revision; mismatch'te `STALE` ve LIVE block.

### R8 — Asgari tek kanallı mühürleme devresinin teşhis sınırı

**Sonuç:** Tek NK E-Stop devresi çift kanal uyuşmazlığını, kontaktör ana-kutup yapışmasını veya START kontağının yapışmasını kendi başına teşhis edemez.

**Azaltma:** Bu mimariyi SIL/çift kanallı olarak tanımlama; her oturum öncesi E-Stop dört-adım ve START geri-dönüş testi yap; kontaktörün fiziksel düşmesini gözle; PC817 kablo-kopuk testini uygula; başarısız parçayla devam etme. Yazılım `ESTOP_SAFE_SENSE` değerini kontaktör geri bildirimi gibi göstermemelidir.

### R9 — Airsoft DC kesme elemanının değeri belirsiz

**Sonuç:** Kontak kaynaşması, ısınma veya E-Stop'ta 7,4 V airsoft enerjisinin kesilememesi.

**Azaltma:** Stok sigorta değerini ve motor kalkış akımını ölç; DC motor/inrush değeri belgeli kesme elemanı kullan; YL-314-C-T'yi etiketi/verisi doğrulanmadan kabul etme; BB/şarjörsüz E-Stop ve sıcaklık testi geçmeden FIRE açma.

### R10 — Yazılım kontaktörün çektiğini doğrudan göremiyor

**Sonuç:** `ESTOP_SAFE_SENSE`, E-Stop bırakıldığında `true` olabilir; fakat START'a basılmadığı için kontaktör hâlâ kapalı olabilir. Tersi yönde, yazılım ARM edilmişken sonradan START'a basılması sürücü enerjisini beklenmeyen sırada açabilir.

**Azaltma:** Saha sırasını `E-Stop bırak → fiziksel START → yazılım RESET → hold-to-arm` olarak kilitle; E-Stop edge'inde Pico'yu latched `FAULT` yap; UI yalnız `safetyChainOk` göstersin, `contactorEnergized` göstermesin. İleride runtime kontaktör kanıtı istenirse ayrıca izole bobin/switched-output sense eklenir; mevcut PC817 `X` ölçümü bu kanıt yerine kullanılamaz.

---

## 10. Ana ilerleme tablosu

| Kilometre taşı | Durum | Sorumlu | Kanıt | Sonraki kapı |
|---|---|---|---|---|
| M0 Pin/as-built freeze | [ ] |  |  | Monitor-only firmware |
| M1 Pico safe I/O | [ ] |  |  | Motor/FIRE çıkış kodu |
| M2 Motor + encoder HIL | [ ] |  |  | Manuel hareket |
| M3 Airsoft safe-load HIL | [ ] |  |  | Manuel FIRE |
| M4 USB status + LIVE bootstrap | [ ] |  |  | Fiziksel LIVE arm |
| M5 Manuel Mod kabul | [ ] |  |  | Aşama 1 |
| M6 LiDAR + camera fusion | [ ] |  |  | Otonom range gate |
| M7 Otonom controller | [ ] |  |  | Aşama 2 |
| M8 Aşama 2 kabul | [ ] |  |  | Hedef tipi |
| M9 Hailo hedef tipi + Aşama 3 | [ ] |  |  | Final release |
| M10 Release/rollback/soak | [ ] |  |  | Saha hazırlığı |

---

## 11. Bir sonraki uygulanacak iş

Bu plan üzerinden ilk uygulama dilimi **FAZ 0 + FAZ 1** olmalıdır:

1. İmal edilen/edilecek I/O kartının revizyonunu ve kesin pin haritasını repoya aktar.
2. Pin haritası henüz kesinleşmemişse aktüatör GPIO'larını açmadan HAL ve host-test iskeletini geliştir.
3. PC817 `ESTOP_SAFE_SENSE`, airsoft interlock, trigger feedback ve limit girişlerini fail-closed modele ekle.
4. Host testlerini geçir.
5. Fiziksel kart geldiğinde yalnız monitor-only GPIO kabulü yap.

**FAZ 0 tamamlanmadan gerçek STEP/DIR/ENA veya FIRE pin numarası tahmin edilmemelidir.**

---

## 12. Tamamlandı iddiası için son kontrol

Aşağıdakilerden biri eksikse sistem “%100 entegre” olarak raporlanmamalıdır:

- [ ] Pico fiziksel actuator firmware'i
- [ ] Motor/encoder/limit HIL
- [ ] Airsoft safe-load ve kuru kontak kabulü
- [ ] Tek NK E-Stop + START + LP1K1210BD mühürleme ve PC817 `ESTOP_SAFE_SENSE` kanıtı
- [ ] Airsoft ayrı 7,4 V sigorta ve DC uygun fiziksel kesme kanıtı
- [ ] USB disconnect/reconnect/EMI kabulü
- [ ] Gerçek LIVE bootstrap
- [ ] Production LiDAR fusion
- [ ] Kamera/taret calibration
- [ ] Airsoft trajectory calibration
- [ ] Aşama 2 otonom aim/fire döngüsü
- [ ] Aşama 3 hedef tipi ve dost/düşman saha metriği
- [ ] Pi 5 + Camera + Hailo-8 fiziksel runtime kanıtı
- [ ] Full fault-injection matrisi
- [ ] Release manifest, soak ve rollback kanıtı
