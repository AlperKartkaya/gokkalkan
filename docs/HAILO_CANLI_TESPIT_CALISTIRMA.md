# AI HAT+ ile canlı kamera tespiti — Aşama 1 smoke kabulü

Bu prosedür yalnız **Pi 5 + AI HAT+ (Hailo-8) + Camera Module 3** içindir.
Pico, motor sürücüsü, LiDAR ve airsoft bağlanmaz; bu işlem hiçbir hareket veya
FIRE yetkisi vermez. Kullanılan model `SYNTHETIC_RESEARCH_ONLY` durumundadır:
canlı görüntüde kutu/etiket görmek için kullanılabilir, yarışma/LIVE angajman
kabulü değildir.

## 1. Eğitim ağırlığını ONNX'e çıkar

Geliştirme bilgisayarında, repo kökünde:

```bash
npm run model:export:hailo
shasum -a 256 artifacts/hailo/target_detector.onnx
```

Bu işlem `artifacts/hailo/target_detector.onnx` ve yanında sınıf, girdi boyutu
ve SHA-256 bilgisini taşıyan `target_detector.export.json` üretir.

## 2. ONNX'i HEF'e derle

HEF derlemesi Raspberry Pi üzerinde yapılmaz. Hailo Dataflow Compiler ve Hailo
Model Zoo kurulu **x86_64 Linux** derleme makinesinde ONNX'i ve calibration
görüntülerini aynı dizin yapısıyla bulundurun, sonra repo kökünde çalıştırın:

```bash
bash scripts/compile_hailo_hef.sh \
  artifacts/hailo/target_detector.onnx \
  perception/dataset/generated/yolo_cad_research/images/train \
  artifacts/hailo/target_detector.hef
```

Beklenen çıktı `artifacts/hailo/target_detector.hef` dosyası ve SHA-256
satırıdır. Komut `hailomz` bulamazsa doğru ortamda değilsiniz. Komut Hailo
Model Zoo'nun YOLOv8s YAML'ını ve `--classes 7 --hw-arch hailo8` ayarını
kullanır; HEF'in Hailo NMS çıktısı taşıması gerekir.

## 3. Pi'ye kur ve perception'ı başlat

Geliştirme bilgisayarında, Pi yeniden ağdayken:

```bash
npm run pi:deploy -- --host gokkalkan@<PI_IP> \
  --identity ~/.ssh/gokkalkan_pi \
  --hef artifacts/hailo/target_detector.hef \
  --runner-factory gokkalkan_hailo_runtime:create_batch_runner
```

Bu komut HEF'i `/opt/gokkalkan/perception/models/target_detector.hef` yoluna
kopyalar, canlı perception kapısını açar ve `gokkalkan-perception.service`i
başlatır. Runtime, Picamera2'nin resmi Hailo API'sini kullanır; her Hailo NMS
çıktısını 7-sınıflı Gökkalkan sözleşmesine dönüştürür.

Pi üzerindeki doğrulama komutları:

```bash
hailortcli fw-control identify
systemctl is-active gokkalkan-perception.service
curl -fsS http://127.0.0.1:8090/health
journalctl -u gokkalkan-perception.service -n 100 --no-pager
```

Sağlık JSON'ında aşağıdakiler birlikte görünmelidir:

- `camera.hasFrame: true`
- `accelerator.available: true`
- `detector.inferenceReady: true`

## 4. Operatör panelinde gör

Pi ekranında paneli açıyorsanız `http://127.0.0.1:4173` adresini açın.
Başka bilgisayardan görüntülemek için önce SSH tüneli kurun:

```bash
ssh -N -L 4173:127.0.0.1:4173 -L 8088:127.0.0.1:8088 \
  -i ~/.ssh/gokkalkan_pi gokkalkan@<PI_IP>
```

Ardından `http://127.0.0.1:4173/?cameraStream=http://127.0.0.1:8090/camera/live.mjpg`
adresini açın ve **AI TESPİT** görünümüne geçin. Tespit kutuları backend
track telemetrisi üzerinden görüntünün üzerine çizilir.

## Başarısızlıkta hızlı teşhis

| Belirti | İlk kontrol |
|---|---|
| `Hailo-8` görünmüyor | AI HAT+ fiziksel montajı ve `hailo-all` paketi |
| `hasFrame=false` | `rpicam-hello --list-cameras`, perception journal |
| `inferenceReady=false` | HEF yolunu, 7 sınıf/NMS sözleşmesini ve journal'ı kontrol et |
| Görüntü var, kutu yok | Doğru fiziksel hedef, ışık ve model güven eşiği gerekir; bu model yalnız sentetik veride eğitilmiştir |

Hailo Model Zoo'nun YOLOv8 eğitim notu ONNX→HEF için `--ckpt`,
`--calib-path`, YAML ve `--classes` kullanımını tanımlar; Picamera2 Hailo
örneği NMS çıktısını sınıf başına `[y0, x0, y1, x1, score]` olarak işler.
