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
Kart pin haritası ve GPIO çıkış katı onaylanana kadar `pico_main.cpp` aktüatör
çıkışlarını bilerek etkinleştirmez. İmalat ayrıntıları için
`docs/IMALAT_ELEKTRIK_KABLOLAMA_VE_EK_MALZEME.md` dosyasına bakın.
