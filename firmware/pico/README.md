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
