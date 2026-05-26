# Gökkalkan Backend

Bu klasör, gerçek operatör panelinin bağlanacağı görev çekirdeği ve donanım denetimi katmanı için ayrılmıştır. İlk uygulanmış parça, fiziksel çıkış üretmeyen dry-run operatör API iskeletidir.

## Dry-run Operatör API

Çalıştırma:

```bash
PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server --host 127.0.0.1 --port 8088
# İsteğe bağlı kanıt/replay yolu:
PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server --host 127.0.0.1 --port 8088 --telemetry-jsonl telemetry_data/operator-api-dry-run.jsonl
```

Endpoint’ler:

- `GET /health`
- `GET /state`
- `GET /sensor-frames` — radar/LiDAR biçimli dry-run `SensorFrame` replay paketi döner; gerçek sensör bağlı iddiası taşımaz.
- `GET /readiness` — final fazı arayüz hazırlığı, TBD/kilitli boşluklar ve sıradaki kritik adımları döner; resmi uygunluk skoru değildir.
- `GET /events`
- `GET /telemetry/export` — KTR/debug için tek JSON kanıt paketi döner.
- `GET /replay` — JSONL kayıtlarından replay-only olay/komut/donanım sonucu paketi döner.
- `POST /stage` — aşama/tur görev bağlamını ve beklenen modu günceller; geçersiz aşama/tur fiziksel çıkışsız bloklanır.
- `POST /mode`
- `POST /manual-aim`
- `POST /fire-intent`
- `POST /telemetry/reset` — dry-run oturumu ve JSONL kanıtını güvenli başlangıç durumuna sıfırlar.

Telemetri varsayılan olarak git’e eklenmeyen `telemetry_data/operator-api-dry-run.jsonl` dosyasına JSONL olarak yazılır. `GOKKALKAN_TELEMETRY_JSONL` ortam değişkeni veya `--telemetry-jsonl` parametresiyle yol değiştirilebilir. `/readiness` repo içi entegrasyon durumunu gösterir; `/replay` yalnız kayıtları okur ve gerçek hardware adapter çağırmaz.

Güvenlik notu: Bu API geçişinde `hardware_mock.dry_run` adapter kullanılır. Komut kabul edilse bile `physicalOutput=false` döner; gerçek motor, MCU, radar/LiDAR veya imha hattı sürülmez.

Frontend’i bu API’ye bağlamak için:

```bash
cd frontend
VITE_GOKKALKAN_OPERATOR_API_BASE=http://127.0.0.1:8088 npm run dev
```

## Test

```bash
PYTHONPATH=backend/src python3 -m unittest discover -s tests -p 'test_*.py'
```
