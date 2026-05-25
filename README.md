# Gökkalkan

Gökkalkan, TEKNOFEST 2026 Çelikkubbe Hava Savunma Sistemleri Yarışması için geliştirilen yazılım, simülasyon ve KTR/rapor hazırlık çalışma alanıdır. Nihai gereksinim kaynağı `docs/sartname_v5.pdf` ve aranabilir metin karşılığı `docs/sartname_v5.txt` dosyalarıdır.

## Güncel durum

- `frontend/` artık React + Vite + TypeScript tabanlı **yarışma eğitim simülatörü** içerir.
- Simülatör; Aşama 1 manuel hedef pratiği, Aşama 2 sürü saldırısı, Aşama 3 dost/düşman + menzil kurallarını görselleştirir.
- Hız, kesin parkur koordinatı, hedef fiziksel ölçüsü ve sensör modeli şartnamede sayısal verilmediği için simülasyon parametreleri yapılandırılabilir varsayımdır.
- `backend/`, `perception/` ve donanım bağlantıları hâlâ gerçek operatör paneli / saha sistemi için geliştirme alanıdır.

## Ürün yüzeyleri

1. **Yarışma Simülatörü** — eğitim, KTR ekran görüntüsü ve görev akışı provası için. Gerçek donanım komutu göndermez.
2. **Gerçek Operatör Paneli (planlanan)** — final fazında backend, algı, sensör ve donanım adaptörlerine bağlanacak güvenlik-kritik kontrol paneli. UI yalnızca komut niyeti üretmeli; hareket/ateş izni backend Safety Gate tarafından verilmelidir.
3. **Rapor/KTR dokümantasyonu** — mimari, arayüzler, sequence diyagramları ve yarışma kanıtlarının yazılı kaynağı.

## Hızlı başlangıç

```bash
cd frontend
npm install
npm run dev
```

Doğrulama komutları:

```bash
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

Simülatör eğitim amaçlıdır. Gerçek sistemde operatör paneli doğrudan ateşleme/imha hattını tetiklememelidir. Komut akışı `Operatör Paneli → Backend API → Safety Gate → Hardware Adapter → MCU/İmha Hattı` zincirinden geçmeli; Acil Durdur ve yasak alan kontrolleri UI’dan bağımsız olarak uygulanmalıdır.
