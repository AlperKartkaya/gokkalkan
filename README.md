# Gökkalkan

Gökkalkan, TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması için geliştirilen yazılım, simülasyon ve KTR/rapor hazırlık çalışma alanıdır. Nihai gereksinim kaynağı `docs/sartname_v5.pdf` ve aranabilir metin karşılığı `docs/sartname_v5.txt` dosyalarıdır.

## Güncel durum

- `frontend/` artık React + Vite + TypeScript tabanlı **yarışma eğitim simülatörü** içerir.
- Simülatör; Aşama 1 manuel hedef pratiği, Aşama 2 sürü saldırısı, Aşama 3 dost/düşman + menzil kurallarını görselleştirir.
- Hız, kesin parkur koordinatı, hedef fiziksel ölçüsü ve sensör modeli şartnamede sayısal verilmediği için simülasyon parametreleri yapılandırılabilir varsayımdır.
- `backend/` içinde **dry-run Operatör API** iskeleti çalışır; gerçek donanım çıkışı üretmez, JSONL telemetri/replay kanıtı üretir, `/stage` ile aşama/tur bağlamını yönetir, `/sensor-frames` ile radar/LiDAR biçimli replay verisi sunar ve `/readiness` ile final fazı entegrasyon boşluklarını dürüstçe raporlar. Operatör panelindeki `Aşama / Tur kontrolü`, `Radar/LiDAR realtime katmanı`, `Finale Hazırlık`, manuel yönlendirme, hardware mock sonucu ve `Kanıt / Replay` yüzeyleri bu verileri okuyabilir.
- `perception/` ve gerçek sensör/donanım bağlantıları hâlâ saha sistemi için geliştirme alanıdır.

## Ürün yüzeyleri

1. **Yarışma Simülatörü** — eğitim, KTR ekran görüntüsü ve görev akışı provası için. Gerçek donanım komutu göndermez.
2. **Gerçek Operatör Paneli** — final fazında backend, algı, sensör ve donanım adaptörlerine bağlanacak güvenlik-kritik kontrol paneli. Dry-run geçişte React panel; aşama/tur seçimi, mod seçimi, radar/LiDAR replay ölçümleri, yazılımsal hedef tipi + dost/düşman yorumu, deadman’li manuel pan/tilt niyeti, FireIntent, seçili hedef detayı, Safety Gate gerekçesi, hardware mock sonucu, `Finale Hazırlık`, adapter/TBD çekmecesi ve kapalı gelen `Kanıt / Replay` çekmecesini içerir. UI yalnızca komut niyeti üretmeli; hareket/ateş izni backend Safety Gate tarafından verilmelidir.
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

Dry-run operatör API, `POST /stage`, `POST /manual-aim`, `POST /fire-intent`, `GET /sensor-frames`, `/readiness`, `/telemetry/export` ve `/replay` endpoint’leriyle entegrasyon durumu ve komut/olay kanıtı üretir; readiness yüzdesi resmi yarışma uygunluk skoru değildir. `SensorFrame` replay akışı gerçek radar/LiDAR bağlıymış gibi kesinlik iddiası taşımaz, fiziksel çıkış üretmez ve hardware adapter çağırmaz.

Simülatör eğitim amaçlıdır. Gerçek sistemde operatör paneli doğrudan ateşleme/imha hattını tetiklememelidir. Komut akışı `Operatör Paneli → Backend API → Safety Gate → Hardware Adapter → MCU/İmha Hattı` zincirinden geçmeli; Acil Durdur ve yasak alan kontrolleri UI’dan bağımsız olarak uygulanmalıdır.

## Desktop operatör paneli

Tek yarışma programı hedefi Gökkalkan Operator Panel’dir. Geliştirme makinesinde kökten:

```bash
npm run desktop
```

komutu dry-run backend API’yi, frontend’i ve `?operator=1&desktop=1` panelini tek akışta başlatır. Linux/macOS/Windows için aynı Node launcher kullanılır; Chromium/Chrome/Edge app-window bulunamazsa varsayılan tarayıcıya düşer. Hızlı doğrulama için:

```bash
npm run desktop:check
```

Vendor LiDAR yazılımları (RPLIDAR Viewer, Livox Viewer vb.) görev arayüzü değildir; yalnız bakım/kalibrasyon/ham point cloud doğrulama için dış diagnostic araçtır. Operasyon verisi `SDK/driver → SensorFrame → Backend → Operatör Paneli` hattından gelmelidir.
