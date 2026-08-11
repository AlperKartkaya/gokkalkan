# GKK-IO-REV-A Pin Haritası

> **Durum:** `UNVERIFIED` — imzalı as-built şema ve fiziksel ölçüm gelmeden aktüatör build'i açılamaz.

| Sinyal | Pico GPIO | Aktif seviye | Elektrik alanı / arayüz | Durum |
|---|---:|---|---|---|
| `ESTOP_SAFE_SENSE` | `UNVERIFIED` | PC817 ölçümü bekleniyor | 24 V `X` → PC817 → Pico 3,3 V | Açık |
| `FIRE_INTERLOCK` | `UNVERIFIED` | Ölçüm bekleniyor | İzole airsoft kesme feedback | Açık |
| `TRIGGER_FEEDBACK` | `UNVERIFIED` | Ölçüm bekleniyor | İzole kuru kontak feedback | Açık |
| `FIRE_OUT` | `UNVERIFIED` | Ölçüm bekleniyor | Pico → PhotoMOS/izole NO | Açık |
| `PAN_LIMIT_NC` | `UNVERIFIED` | NC/kopukta fault | İzole saha girişi | Açık |
| `TILT_LIMIT_NC` | `UNVERIFIED` | NC/kopukta fault | İzole saha girişi | Açık |
| PAN `STEP/DIR/ENA` | `UNVERIFIED` | Sürücü kartı bekleniyor | İzole/open-collector → DM542 | Açık |
| TILT `STEP/DIR/ENA` | `UNVERIFIED` | Sürücü kartı bekleniyor | İzole/open-collector → DM542 | Açık |
| PAN encoder `A/B` | `UNVERIFIED` | Model ölçümü bekleniyor | Receiver/izolasyon | Açık |
| TILT encoder `A/B` | `UNVERIFIED` | Model ölçümü bekleniyor | Receiver/izolasyon | Açık |

## Ölçüm kaydı

| Test | Beklenen | Ölçülen | Tarih / imza |
|---|---|---|---|
| `X=24 V` → PC817 çıkışı | Kaydedilecek | `UNVERIFIED` | |
| `X=0 V` → PC817 çıkışı | Fail-closed | `UNVERIFIED` | |
| PC817 çıkış kablosu kopuk | Fail-closed | `UNVERIFIED` | |
| Boot/reset `STEP/ENA/FIRE` | Pasif | `UNVERIFIED` | |
| USB + haricî besleme backfeed | Yok | `UNVERIFIED` | |

`firmware/pico/include/board_config.hpp` ancak bu tablo fiziksel şemayla doldurulup iki kişi tarafından kontrol edildikten sonra güncellenir.
