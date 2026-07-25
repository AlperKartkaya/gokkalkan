# systemd servisleri

Varsayılan başlangıç sırası:

1. `gokkalkan-backend.service` (kanonik tek-yazarlı session recorder burada)
2. `gokkalkan-perception.service` ve `gokkalkan-frontend.service`

Perception yalnız `/etc/gokkalkan/enable-perception` dosyası varsa başlar; temiz
SIM kurulumunda kamera yokluğu restart döngüsü yaratmaz. Perception backend’den
ayrı bir OS process’idir; bounded latest-wins kuyruğu üreticiyi HTTP gecikmesine
karşı korur, heartbeat kaybı Mission Core’da fail-closed fault üretir. Backend,
SQLite WAL + JSONL session’ın tek kalıcı writer’ıdır. Bağımsız process
üreticileri için aynı store’u kullanan `gokkalkan-telemetry.service` Unix socket
recorder’ı ayrıca kuruludur ancak ikinci bir kanonik kayıt oluşturmaması için
varsayılan `gokkalkan.target` tarafından başlatılmaz.

Loglar journald’a gider:

```bash
journalctl -u gokkalkan-backend -u gokkalkan-perception -u gokkalkan-frontend
```

Servisler `SIGINT`/`SIGTERM`, sınırlı kapanış süresi ve `Restart=on-failure`
kullanır. `LIVE` için ayrı birim yoktur; `/etc/gokkalkan/runtime.toml` ve fiziksel
bootstrap Faz 4 tamamlanmadan değiştirilmez.
