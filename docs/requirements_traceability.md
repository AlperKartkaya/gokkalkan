# Şartname v1.3 Gereksinim İzlenebilirlik Matrisi

Bu matris şartname yükümlülüklerini modül, test, telemetri ve video kanıtına
bağlar. **Bağlandı** bir gereksinimin izlenebilir olduğunu, fiziksel olarak
tamamlandığını değil; **HIL/fiziksel bekliyor** ise donanım kanıtının henüz
üretilmediğini ifade eder. PDF son otoritedir.

## Teslim ve rapor gereksinimleri

| ID | Şartname kaynağı | Gereksinim | Repo/çıktı | Doğrulama | Durum |
| --- | --- | --- | --- | --- | --- |
| `DEL-OTR-PAGE` | txt 328–338 | OTR en fazla 10 sayfa | `reports/` | Teslim öncesi PDF sayfa sayımı | Bağlandı |
| `DEL-KTR-PAGE` | txt 356–366 | KTR en fazla 30 sayfa | `reports/` | Teslim öncesi PDF sayfa sayımı | Bağlandı |
| `DEL-CALENDAR` | txt 228–268 | Güncel teslim/sonuç takvimi | `TARIHLER.md`, `docs/delivery_video_plan.md` | Kaynak tarih karşılaştırması | Bağlandı |
| `DEL-VIDEO-FORMAT` | txt 402–424 | Tek YouTube, 720p+, 2–5 dk, sıralı gösterim | `docs/delivery_video_plan.md` | Video paketleme kontrol listesi | Fiziksel video bekliyor |

## Sistem ve güvenlik gereksinimleri

| ID | Şartname kaynağı | Gereksinim | Modül/karar | Test | Telemetri/Video | Durum |
| --- | --- | --- | --- | --- | --- | --- |
| `SYS-DIM-100` | txt 468–469 | Her sistem boyutu 100 cm’den küçük | Mekanik CAD | Ölçüm tutanağı | Final manifest | Mekanik ölçüm bekliyor |
| `SYS-RANGE-5-10-15` | txt 475–480 | 5/10/15 m hedef imha | Mission Core, perception, TFA50-L | `LID-005`, `REL-003` | Range + `FireIntent`, `VID-Y2/Y6` | HIL/fiziksel bekliyor |
| `SAFE-MOTION-ZONE` | txt 491–495 | Harekete yasak alan | Backend Safety Gate | `tests/test_phase4_safety.py`; `SAFE-013` | `BLOCKED_MOTION_ZONE` | Unit doğrulandı; fiziksel bekliyor |
| `SAFE-FIRE-ZONE` | txt 491–495 | Atışa yasak alan | Backend Safety Gate | `tests/test_phase4_safety.py`; `SAFE-013/017` | `BLOCKED_FIRE_ZONE` | Unit doğrulandı; fiziksel bekliyor |
| `SAFE-ENERGY` | txt 496–504 | Güvenlik uygulanmadan enerji verilmemesi | ADR-001/002, runtime gate, fiziksel interlock | `tests/test_runtime_mode.py` | BOOT `runtimeMode`, readiness | Yazılım kapısı var; fiziksel bekliyor |
| `SAFE-ESTOP` | txt 636–637 ve PDF §6 | Güvenli konumda kablolu Acil Durdur | Pico + emniyet rölesi + Backend | `test_set_estop_blocks_all_commands`, `test_estop_endpoint_activates_and_blocks`, `SAFE-015/017` | `ESTOP_CHANGE`, `VID-Y3/Y4` | Mock doğrulandı; HIL bekliyor |
| `SAFE-CLIENT-AUTHORITY` | mimari türetim | UI güvenlik modunu gevşetemez | `OperatorService`, runtime factory | `test_live_service_ignores_client_dry_run_override`, `tests/test_runtime_mode.py` | BOOT/runtime audit | Unit doğrulandı |
| `SAFE-NO-EXPLOSIVE` | PDF §6 | Patlayıcı hedef imha çözümü kullanılmaması | Mekanik/elektronik tasarım | Güvenlik incelemesi | Malzeme listesi/tutanak | Fiziksel inceleme bekliyor |

## Görev ve mod gereksinimleri

| ID | Şartname kaynağı | Gereksinim | Modül | Test | Telemetri/Video | Durum |
| --- | --- | --- | --- | --- | --- | --- |
| `MODE-MANUAL` | txt 609–617 | Manuel Mod kullanıcı girdisiyle çalışır | Mission Core, Operator Panel | `test_scenario_01_manual_mode_override_and_safety_gate` | `ModeRequest`, `ManualAimCommand`, `VID-Y1` | Mock doğrulandı |
| `MODE-AUTO` | txt 611–623 | Otonom Mod tanımlı görevleri otomatik yürütür | Mission Core, perception | `test_scenario_02_autonomous_tracking_friend_foe_discrimination` | Track/Mode/Fire olayları | Mock kısmi |
| `MODE-TRANSITION` | txt 611–617 | Mod geçişi kullanıcı denetimindedir | Backend `ModeRequest` | Operator API mode testleri | `ModeRequest` | Unit doğrulandı |
| `STAGE-1` | txt 578–585, 615–617 | Durağan hedef, iki eksen, Manuel Mod | Backend/frontend/perception | Stage 1 scenario ve timer testleri | Stage/Manual/Fire, `VID-Y2` | Mock doğrulandı; fiziksel bekliyor |
| `STAGE-2` | txt 589–595, 617–620 | Otonom tespit/takip; parkurdan çıkmadan imha | Backend/frontend/perception | Stage 2 scenario | Track/Fire/round | Mock doğrulandı |
| `STAGE-3` | txt 599–605, 621–623 | Doğru hedefi doğru menzilde otonom imha | Backend/perception/TFA50-L | target/range gate ve scenario testleri | Classification/range/Fire | Mock kısmi; gerçek sensör bekliyor |
| `ZERO-REFERENCE` | txt 624–627 | Başlangıçta yaw/elev 0° | Pico/encoder calibration | `tests/test_phase5_firmware.py`, HIL zero testi | CAN v1 encoder status | Host doğrulandı; HIL bekliyor |
| `MAINT-BUDGET` | txt 628–635 | Toplam 10 dk; istek başına en az 30 sn | Backend maintenance state | `MaintenanceBudgetTest` | `MAINTENANCE_START/END` | Unit doğrulandı |

## Görev Kabiliyeti Gösterimi Videosu

| ID | Şartname kaynağı | Yetenek | Test/kanıt bağı | Durum |
| --- | --- | --- | --- | --- |
| `VID-Y1-UI` | txt 384–389 | Kullanıcı komut arayüzleri | Frontend unit/Playwright + API command events + hash’li session evidence | Yazılım mevcut; entegre çekim bekliyor |
| `VID-Y2-15M` | txt 390 | Durağan 15 m balon imhası | `SYS-RANGE-5-10-15`, Safety + Fire event | Fiziksel bekliyor |
| `VID-Y3-ESTOP-MOTION` | txt 391–392 | Hareket sırasında Acil Durdur | `SAFE-ESTOP`, motor/encoder HIL | HIL/fiziksel bekliyor |
| `VID-Y4-ESTOP-FIRE` | txt 393 | Ateş sırasında Acil Durdur | `SAFE-ESTOP`, güvenli yapay yük | HIL/fiziksel bekliyor |
| `VID-Y5-TRACK` | txt 394–395 | Yan/yükseliş hareketli hedef takibi | Perception track + pan/tilt digital twin feedback + session replay | Mock doğrulandı; gerçek hedef bekliyor |
| `VID-Y6-CLASSIFY` | txt 396–400 | 5/10/15 m tip sınıflandırma *(opsiyonel)* | Camera + TFA50-L + classification | Gerçek veri bekliyor |

## WP-05 kayıt ve kanıt zinciri

| ID | Kaynak | Gereksinim | Modül/test | Durum |
| --- | --- | --- | --- | --- |
| `TRACE-SESSION` | Video §2.4.4 ve mimari türetim | Gösterim aralığı event/sensör/video ile ilişkilendirilebilir | `telemetry_session.py`, `test_media_common_timebase_replay_and_evidence_package` | Yazılım/mock doğrulandı |
| `TRACE-INTEGRITY` | Video §2.4.4 ve kanıt güvenilirliği | Eksik/bozuk kayıt kanıt sayılmaz | `verify_session`, `verify_evidence`, düşük disk/retention/tamper testleri | Yazılım doğrulandı |
| `TRACE-REPLAY` | Mimari türetim | Replay fiziksel çıkış üretemez ve sıralama deterministiktir | `replay_session`, `tests/test_telemetry_session.py` | Yazılım doğrulandı |

## Değişiklik yönetimi

- Şartname değişirse önce `docs/requirements_source.md` güncellenir.
- Requirement ID silinmez; kaldırılan gereksinim `superseded` olarak işaretlenir.
- Yeni test/telemetri/video kanıtı ilgili satıra eklenir.
- HIL veya fiziksel kanıt olmadan “tamamlandı” yazılmaz.
