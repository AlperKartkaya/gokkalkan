# Runtime profilleri

Bu klasördeki TOML dosyaları `gokkalkan_backend.runtime_config` tarafından
şema sürümü, tip, aralık ve güvenlik bağıntılarıyla doğrulanır.

- `SIM`: Fiziksel adapter oluşturmaz.
- `HIL`: Varsayılan `hil.toml` `loop://` Arduino satır-protokolü simülasyonu kullanır.
  `hil-physical.toml` kararlı `/dev/serial/by-id/...` Arduino yolunda yalnız
  manuel PAN/TILT motor çıkışını açar. Deadman ve Safety Gate aktiftir; yazılım
  Acil Durdur Arduino'ya `STOP` yollar. Firmware'de `FIRE` bulunmadığından gerçek
  imha/ateşleme çıkış yetkisi vermez. Fiziksel portta adapter, hareketten önce
  `PING/PONG` ve `[mcu].field_profile` ile `PROFILE` eşleşmesini zorunlu tutar.
  Varsayılan R1 profil `GKK-UNO-DM542-1600PPR-R1`dir. `loop://` bu firmware
  doğrulamasını yapmaz; yalnız taşıma çerçevesi kanıtıdır.
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

`[mcu].field_profile`, flash edilmiş Arduino firmware'in tam kimliğidir; pin
eşlemesi bu dosyadan değiştirilemez. Farklı kablolama, sürücü mikroadımı veya
firmware için yeni, gözden geçirilmiş profil kimliği ve buna karşılık gelen
firmware/adapter/test değişikliği gerekir. Ayrıntı:
[`docs/hardware/GKK-IO-REV-B_PIN_MAP.md`](../../docs/hardware/GKK-IO-REV-B_PIN_MAP.md).
