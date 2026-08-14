# ACTION REQUIRED — AR-01 ve AR-02

> **Durum:** FAZ 0 ve FAZ 1 tamamlandı; FAZ 2 başlamadan kullanıcı girdisi bekleniyor.
> **Kaynak hash:** `9f696bf7aa8c5c0dc2fa1e733266e6e9c274494bc2f210c3bc40b8975fb47028`

## AR-01 — CAD kaynağı ve kullanım izni

Aşağıdaki üç bilgiyi doğrulayın. Gizli parola/token veya kişisel erişim anahtarı
repoya yazmayın.

1. **Kaynak/sahip:** `Modeller.3mf` dosyasını kim hazırladı veya nereden aldınız?
2. **Kullanım izni:** Takım bu modelleri dönüştürme, render alma, model eğitimi ve
   takım içi paylaşım için kullanabilir mi?
3. **Ekip erişimi:** Dosyanın takım üyelerinin erişebileceği kalıcı konumu nedir?
   Google Drive/OneDrive/GitHub Release/artifact deposu olabilir. Normal Git
   geçmişine 26 MB binary eklemeyin. Süresi dolan tek kullanımlık URL vermeyin.

### Cevap şablonu

```text
AR-01
Kaynak/sahip: ...
Kullanım izni: ...
Kalıcı ekip bağlantısı veya artifact kimliği: ...
```

Bu cevap geldikten sonra ajan
`perception/synthetic/config/cad_source.json` içindeki şu alanları dolduracak:

- `sourceUri`
- `owner`
- `licenseOrPermission`
- `status = VERIFIED_SHARED_SOURCE`

İndirilen/paylaşılan dosyanın SHA-256 değeri yukarıdaki hash ile aynı değilse FAZ
2 başlamaz.

## AR-02 — Her modelin burun ve üst ekseni

Aşağıdaki yerel contact sheet dosyalarını açın:

- `perception/synthetic/generated/contact_sheets/drone_source_axes.png`
- `perception/synthetic/generated/contact_sheets/f16_source_axes.png`
- `perception/synthetic/generated/contact_sheets/helicopter_source_axes.png`
- `perception/synthetic/generated/contact_sheets/missile_source_axes.png`

Her karttaki `KAMERA +X TARAFINDA` ifadesi, kameranın modelin kaynak `+X`
tarafında olup merkeze baktığını söyler. Kartın altındaki `sağ=... yukarı=...`
notu ekranda sağa ve yukarı gitmenin hangi kaynak eksene karşılık geldiğini
belirtir.

Her model için iki eksen seçin:

- **BURUN (`noseAxis`)**: modelin burnunun/ileri yönünün baktığı kaynak eksen;
- **ÜST (`upAxis`)**: hedef yarışma düzeninde normal pozdayken üst yüzeyinin
  baktığı kaynak eksen.

`noseAxis` ile `upAxis` aynı veya birbirinin tersi olamaz; birbirine dik olmalıdır.
Füze geometrisi burun etrafında yaklaşık simetrik görünüyorsa `upAxis`, yarışmada
kullanılacak fin/askı yönünü sabitleyen roll referansı olarak seçilmelidir.

### Cevap şablonu

```text
AR-02
Drone: noseAxis=..., upAxis=...
F16: noseAxis=..., upAxis=...
Helikopter: noseAxis=..., upAxis=...
Füze: noseAxis=..., upAxis=...
Füze yarışma montajı: dikey / yatay; açıklama=...
```

Kullanılabilecek değerler yalnız şunlardır:

```text
+X  -X  +Y  -Y  +Z  -Z
```

### Contact sheet yeterli değilse

Yalnız belirsiz kalan modeli Bambu Studio'da açın:

1. Modeli seçin.
2. Taşı/Rotate aracını açıp X/Y/Z gismosunu görünür bırakın.
3. Perspektifi kapatıp mümkünse ortografik görünüş kullanın.
4. Bir burun görünüşü ve bir üst görünüş ekran görüntüsü alın.
5. Dosyaları `docs/evidence/cad_orientation/` altına koyun veya sohbete ekleyin.
6. Modeli döndürüp/kaydedip kaynak `Modeller.3mf` dosyasının üzerine yazmayın.

Blender kullanmanız şu anda gerekmiyor.

## Otomatik incelemede bulunan ek teknik durum

Drone, F16 ve Füze `lib3mf` geçerlilik/manifold kontrolünü geçti. Helikopter:

```text
isValid=false
isManifoldAndOriented=false
```

Bu durum AR-01/AR-02 için sizden ek işlem istemiyor. FAZ 2'de önce otomatik tanı
ve kontrollü onarım denenecek. Silueti değiştirmeden otomatik düzeltilemezse
yalnız Helikopter için ayrı Blender/Bambu Studio blocker'ı açılacak; kaynak dosya
sessizce değiştirilmemelidir.
