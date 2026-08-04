# Raspberry Pi 5 kurulum sözleşmesi

Hedef; Raspberry Pi 5 üzerinde **Raspberry Pi OS Lite 64-bit / Debian 13
Trixie** ve Python 3.13’tür. Bu seçim AI HAT+ resmi yazılım gereksinimiyle
kilitlenmiştir. Hedefte VM, ROS 2 ve Node.js çalışma zamanı
bulunmaz. Frontend CI/geliştirme makinesinde `npm ci && npm run build` ile
üretilir; `frontend/dist` deploy paketine dahil edilir ve Pi’de bağımlılıksız
Python static server tarafından sunulur.

## Temiz imaj akışı

1. 64-bit Trixie Lite imajını doğrulanmış Raspberry Pi Imager ile yaz.
2. Tek Camera Module 3 Standard'ı CSI portuna; AI HAT+ 26 TOPS'ı ürünle gelen
   PCIe kablosu, stacking header ve standoff'larla Pi 5'e bağla. Pi Active
   Cooler önerilir; enerjiyi tamamen kesmeden bağlantı yapma.
3. Repo/deploy paketini `/opt/gokkalkan` altına koy.
4. Önce salt okunur manifest kontrolü:

   ```bash
   python3 scripts/verify_pi_manifest.py --manifest-only
   ```

5. Kurulumu uygula:

   ```bash
   sudo bash scripts/bootstrap_pi.sh --apply
   ```

6. Host ve dry-run kontrolü:

   ```bash
   systemctl start gokkalkan.target
   curl --fail http://127.0.0.1:8088/health
   curl --fail http://127.0.0.1:4173/healthz
   sudo -u gokkalkan /opt/gokkalkan/.venv/bin/gokkalkan doctor \
     --config /etc/gokkalkan/runtime.toml --strict
   hailortcli fw-control identify
   ```

Operatör arayüzü ve API güvenlik gereği yalnız loopback üzerinde dinler. Başka
bir bilgisayardan erişmek için portları doğrudan ağa açmak yerine SSH tüneli
kullan:

```bash
ssh -L 4173:127.0.0.1:4173 -L 8088:127.0.0.1:8088 pi@<pi-adresi>
```

Ardından operatör bilgisayarında `http://127.0.0.1:4173` açılır.

Kurulum `config/runtime/pi-sim.toml` dosyasını hedef runtime config’i yapar.
`LIVE` otomatik etkinleştirilmez. CAN sürücüsü/device-tree overlay’i kullanılan
fiziksel CAN denetleyicisine bağlı olduğundan elektronik kabulünde ayrıca
kilitlenir; manifest yalnız SocketCAN arayüz adı ve bitrate sözleşmesini sabitler.
`hailortcli` çıktısında `Hailo-8` görülmeden perception sağlıklı sayılmaz.
`Hailo-8L` 13 TOPS varyantıdır ve bu projenin 26 TOPS donanım sözleşmesini
karşılamaz. HEF model yolu ayrıca seçilmediği sürece health, donanımı hazır ama
modeli hazır değil olarak raporlar.

Kurulum sonunda aşağıdaki komut release kanıtı olarak saklanır:

```bash
dpkg-query -W -f='${Package}==${Version}\n' \
  > /var/lib/gokkalkan/installed-packages.lock
```
