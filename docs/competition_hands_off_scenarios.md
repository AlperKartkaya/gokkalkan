# Hands-off Yarışma Senaryoları

Bu dosya, `frontend/src/scenarios/` altındaki çalıştırılabilir senaryo verilerinin insan-okur özetidir. Şartname kaynakları:

- `docs/sartname_v5.txt:430-463` — Manuel/Otonom Mod, Acil Durdur, bakım ve patlayıcı yasağı.
- `docs/sartname_v5.txt:469-511` — Aşama 1, 5/10/15 m durağan hedef, sıra ve puanlama.
- `docs/sartname_v5.txt:513-540` — Aşama 2, 4 tur, üç kol, A→B parkur, sınıflandırma beklenmez.
- `docs/sartname_v5.txt:543-580` — Aşama 3, 8 tur, 1 düşman + 2 dost, menzil kapıları.

> Not: Şartname kesin parkur koordinatı, hedef hız profili veya radar/LiDAR donanım modeli vermediği için rota ve sensör değerleri ayarlanabilir mock veridir. Rota ayarı `frontend/src/scenarios/*.ts` dosyalarındaki `route` dizileri üzerinden saniye/x/y/range olarak yapılır.

## Dosyalar

- `frontend/src/scenarios/stage1.ts` — Aşama 1 manuel hedef sırası, kaçan F16 atışı ve bakım izni.
- `frontend/src/scenarios/stage2.ts` — Aşama 2 dört turlu sürü saldırısı, bir kaçan hedef, bakım molası.
- `frontend/src/scenarios/stage3.ts` — Aşama 3 sekiz tur dost/düşman, menzil kapısı, dost kilidi, bakım molası.
- `frontend/src/scenarios/index.ts` — Senaryo oynatıcı: saniyeye göre hedefleri, seçili izi, modu, puanı ve olayı üretir.

## Özet akış

### Aşama 1
- 0s: Manuel Mod otomatik seçilir.
- 2s: 5 m Balistik Füze görünür.
- 9s: M-1 vurulur.
- 12s: 10 m Helikopter görünür.
- 18s: M-2 vurulur.
- 22s: 15 m F16 görünür.
- 32s: İlk F16 atışı kaçar.
- 38s: F16 vurulur.
- 47s: Mini/Micro İHA görünür.
- 55s: Mini/Micro İHA vurulur.
- 58s: Bakım izni talep edilir.
- 60-90s: Bakım molası.
- 92s: Aşama tamamlanır.

### Aşama 2
- 0s: Otonom Mod otomatik seçilir.
- 1-22s: Tur 1, üç hedef de vurulur.
- 24-44s: Tur 2, iki hedef vurulur; kol 3 kaçar.
- 48-60s: Bakım talebi ve kısa bakım.
- 61-74s: Tur 3, üç hedef vurulur.
- 84-101s: Tur 4, üç hedef vurulur.
- 110s: Aşama tamamlanır.

### Aşama 3
- 0s: Otonom Mod otomatik seçilir.
- 1-12s: Tur 1, düşman F16 uygun menzilde vurulur.
- 20-33s: Tur 2, düşman Helikopter vurulur.
- 40-58s: Tur 3, dost hedef kilidi gösterilir; düşman Mini/Micro İHA vurulur.
- 60-72s: Tur 4, düşman Balistik Füze kaçar ve ceza yazılır.
- 80-100s: Bakım izni ve bakım molası.
- 101-172s: Tur 5-8; iki F16/Helikopter/Balistik isabeti ve bir kaçan Mini/Micro İHA senaryosu.
- 182s: Aşama tamamlanır.
