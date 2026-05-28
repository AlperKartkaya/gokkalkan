# Raporlar

Bu klasör OTR/KTR rapor materyalleri, diyagram kaynakları ve teslim hazırlık notları için kullanılır. Yarışma şartnamesi (`docs/sartname_v5.pdf` / `docs/sartname_v5.txt`) rapor içeriğinde nihai otoritedir.

## Güncel odak

- **OTR:** en fazla 10 sayfa.
- **KTR:** en fazla 30 sayfa; yazılım mimarisi, arayüzler, güvenlik katmanı, görev akışları ve doğrulama planı açık anlatılmalı.
- **Görev Kabiliyeti Gösterimi Videosu:** tek YouTube linki, 720p+, 2-5 dakika, şartnamedeki yetenek sırasına uygun.

## KTR arayüz bölümü için kaynaklar

- `docs/operator_panel_interfaces_roadmap.md` — kullanıcı arayüzü, yazılımsal mesaj arayüzleri, sensör/veri aktarımı ve elektronik güç/sinyal arayüzleri için tablo önerileri.
- `docs/tech_stack.md` — backend, perception, frontend, Safety Gate ve donanım adapter mimarisi.
- `reports/diyagramlar/mermaid_kodu/ktr_mermaid_diagrams.md` — KTR’ye taşınacak Mermaid blok, akış ve sequence diyagramları.

## Yazım ilkeleri

- Şartnamede olmayan hız, sensör modeli, voltaj, protokol veya fiziksel koordinat değerlerini resmi değer gibi yazmayın.
- Gerçek operatör panelini simülatörden ayırın: simülatör eğitimdir; gerçek panel backend/perception/hardware bağlantılıdır.
- UI’nın ateşleme/imha hattını doğrudan tetiklemediğini; komutların Safety Gate ve Hardware Adapter üzerinden geçtiğini açık yazın.
- Elektronik arayüzlerde seçilmemiş kararları `TBD` veya “tasarım netleşince doldurulacak” olarak bırakın.
