# Faz 8 uygulama ve sadeleştirme planı

Bu plan, `docs/imalat_oncesi_yazilim_todo.md` içindeki Faz 8 maddelerini
mevcut davranışı koruyarak tamamlamak için yazılmıştır. Şartnamenin görev
akışları son otoritedir; bu faz yalnız yazılım/SIM kanıtı üretir, fiziksel
imalat veya saha kabulü kanıtı sayılmaz.

## Önce kilitlenecek davranış

1. Aşama 1'in 300 saniyelik sayacı, manuel yönelim için deadman zorunluluğu
   ve kullanıcı kaynaklı `FireIntent` davranışı regression testleriyle korunur.
2. Aşama 2'de hedef tipi bilinmeyen gerçek perception izlerinin de öncelik
   hesabına girebildiği; Aşama 3'te ise dost/düşman, tip ve ölçülmüş menzil
   kapılarının birlikte uygulandığı test edilir.
3. Bakımın en az 30 saniye yazdığı, toplam 600 saniye bütçeyi kullandığı;
   stop/resume ve mandallı E-Stop geçişlerinin görev sayacını güvenli biçimde
   durdurup yeniden başlattığı test edilir.
4. HTTP uçtan uca testleri gerçek `MissionCore` ve gerçek HTTP cevaplarıyla
   Aşama 1/2/3, bakım, stop/resume ve E-Stop akışlarını doğrular.

## Küçük ve geri alınabilir değişiklikler

1. Görev geçişleri saf ve bağımsız bir `MissionFlow` durum makinesinde
   toplanır; bütün mutasyonlar mevcut tek-sahipli `MissionCore` thread'inde
   kalır.
2. `OperatorService`, Safety Gate'i atlamadan görev durum makinesini,
   görev/tur ilerlemesini, hedef sırasını ve geçiş nedenlerini snapshot ve
   telemetriye ekler.
3. Operatör panelinin SSE + snapshot eşitlemesi bir hook'a ayrılır. Bağlı
   panel hedef, güvenlik, bakım ve stop durumunu yalnız backend snapshot'ından
   okur; bağlantı yokken fail-closed ve boş görünür.
4. Manuel yönelim/deadman, görev kontrolü, gerçek track listesi ve birleşik
   sağlık özeti mevcut bileşenlere bölünür. Yeni bağımlılık eklenmez ve mevcut
   görsel dil korunur.
5. UI, sentetik hedef kimliği veya optimistik E-Stop/bakım durumu üretmez.
   Komut sonrası backend cevabı/SSE snapshot'ı beklenir; restart'ta `runId`
   değişikliği tam snapshot yeniden eşitlemesi olarak ele alınır.

## Tamamlanma kapısı

- Python unit ve HTTP E2E testleri,
- frontend unit testleri, TypeScript typecheck ve üretim build'i,
- Playwright operatör senaryoları,
- `docs/imalat_oncesi_yazilim_todo.md` Faz 8 kutularının yalnız kanıtlar
  geçtikten sonra işaretlenmesi,
- fiziksel E-Stop, gerçek LiDAR/kamera, MCU/CAN ve saha testlerinin Faz 9+
  riski olarak açık bırakılması.
