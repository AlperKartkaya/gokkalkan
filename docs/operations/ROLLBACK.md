# Gökkalkan Geri Dönüş Prosedürü

> Fiziksel çıkışlar kapatılmadan ve sistem E-Stop ile enerjisiz doğrulanmadan sürüm değiştirilmez.

1. Fiziksel E-Stop'a bas; LP1K1210BD'nin düştüğünü doğrula.
2. `sudo systemctl stop gokkalkan.target` çalıştır.
3. Son session/evidence dizinini salt okunur arşive kopyala ve SHA-256 kaydet.
4. `/opt/gokkalkan/releases/<KNOWN_GOOD>` symlink'ini doğrulanmış sürüme çevir.
5. `/etc/gokkalkan` config/calibration/model hash'lerinin o sürüm release manifestiyle aynı olduğunu doğrula.
6. `python3 scripts/verify_pi_manifest.py --manifest-only` ve `gokkalkan doctor --config /etc/gokkalkan/runtime.toml --strict` çalıştır.
7. Servisleri başlat; sistem **DISARMED** kalmalıdır.
8. Önce monitor-only, sonra onaylı safe-load HIL senaryolarını yeniden çalıştır.
9. İleri sürüme dönüş de aynı adımlarla yapılır; eski HIL kanıtı yeni hash'lere taşınmaz.

Rollback başarılı sayılmak için başlangıçta otomatik arm/FIRE oluşmadığı ve yeni HIL raporunun kullanılan commit, firmware, config, calibration ve model hash'lerini içerdiği kaydedilir.
