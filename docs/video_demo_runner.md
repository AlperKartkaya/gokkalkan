# Görev Kabiliyeti Gösterim Videosu — Pi Oturum Komutları

Bu komutlar kamera, algı, Arduino Uno ve operatör API'si çalışan Pi üzerinde ilgili
video yeteneği için zaman damgalı bir **kanıt oturumu** açar. Komut fiziksel
hareket, atış, Acil Durdur reseti veya hedef tespiti üretmez; bunlar gerçek
operatör ve donanım olayları olarak video/telemetride görünmelidir.

## Başlatma

Her yetenek için aynı komut kullanılır:

```bash
ssh -i ~/.ssh/gokkalkan_pi gokkalkan@gokkalkan.local \
  'sudo -u gokkalkan /opt/gokkalkan/.venv/bin/gokkalkan video-demo run --capability Y5'
```

`Y5` yerine `Y1`–`Y7` kullanılabilir. Çıktıdaki `runId` ve `path`, çekimin
kanıt klasörüdür. Pi'de varsayılan kayıt kökü:

```text
/var/lib/gokkalkan/video-runs/<run-id>/start.json
```

Komut `/health`, `/state` ve gerekirse `/readiness` endpointlerinden **mevcut
durumu** kaydeder. Endpoint erişilemezse başarısız olur; sağlıklıymış gibi
rapor üretmez.

Operatör ve Algı paneli, Pi üzerindeki en son oturumu
`GET /video-demo/session` üzerinden her üç saniyede bir salt-okunur olarak
gösterir. Paneldeki sarı video bandı fiziksel başarı göstergesi değildir.

Çekim bittiğinde aynı klasör için bitiş kanıtını alın:

```bash
ssh -i ~/.ssh/gokkalkan_pi gokkalkan@gokkalkan.local \
  'sudo -u gokkalkan /opt/gokkalkan/.venv/bin/gokkalkan video-demo finish \
    --run-path /var/lib/gokkalkan/video-runs/<run-id>'
```

Bu komut `finish.json` içine bitiş anındaki `/health`, `/state` ve `/events`
cevaplarını kaydeder. Ayrıca başlangıçtan sonra oluşan olayları ayırır ve Y3/Y4
için fiziksel E-Stop, hareket/ateş niyeti; Y5/Y6 için track güncellemesi gibi
**gözlemleri** raporlar. Fiziksel başarı hükmü vermez.

## Manuel işaretleme sınırı

Kamera görüntüsü üzerinde operatörün çizdiği bir kare yalnızca açıkça
`Operatör ROI / Görsel İnceleme` olarak sunulabilir. Bu işaretleme AI tespiti,
sınıflandırma, menzil ölçümü veya otonom angajman verisi değildir; `TrackState`
üretmez ve Safety Gate'e giremez.

## Video sırası

Şartname sırası korunur: `Y1`, `Y2`, `Y3`, `Y4`, `Y5`, `Y6`, ardından
gösterilecekse opsiyonel `Y7`. Tek video 720p veya üzeri ve 2–5 dakika olmalıdır.
