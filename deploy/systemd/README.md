# systemd servisleri

Başlangıç sırası:

1. `gokkalkan-telemetry.service`
2. `gokkalkan-backend.service`
3. `gokkalkan-perception.service` ve `gokkalkan-frontend.service`

Perception yalnız `/etc/gokkalkan/enable-perception` dosyası varsa başlar; temiz
SIM kurulumunda kamera yokluğu restart döngüsü yaratmaz. Perception backend’den
ayrı bir OS process’idir; bounded latest-wins kuyruğu üreticiyi HTTP gecikmesine
karşı korur, heartbeat kaybı Mission Core’da fail-closed fault üretir. Telemetry recorder Unix
socket arayüzü hazırdır; mevcut backend JSONL kaydını da sürdürür. Üreticilerin
tamamının tek-yazarlı socket hattına taşınması `TEL-001` kapsamıdır.

Loglar journald’a gider:

```bash
journalctl -u gokkalkan-backend -u gokkalkan-perception \
  -u gokkalkan-frontend -u gokkalkan-telemetry
```

Servisler `SIGINT`/`SIGTERM`, sınırlı kapanış süresi ve `Restart=on-failure`
kullanır. `LIVE` için ayrı birim yoktur; `/etc/gokkalkan/runtime.toml` ve fiziksel
bootstrap Faz 4 tamamlanmadan değiştirilmez.
