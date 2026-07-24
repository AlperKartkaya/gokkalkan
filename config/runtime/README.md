# Runtime profilleri

Bu klasördeki TOML dosyaları `gokkalkan_backend.runtime_config` tarafından
şema sürümü, tip, aralık ve güvenlik bağıntılarıyla doğrulanır.

- `SIM`: Fiziksel adapter oluşturmaz.
- `HIL`: Yalnız `vcan*` veya `python-can virtual` kanalını kabul eder.
- `LIVE`: Fiziksel CAN, interlock/readiness sağlayıcı adları ve operatör token
  yolu zorunludur. Örnek dosyada `live_output_enabled=false` bırakılmıştır.

CLI:

```bash
gokkalkan operator-api --config config/runtime/sim.toml
gokkalkan doctor --config config/runtime/sim.toml
```

CLI veya istemci payload’ı güvenlik alanlarını gevşetemez. Saha `LIVE`
konfigürasyonu `/etc/gokkalkan/runtime.toml` altında, erişimi kısıtlı ve
değişiklik hash’i kayıtlı olacak şekilde yönetilir.
