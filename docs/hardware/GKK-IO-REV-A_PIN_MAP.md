# GKK-IO-REV-A Pin Haritası

> **Durum:** Mantıksal GPIO ataması tamamlandı; elektriksel aktif seviyeler,
> izolasyon ve boot/reset ölçümleri fiziksel kabul bekliyor. Bu tablo kablo
> renklerinin veya arayüz kartı pinlerinin ölçümsüz kabul edildiği anlamına gelmez.

| Sinyal | Pico GPIO | Aktif seviye | Elektrik alanı / arayüz | Durum |
|---|---:|---|---|---|
| `ESTOP_SAFE_SENSE` | `GP8` (pin 11) | PC817 ölçümü bekleniyor | 24 V `X` → PC817 → Pico 3,3 V | Atandı / ölçüm açık |
| `FIRE_INTERLOCK` | `GP9` (pin 12) | Ölçüm bekleniyor | İzole airsoft kesme feedback | Atandı / ölçüm açık |
| `TRIGGER_FEEDBACK` | `GP10` (pin 14) | Ölçüm bekleniyor | İzole kuru kontak feedback | Atandı / ölçüm açık |
| `FIRE_OUT` | `GP11` (pin 15) | Varsayılan pasif; ölçüm bekleniyor | Pico → PhotoMOS/izole NO | Atandı / ölçüm açık |
| `PAN_LIMIT_NC` | `GP12` (pin 16) | NC/kopukta fault | İzole saha girişi | Atandı / ölçüm açık |
| `TILT_LIMIT_NC` | `GP13` (pin 17) | NC/kopukta fault | İzole saha girişi | Atandı / ölçüm açık |
| PAN `STEP/DIR/ENA` | `GP2/GP3/GP4` (pin 4/5/6) | Arayüz ölçümü bekleniyor | İzole/open-collector → DM542 | Atandı / ölçüm açık |
| TILT `STEP/DIR/ENA` | `GP5/GP6/GP7` (pin 7/9/10) | Arayüz ölçümü bekleniyor | İzole/open-collector → DM542 | Atandı / ölçüm açık |
| PAN encoder `A/B` | `GP14/GP15` (pin 19/20) | Model ölçümü bekleniyor | Receiver/izolasyon | Atandı / ölçüm açık |
| TILT encoder `A/B` | `GP16/GP17` (pin 21/22) | Model ölçümü bekleniyor | Receiver/izolasyon | Atandı / ölçüm açık |

## Ölçüm kaydı

| Test | Beklenen | Ölçülen | Tarih / imza |
|---|---|---|---|
| `X=24 V` → PC817 çıkışı | Kaydedilecek | `UNVERIFIED` | |
| `X=0 V` → PC817 çıkışı | Fail-closed | `UNVERIFIED` | |
| PC817 çıkış kablosu kopuk | Fail-closed | `UNVERIFIED` | |
| Boot/reset `STEP/ENA/FIRE` | Pasif | `UNVERIFIED` | |
| USB + haricî besleme backfeed | Yok | `UNVERIFIED` | |

Mantıksal atamalar `firmware/pico/include/board_config.hpp` ile eşleşir. Ölçüm
satırları doldurulup iki kişi tarafından kontrol edilmeden LIVE fiziksel çıkış
kabulü verilmez.
