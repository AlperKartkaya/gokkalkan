# Runtime profilleri

Bu klasördeki TOML dosyaları `gokkalkan_backend.runtime_config` tarafından
şema sürümü, tip, aralık ve güvenlik bağıntılarıyla doğrulanır.

- `SIM`: Fiziksel adapter oluşturmaz.
- `HIL`: Yalnız `vcan*` veya `python-can virtual` kanalını kabul eder.
- `LIVE`: Fiziksel CAN, interlock/readiness sağlayıcı adları ve operatör token
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
```

CLI veya istemci payload’ı güvenlik alanlarını gevşetemez. Saha `LIVE`
konfigürasyonu `/etc/gokkalkan/runtime.toml` altında, erişimi kısıtlı ve
değişiklik hash’i kayıtlı olacak şekilde yönetilir.
