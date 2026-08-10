# Gökkalkan Pico firmware

Bu dizin güvenlik durum makinesinin ve CAN v1 codec'inin donanımdan bağımsız
çekirdeğini içerir.

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
çıkışını fail-closed kapatır. Gerçek CAN controller sürücüsü, kart pin haritası
ve GPIO çıkış katı kart revizyonu onaylanana kadar `pico_main.cpp` içinde
bilerek etkin değildir. İmalat ayrıntıları için
`docs/IMALAT_ELEKTRIK_KABLOLAMA_VE_EK_MALZEME.md` dosyasına bakın.
