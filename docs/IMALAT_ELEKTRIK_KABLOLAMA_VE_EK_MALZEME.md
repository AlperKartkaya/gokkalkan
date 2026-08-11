# Gökkalkan İmalat Elektrik ve Kablolama Belgesi — Yönlendirme

> **Durum:** Bu eski Markdown kılavuzu kullanımdan kaldırılmıştır.

Önceki sürüm, artık geçerli olmayan Siemens 3SK, çift kanal E-Stop ve LP1K1201BD mimarisini içeriyordu. Satın alma, kablolama veya yazılım pin kararı için kullanılmamalıdır.

Güncel ve bağlayıcı repo belgeleri:

1. `Gökkalkan Malzeme Listesi - Nihai Kablolama.xlsx` — nihai BOM/kablolama tablosu
2. `docs/IMALAT_EK_MALZEME_SIPARIS_LISTESI.html` — satın alma ve çıkarma kararları
3. `docs/IMALAT_KOMPONENT_BAGLANTI_REHBERI.html` — imalat bağlantı handbook'u
4. `docs/YAZILIM_DONANIM_UCTAN_UCA_ENTEGRASYON_PLANI.md` — yazılım/firmware uygulama ve kabul sırası
5. `docs/usb_serial_mcu_protocol.md` ve `docs/adr/005-pi-pico-usb-serial.md` — Pi↔Pico taşıma sözleşmesi

Aktif asgari emniyet mimarisi:

```text
RSP +24 V → 1 A kontrol sigortası → tek NK E-Stop → X
X → anlık 1NA START → LP1K1210BD A1
LP1K1210BD yardımcı 1NA → START'a paralel mühürleme
A2 → kontrol 0 V; LA4KE1B → A1/A2
X → 24 V girişli PC817 → Pico ESTOP_SAFE_SENSE
```

Bu mimari çift kanallı veya SIL dereceli olarak tanımlanmaz. İmalat sırasında imzalanan as-built şema ve fiziksel cihaz etiketleri, repo içindeki örnek satıcı bağlantılarından üstündür.
