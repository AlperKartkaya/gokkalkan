# Gökkalkan Pico firmware

Bu dizin güvenlik durum makinesini, tarihsel CAN v1 payload codec'ini ve aktif
USB CDC Serial taşımasını içerir. USB byte stream'i COBS+CRC16 ile çerçevelenir.

## Host testi

```sh
cmake -S firmware/pico -B build/firmware-host -G Ninja
cmake --build build/firmware-host
ctest --test-dir build/firmware-host --output-on-failure
```

## Pico SDK derleme ve flash

```sh
export PICO_SDK_PATH=/opt/pico-sdk
cmake -S firmware/pico -B build/firmware-pico -G Ninja -DGOKKALKAN_BUILD_PICO=ON
cmake --build build/firmware-pico
picotool load -f build/firmware-pico/gokkalkan_pico.uf2
```

Pin haritası ve gerçek kart revizyonu onaylanmadan actuator çıkışları açılmaz.
Host testi fiziksel E-Stop, watchdog ve motor kesme kanıtı değildir; bunlar HIL
ve saha kabulünde ayrıca doğrulanacaktır.

Güvenlik çekirdeği FIRE için kapalı fiziksel interlock ve serbest tetik geri
bildirimi ister; kuru-kontak çıkışını 120 ms ile sınırlar. Interlock kopması,
takılı tetik geri bildirimi, E-Stop, heartbeat veya enkoder fault'u ateş
çıkışını fail-closed kapatır. USB CDC alıcı/verici, 100 ms host heartbeat ve status/ACK yolu uygulanmıştır.
GKK-IO-REV-A mantıksal GPIO ataması `board_config.hpp` ve
`docs/hardware/GKK-IO-REV-A_PIN_MAP.md` içinde yapılmıştır. Elektriksel aktif
seviyeler, izolasyon ve boot/reset ölçümleri tamamlanmadan LIVE fiziksel çıkış
kabulü verilmez. İmalat ayrıntıları için
`docs/IMALAT_ELEKTRIK_KABLOLAMA_VE_EK_MALZEME.md` dosyasına bakın.

## Ayrı çift-motor tezgâh testi

Üretim pin haritasını etkinleştirmeden iki DM542 kanalını sınayan ayrı
`gokkalkan_motor_test` hedefi vardır. Ortak-anot (VBUS 5V) bağlantıda logic level converter
üzerinden sürücü 1 için `GP15=PUL-`, `GP14=DIR-`; sürücü 2 için `GP12=PUL-`, `GP11=DIR-`
kullanılır (`ENA` klemensleri boşta bırakılır). Her sürücünün `PUL+` ve `DIR+` ucu
VBUS (+5V) ortak anot hattına bağlı olmalıdır. Açılışta hareket yoktur; USB'den `ARM` ve sınırlı `MOVE`
gelmelidir. Komut başına sınır 64000 adım/4000 Hz, ARM süresi 120 saniyedir.
`MOVE 0` iki sürücüyü, `MOVE 1` yalnız sürücü 1'i, `MOVE 2` yalnız sürücü 2'yi
çalıştırır.

```sh
npm run pico:motor-test:deploy -- --host gokkalkan@gokkalkan.local \
  --identity ~/.ssh/gokkalkan_pi --prepare
```

Sonraki yüklemelerde `--prepare` çıkarılır. İlk düşük hızlı test:

```sh
ssh -i ~/.ssh/gokkalkan_pi gokkalkan@gokkalkan.local \
  'python3 /tmp/gokkalkan-pico-motor-test/scripts/pico_motor_test.py --driver 1 --direction CW --steps 200 --hz 100'
```

Bu hedef airsoft bağlantısı sökülmüş ve motor mekanik olarak emniyete alınmış
tezgâh testi içindir; üretim/HIL kabulü değildir.
