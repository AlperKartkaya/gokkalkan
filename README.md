# Gökkalkan

Gökkalkan, TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması için geliştirilen yazılım, simülasyon ve KTR/rapor hazırlık çalışma alanıdır. Nihai gereksinim kaynağı `docs/sartname_v5.pdf` ve aranabilir metin karşılığı `docs/sartname_v5.txt` dosyalarıdır.

## Güncel durum

- `frontend/` artık React + Vite + TypeScript tabanlı **yarışma eğitim simülatörü** içerir.
- Simülatör; Aşama 1 manuel hedef pratiği, Aşama 2 sürü saldırısı, Aşama 3 dost/düşman + menzil kurallarını görselleştirir.
- Hız, kesin parkur koordinatı, hedef fiziksel ölçüsü ve sensör modeli şartnamede sayısal verilmediği için simülasyon parametreleri yapılandırılabilir varsayımdır.
- `backend/` içinde ilk **dry-run Operatör API** iskeleti başlamıştır; gerçek donanım çıkışı üretmez ve JSONL telemetri/replay kanıtı üretir.
- `perception/` ve gerçek sensör/donanım bağlantıları hâlâ saha sistemi için geliştirme alanıdır.

## Ürün yüzeyleri

1. **Yarışma Simülatörü** — eğitim, KTR ekran görüntüsü ve görev akışı provası için. Gerçek donanım komutu göndermez.
2. **Gerçek Operatör Paneli** — final fazında backend, algı, sensör ve donanım adaptörlerine bağlanacak güvenlik-kritik kontrol paneli. İlk geçişte React panel + dry-run Backend API vardır. UI yalnızca komut niyeti üretmeli; hareket/ateş izni backend Safety Gate tarafından verilmelidir.
3. **Rapor/KTR dokümantasyonu** — mimari, arayüzler, sequence diyagramları ve yarışma kanıtlarının yazılı kaynağı.

## Hızlı başlangıç

```bash
cd frontend
npm install
npm run dev
```

Dry-run operatör backend’i:

```bash
PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server --host 127.0.0.1 --port 8088
# KTR/debug kanıtı için isteğe bağlı özel JSONL yolu:
PYTHONPATH=backend/src python3 -m gokkalkan_backend.operator_http_server --host 127.0.0.1 --port 8088 --telemetry-jsonl telemetry_data/operator-api-dry-run.jsonl
```

Doğrulama komutları:

```bash
PYTHONPATH=backend/src python3 -m unittest discover -s tests -p 'test_*.py'
cd frontend
npm run typecheck
npm run build
npm run test
```

## Önemli dokümanlar

- `docs/sartname_v5.txt` — şartname metni; gereksinimlerde final otorite.
- `docs/tech_stack.md` — güncel teknik yönelim, modlar, safety gate ve arayüz mimarisi.
- `docs/operator_panel_interfaces_roadmap.md` — gerçek operatör paneli önerisi ve KTR arayüz tabloları.
- `DESIGN.md` — simülatör ve operatör paneli tasarım ilkeleri.
- `reports/diyagramlar/mermaid_kodu/ktr_mermaid_diagrams.md` — KTR için Mermaid blok/akış/sequence diyagramları.

## Takım ve teslim disiplini

- Yazılım ekibi: Alper, Ebubekir, Enes, Akif.
- Makine ekibi: mekanik tasarım ve imalat.
- OTR: en fazla 10 sayfa.
- KTR: en fazla 30 sayfa.
- Görev Kabiliyeti Gösterimi Videosu: tek YouTube linki, 720p+, 2-5 dakika, şartnamedeki yetenek sırasına uygun.

## Güvenlik ilkesi

Dry-run operatör API, `/telemetry/export` ve `/replay` endpoint’leriyle komut/olay kanıtı üretir; replay akışı fiziksel çıkış üretmez ve hardware adapter çağırmaz.

Simülatör eğitim amaçlıdır. Gerçek sistemde operatör paneli doğrudan ateşleme/imha hattını tetiklememelidir. Komut akışı `Operatör Paneli → Backend API → Safety Gate → Hardware Adapter → MCU/İmha Hattı` zincirinden geçmeli; Acil Durdur ve yasak alan kontrolleri UI’dan bağımsız olarak uygulanmalıdır.
