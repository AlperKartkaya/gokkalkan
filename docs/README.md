# docs/ — Doküman Dizini

Bu klasör Gökkalkan projesinin tüm teknik dokümanlarını barındırır.

## 📋 Şartname ve Gereksinimler

| Dosya | Açıklama |
|-------|----------|
| [`sartname_v4.pdf`](sartname_v4.pdf) | Yarışma şartnamesi (nihai otorite) |
| [`sartname_v4.txt`](sartname_v4.txt) | Şartnamenin aranabilir metin çıktısı |
| [`Celikkubbe_Hava_Savunma_Sistemleri_Parkur_Cizim.pdf`](Celikkubbe_Hava_Savunma_Sistemleri_Parkur_Cizim.pdf) | Kanonik parkur teknik çizimi (Rev 1) |
| [`parkur_geometri_referansi.md`](parkur_geometri_referansi.md) | Parkur geometrisi kanonik referansı ve deterministik fallback modeli |
| [`requirements_source.md`](requirements_source.md) | Şartname sürümü, hash ve güncelleme prosedürü |
| [`requirements_traceability.md`](requirements_traceability.md) | Gereksinim → modül / test / telemetri / video izlenebilirlik matrisi |
| [`hedef_ve_parkur_operasyon_guncellemesi.md`](hedef_ve_parkur_operasyon_guncellemesi.md) | Güncel hedef tablosu, balon, 10×16 m parkur ve 60/70/130 cm yükseklik sözleşmesi |

## 🏗️ Mimari ve Teknik Tasarım

| Dosya | Açıklama |
|-------|----------|
| [`tech_stack.md`](tech_stack.md) | Teknik yığın, Arduino Uno saha taşıması, tarihsel CAN sözleşmesi ve Safety Gate |
| [`taret_mekanik_ve_sensor_yerlesimi.md`](taret_mekanik_ve_sensor_yerlesimi.md) | Nihai iki eksenli taret, tabana göre 700 mm / yere göre yaklaşık 1300 mm LiDAR merkezi, tek kamera ve AI HAT+ referansı |
| [`hedef_gorseli_yolo_veri_plani.md`](hedef_gorseli_yolo_veri_plani.md) | Video hedef baskıları, gerçek kamera veri toplama, grup split, augmentation, YOLO ve Hailo-8 kabul planı |
| [`hedef_veri_seti_uygulama_rehberi.md`](hedef_veri_seti_uygulama_rehberi.md) | Çalışan augmentation, gerçek fotoğraf pull/import, YOLO dataset ve smoke eğitim komutları |
| [`FIZIKSEL_VERI_ETIKETLEME_MODEL_VE_OPERATOR_AKISI.md`](FIZIKSEL_VERI_ETIKETLEME_MODEL_VE_OPERATOR_AKISI.md) | Tek model/iki inference yolu kararı, CVAT etiketleme, operatör canlı veri sözleşmesi ve Pi dağıtımı |
| [`usb_serial_mcu_protocol.md`](usb_serial_mcu_protocol.md) | Legacy Pico USB CDC/COBS/CRC16 regresyon sözleşmesi (saha yolu değildir) |
| [`can_icd_v1.md`](can_icd_v1.md) | Tarihsel CAN payload kimlikleri ve v1 test sözleşmesi |
| [`message_contracts.md`](message_contracts.md) | Mission Core komut/olay şeması ve mesaj sıralaması |
| [`adr/`](adr/) | Mimari Karar Kayıtları (ADR-001 … ADR-006) |

## 📅 Planlama ve Yol Haritası

| Dosya | Açıklama |
|-------|----------|
| [`imalat_oncesi_yazilim_todo.md`](imalat_oncesi_yazilim_todo.md) | Legacy imalat öncesi Pico planı; yalnız tarihsel kayıt |
| [`operator_panel_interfaces_roadmap.md`](operator_panel_interfaces_roadmap.md) | Operatör panelinin tarihsel arayüz yol haritası; güncel yüzey `frontend/` |
| [`celikkubbe_final_phase_real_competition_sim_specs.md`](celikkubbe_final_phase_real_competition_sim_specs.md) | Final aşaması simülasyon spesifikasyonu |
| [`delivery_video_plan.md`](delivery_video_plan.md) | Güncel takvim ve sıralı video kanıt planı |
| [`digital_twin_and_evidence.md`](digital_twin_and_evidence.md) | Dijital ikiz, senaryo, session, replay ve kanıt kullanımı |
| [`faz_8_uygulama_plani.md`](faz_8_uygulama_plani.md) | Faz 8 uygulama detayları |
| [`frontend_ui_ux_polish_plan.md`](frontend_ui_ux_polish_plan.md) | Simülatör/operatör UI yön planı |
| [`taret_ve_asama1_operator_destegi.md`](taret_ve_asama1_operator_destegi.md) | Saha taret kalibrasyonu ve Aşama 1 canlı nişan sınırları |

## 📖 Kılavuzlar

| Dosya | Açıklama |
|-------|----------|
| [`IMALAT_KOMPONENT_BAGLANTI_REHBERI.html`](IMALAT_KOMPONENT_BAGLANTI_REHBERI.html) | Legacy Pico bağlantı arşivi; güncel saha kararı için REV-B pin map + ADR-006 kullanılır |
| [`IMALAT_ELEKTRIK_KABLOLAMA_VE_EK_MALZEME.md`](IMALAT_ELEKTRIK_KABLOLAMA_VE_EK_MALZEME.md) | Elektrik kablolama özeti, ek satın alma listesi ve imalat kontrol maddeleri |
| [`IMALAT_EK_MALZEME_SIPARIS_LISTESI.html`](IMALAT_EK_MALZEME_SIPARIS_LISTESI.html) | Legacy satın alma notu; Arduino pin/protokolü için `hardware/` ve ADR-006 bağlayıcıdır |
| [`MALZEME_LISTESI.md`](MALZEME_LISTESI.md) | Güncel malzeme ve teslimat durumlarının erişilebilir Markdown dökümü |
| [`CODEBASE_TUTORIAL.md`](CODEBASE_TUTORIAL.md) | Kod tabanı ve mimari eğitim kılavuzu |
| [`competition_hands_off_scenarios.md`](competition_hands_off_scenarios.md) | Yarışma hands-off senaryoları |

## 🖼️ Görseller ve Örnekler

| Dosya | Açıklama |
|-------|----------|
| [`images/`](images/) | CAD çizimleri ve mimari diyagram görselleri |
| [`screenshots/`](screenshots/) | KTR ekran görüntüleri |
| [`assets/`](assets/) | Tutorial varlıkları |
| [`turret_calibration_observations.example.json`](turret_calibration_observations.example.json) | Taret kalibrasyon gözlem örnek dosyası |
