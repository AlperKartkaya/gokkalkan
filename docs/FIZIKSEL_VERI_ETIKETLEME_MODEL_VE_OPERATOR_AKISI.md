# Fiziksel Veri, Tek Model, Etiketleme ve Operatör Akışı

**Karar tarihi:** 17 Ağustos 2026
**İlgili iş paketleri:** WP-01 Manuel Mod, WP-02 Otonom Tespit ve Takip,
WP-03 Dost-Düşman + Menzil, WP-04 Güvenlik Katmanı

## 1. Tek model mi, iki model mi?

**Bugünkü bağlayıcı karar: tek dedektör modeli ve tek ağırlık dosyası.**

```text
Camera Module 3 / main 2304×1296
├─ ARAMA: 8 adet 768×768 SAHI tile ─┐
└─ TAKİP: 1 adet 768×768 ROI ────────┤→ aynı 640×640 YOLO → aynı HEF
                                     └→ farklı scheduler/koordinat dönüşümü
```

SAHI ayrı bir model değildir. Uzak hedefi kaçırmamak için aynı modelin yüksek
çözünürlüklü görüntünün örtüşmeli parçalarında çalıştırılmasıdır. Takipte taret
hedefe döndüğünde aynı model tek kare ROI'de daha yüksek frekansla çalışır.

Eğitim veri setinde iki görünüm ailesi birlikte bulunur:

- `SEARCH_SAHI_TILE_768`: tile sınırı, küçük hedef ve hard-negative örnekleri;
- `TRACK_SQUARE_ROI`: normal 768 ve kurtarma 960/1152 ROI örnekleri.

Fiziksel fotoğraflardan da her iki runtime görünümü türetilir. Tek model ancak
bağımsız gerçek testlerde arama recall'u ile takip kararlılığını aynı anda
sağlayamazsa iki modele ayrılır. Şimdiden iki model tutmak veri parçalanması,
iki ayrı HEF ve iki ayrı kalibrasyon/release zinciri oluşturacağı için gereksizdir.

## 2. Fiziksel veriyi nereye koyacağız?

### Ham, henüz etiketsiz çekimler

```text
perception/dataset/captures/drop/<sessionId>/
├── session.json
└── <sunum-sınıfı>/*.jpg
```

Bu alan hızlı ön etiketleme içindir. `npm run dataset:pull` dosyaları hash'li
store'a kopyalar; kaynakları silmez.

### Takım tarafından insan onaylı etiketler

```text
perception/dataset/captures/annotated/<sessionId>/
├── session.json
├── images/**/frame.jpg
└── labels/**/frame.txt
```

`npm run dataset:prepare` bu alanı otomatik alır. Aynı oturumun kareleri farklı
split'lere dağılmaz; `sessionId` bütünüyle train, val veya test olur. Ham
fotoğraf ve export arşivleri Git'e konmaz.

## 3. Etiket biçimi ve sınıf sözleşmesi

Runtime YOLO olduğundan kanonik eğitim etiketi JSON değil, Ultralytics YOLO bbox
satırıdır:

```text
class_id center_x center_y width height
```

Değerler 0..1 normalize edilir. CVAT isterse ayrıca COCO 1.0 JSON yedeği
üretebilir; fakat pipeline'a giren biçim **Ultralytics YOLO Detection 1.0**'dır.
Sınıf sırası değiştirilemez:

1. `dusman_drone_kirmizi`
2. `dusman_helikopter_kirmizi`
3. `dusman_f16_kirmizi`
4. `dusman_fuze_kirmizi`
5. `dost_helikopter_camgobegi`
6. `dost_f16_camgobegi`
7. `balon`

Pipeline sınıf numarasını, bbox aralığını, eşleşen görüntü/label dosyasını ve
session metadata'sını fail-closed doğrular.

## 4. Takım için en kolay etiketleme arayüzü: CVAT

Yeni özel etiketleme uygulaması yazılmayacaktır. CVAT zaten kullanıcı, görev,
inceleme, bbox, otomatik ön etiket ve Ultralytics YOLO export sağlar.

1. Bir ekip bilgisayarında resmi CVAT Docker kurulumu yapılır.
2. Yedi label yukarıdaki sırayla tek projede oluşturulur.
3. Her fiziksel çekim oturumu ayrı CVAT task olur.
4. Etiketçi hedef maketi ve balonu ayrı bbox olarak çizer.
5. İkinci takım üyesi review yapar; yanlış renk/tür ve eksik balon kontrol edilir.
6. `Ultralytics YOLO Detection 1.0` ve ayrıca arşiv için `COCO 1.0` export alınır.
7. YOLO export `captures/annotated/<sessionId>/` altına açılır ve `session.json`
   eklenir.
8. `npm run dataset:prepare` çalıştırılır.

CVAT kaynakları:

- [Resmî kurulum](https://docs.cvat.ai/docs/administration/basics/installation/)
- [Desteklenen veri biçimleri](https://docs.cvat.ai/docs/dataset_management/formats/)
- [YOLO import/export](https://docs.cvat.ai/docs/manual/advanced/formats/format-yolo/)

### Etiketleme sorumluluğu

- **Etiketçi:** bbox ve doğru yedi sınıftan biri.
- **Reviewer:** bbox'ın maketi/balonu tam sardığını ve sınıfı kontrol eder.
- **ML sorumlusu:** session split, manifest reviewQueue, veri sızıntısı ve sınıf
  dağılımını kontrol eder.

Model tahmini ön etiket olarak kullanılabilir; insan review olmadan gerçek
test/release verisi kabul edilmez.

## 5. Fiziksel çekim planı

Tek bir klasöre rastgele fotoğraf atılmaz. Farklı gün, ışık, arka plan, baskı
örneği ve mesafe ayrı `sessionId` olur. Arama ve takip girdileri aynı yüksek
çözünürlüklü fiziksel ana kareden runtime ile aynı sırada türetilir:

```text
gerçek main frame
→ 8× SAHI tile + track ROI aileleri
→ aynı session/group split
→ aynı model eğitimi
```

Val/test oturumları eğitimden önce kilitlenir; ekip onların etiketlerini görse
de model ayarı sırasında test sonucuna göre tekrar tekrar seçim yapmaz.

## 6. Canlı güven yüzdeleri

Model sınıfları bugün renk ve hedef tipini birleşik kodlar. Bu nedenle
`dusman_f16_kirmizi %87` skoru ayrı ayrı kalibre edilmiş iki olasılık değil,
**birleşik sunum sınıfı güvenidir**. API alanları:

- `confidence`: geriye uyumlu birleşik skor;
- `typeConfidence`: tür göstergesinde kullanılan skor;
- `friendFoeConfidence`: Aşama 3 renk/IFF göstergesinde kullanılan skor;
- `confidenceSemantics`: skorun `JOINT_PRESENTATION_CLASS`,
  `HSV_TRACK_STABILITY` veya legacy olduğunu açıklar.

YOLO yolunda ilk iki yüzde aynı birleşik değeri taşır; bu durum UI'da canlı
track üzerinden gösterilir ve sensör replay yüzdesi uydurulmaz. İleride ayrı
renk başlığı/multi-head kalibrasyonu gelirse alanlar ayrışabilir.

## 7. Şartnameye göre operatör görev akışı

Şartname 6. bölüm: Aşama 1 manuel, Aşama 2/3 otonom; bakım bitince yarışma
süresi devam eder; Acil Durdur sonrası ancak hakem değerlendirmesiyle devam
edilebilir.

Uygulanan panel davranışı:

1. Backend `IDLE`, Aşama 1/Tur 1 ve `safe` modunda açılır.
2. Operatör `AŞAMA 1 · TUR 1 BAŞLAT` ile görevi başlatır.
3. Aktif görevde aşama/tur düğmeleriyle rastgele atlama yoktur.
4. Tur bitince yalnız backend sırasındaki sonraki tur/aşama başlatılabilir.
5. Aşama 1 manuel yönelim yalnız `ACTIVE + manual + deadman` iken backend'e
   `ManualAimCommand` yollar; backend Safety Gate'ten sonra Arduino Uno adapterına
   aktarır.
6. Bakım bitince önceki aktif mod ve görev timer'ı doğrudan sürer.
7. Kırmızı komut `ACİL DURDUR` endpoint'ini kullanır; fiziksel buton yine
   birincil donanımsal kesmedir.

## 8. Panelde hâlâ fiziksel karşılık bekleyen öğeler

| Panel öğesi | Bugünkü kaynak | Fiziksel kabul için gereken |
| --- | --- | --- |
| Track ve bbox | Perception API bağlı; SIM'de fixture | Camera Module 3 + gerçek HEF |
| Tür/renk yüzdesi | Canlı track alanına bağlı | Gerçek veri kalibrasyonu |
| 1D LiDAR menzili | Adapter sözleşmesi var; SIM/replay olabilir | TFA50-L saha doğrulaması |
| Manuel yönelim | Backend/Safety/adapter bağlı | Arduino firmware, motor ve yön HIL |
| ATEŞ | Safety + adapter bağlı | Airsoft dry-contact HIL ve canlı arm kabulü |
| Kamera nişangâhı | UI katmanı bağlı | Kamera-boresight ve balistik kalibrasyon |
| 3D LiDAR görünümü | Replay/temsili sensor frame | Donanım 1D olduğundan karar ekranı değil, teşhis |
| Readiness/replay | Backend kanıt endpointleri | Saha kanıtlarının kaydı |
| AI panel CAD kartı | Bilgilendirme/placeholder | Runtime karar yüzeyi değildir |

`frontend` içindeki yarışma simülatörü ayrı eğitim/demo yüzeyidir; gerçek
operatör panelinin veri kaynağı değildir.

## 9. Raspberry Pi dağıtımı

Bilgisayardan:

```bash
npm run pi:deploy -- --host pi@<pi-ip>
```

Frontend bilgisayarda statik dosyalara derlenir. Repo, Python kaynakları ve
`frontend/dist` Pi'ye kopyalanır; Python venv ve systemd servisleri Pi'de
kurulur. `gokkalkan.target` açılışta otomatik başlar. Bilgisayar ve SSH
bağlantısı kesildiğinde Pi yazılımı çalışmaya devam eder. Operatör tarayıcısı
uzaktan bağlanacaksa yalnız SSH tüneli gerekir; tünel görev proseslerinin
çalışması için gerekli değildir.

## 10. Kabul kapıları

- Kod testlerinin geçmesi fiziksel motor/kamera/atış kabulü değildir.
- Gerçek val/test oturumları ve insan review olmadan model release değildir.
- HEF eşdeğerliği ve Pi 5 + AI HAT+ gecikmesi ölçülmeden SAHI hedef frekansı
  doğrulanmış değildir.
- Arduino USB, encoder/E-Stop geri bildirimi ve airsoft dummy-load HIL tamamlanmadan LIVE arm
  açılmaz.
