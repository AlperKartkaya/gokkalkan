# Gökkalkan Backend

Bu klasör, gerçek operatör panelinin bağlanacağı görev çekirdeği ve donanım denetimi katmanı için ayrılmıştır. İlk uygulanmış parça, fiziksel çıkış üretmeyen dry-run operatör API iskeletidir.

## Dry-run Operatör API

Çalıştırma:

```bash
.venv/bin/gokkalkan operator-api --config config/runtime/sim.toml
# İsteğe bağlı kanıt/replay yolu:
.venv/bin/gokkalkan operator-api --config config/runtime/sim.toml \
  --telemetry-jsonl telemetry_data/operator-api-dry-run.jsonl
```

Tüm mutasyon endpoint’leri önce bounded `CommandEnvelope` kuyruğuna girer. State
yalnız tek sahipli Mission Core reducer thread’inde değişir; HTTP/USB-MCU/sensör
thread’leri `OperatorService` state’ini doğrudan yazamaz.

Endpoint’ler:

- `GET /health`
- `GET /state` — immutable Mission Core snapshot’ı.
- `GET /state/stream?after=N` — SSE state akışı; `id=snapshotVersion`.
- `GET /commands/{commandId}` — kabul edilen/kuyruktaki komutun sonucu.
- `GET /sensor-frames` — radar/LiDAR biçimli dry-run `SensorFrame` replay paketi döner; gerçek sensör bağlı iddiası taşımaz.
- `GET /readiness` — final fazı arayüz hazırlığı, TBD/kilitli boşluklar ve sıradaki kritik adımları döner; resmi uygunluk skoru değildir.
- `GET /events`
- `GET /telemetry/export` — KTR/debug için tek JSON kanıt paketi döner.
- `GET /replay` — JSONL kayıtlarından replay-only olay/komut/donanım sonucu paketi döner.
- `POST /stage` — aşama/tur görev bağlamını ve beklenen modu günceller; geçersiz aşama/tur fiziksel çıkışsız bloklanır.
- `POST /mode`
- `POST /manual-aim`
- `POST /fire-intent`
- `POST /tracks/update` — perception sonucu; source sequence ile sıra kontrolü.
- `POST /perception/heartbeat` — ayrı perception process health bildirimi.
- `POST /estop` — ikincil yazılımsal Acil Durdur olayı.
- `POST /telemetry/reset` — dry-run oturumu ve JSONL kanıtını güvenli başlangıç durumuna sıfırlar.

Telemetri varsayılan olarak git’e eklenmeyen `telemetry_data/operator-api-dry-run.jsonl` dosyasına JSONL olarak yazılır. `GOKKALKAN_TELEMETRY_JSONL` ortam değişkeni veya `--telemetry-jsonl` parametresiyle yol değiştirilebilir. `/readiness` repo içi entegrasyon durumunu gösterir; `/replay` yalnız kayıtları okur ve gerçek hardware adapter çağırmaz.

Güvenlik notu: Bu API geçişinde `hardware_mock.dry_run` adapter kullanılır. Komut kabul edilse bile `physicalOutput=false` döner; gerçek motor, MCU, radar/LiDAR veya imha hattı sürülmez.

Mesaj şeması, idempotency, sıra ve kapanış davranışı
[`docs/message_contracts.md`](../docs/message_contracts.md); concurrency kararı
[`ADR-004`](../docs/adr/004-mission-core-concurrency.md) içinde açıklanır.

## Runtime profilleri

- `SIM` varsayılandır ve fiziksel MCU adapter oluşturmaz.
- `HIL` varsayılan olarak `loop://` USB seri taşımasını kullanır; fiziksel
  çıkış yetkisi yoktur.
- `LIVE`, açık backend enable yanında fiziksel interlock ve readiness preflight
  ister. Genel CLI bu preflight’ı üretmediği için canlı adapter fail-closed
  kilitlidir.

```bash
# USB seri HIL loopback
.venv/bin/gokkalkan operator-api --config config/runtime/hil.toml

# macOS/Linux USB loopback
.venv/bin/gokkalkan operator-api --config config/runtime/hil.toml --usb-loop
```

Frontend’i bu API’ye bağlamak için:

```bash
cd frontend
VITE_GOKKALKAN_OPERATOR_API_BASE=http://127.0.0.1:8088 npm run dev
```

## Test

```bash
.venv/bin/python -m pytest
```

## Paket ve tanılama

`pyproject.toml`, `gokkalkan`, `gokkalkan-operator-api`,
`gokkalkan-doctor`, `gokkalkan-static-server` ve
`gokkalkan-telemetry-recorder` giriş noktalarını kurar.

```bash
.venv/bin/gokkalkan doctor --config config/runtime/sim.toml
```

Doctor yalnız config, dosya sistemi, cihaz düğümleri ve salt okunur health
endpoint’lerini inceler; USB MCU/GPIO adapter oluşturmaz.
