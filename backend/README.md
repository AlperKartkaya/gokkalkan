# Gökkalkan Backend

Bu klasör, gerçek operatör panelinin bağlanacağı görev çekirdeği ve donanım denetimi katmanı için ayrılmıştır. İlk uygulanmış parça, fiziksel çıkış üretmeyen dry-run operatör API iskeletidir.

## Dry-run Operatör API

Çalıştırma:

```bash
PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server --host 127.0.0.1 --port 8088
```

Endpoint’ler:

- `GET /health`
- `GET /state`
- `GET /events`
- `POST /mode`
- `POST /manual-aim`
- `POST /fire-intent`

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
