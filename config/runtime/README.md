# Runtime profilleri

Bu klasördeki TOML dosyaları `gokkalkan_backend.runtime_config` tarafından
şema sürümü, tip, aralık ve güvenlik bağıntılarıyla doğrulanır.

- `SIM`: Fiziksel adapter oluşturmaz.
- `HIL`: Varsayılan `hil.toml` `loop://` Arduino satır-protokolü simülasyonu kullanır.
  `hil-physical.toml` kararlı `/dev/serial/by-id/...` Arduino yolunda yalnız
  manuel PAN/TILT motor çıkışını açar. Deadman ve Safety Gate aktiftir; yazılım
  Acil Durdur Arduino'ya `STOP` yollar. Firmware'de `FIRE` bulunmadığından gerçek
  imha/ateşleme çıkış yetkisi vermez.
- `LIVE`: Fiziksel Arduino USB seri cihazı, interlock/readiness sağlayıcı adları ve operatör token
  yolu zorunludur; API yalnız loopback adresinde dinler. Örnek dosyada
  `live_output_enabled=false` bırakılmıştır.

`[safety]` içindeki `zone_schema_version=1`, hareket/atış yasak bölge
geometrilerini sürümler. Sınırlar yasaktır (inclusive); geçersiz geometri
profilin açılmasını engeller. `arm_hold_ms` sürekli operatör hold süresini,
`arm_timeout_ms` kayıp keepalive sonrası otomatik disarm sınırını belirler.

CLI:

```bash
gokkalkan operator-api --config config/runtime/sim.toml
gokkalkan doctor --config config/runtime/sim.toml
GOKKALKAN_MCU_PORT=/dev/serial/by-id/ARDUINO_CIHAZ_YOLU npm run desktop:hil
```

CLI veya istemci payload’ı güvenlik alanlarını gevşetemez. Saha `LIVE`
konfigürasyonu `/etc/gokkalkan/runtime.toml` altında, erişimi kısıtlı ve
değişiklik hash’i kayıtlı olacak şekilde yönetilir.
