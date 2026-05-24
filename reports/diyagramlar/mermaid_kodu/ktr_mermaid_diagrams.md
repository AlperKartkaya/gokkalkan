# KTR Mermaid Diyagramları

Bu dosyadaki Mermaid blokları `reports/ktr_v1.docx` içindeki şekil yer tutucularıyla birebir eşleşir.

## Şekil 1 yazilim_blok_semasi

```mermaid
flowchart LR
    Camera["Kamera"] --> Perception["Algılama\nhedef adayı / takip / sınıf"]
    UI["Operatör Arayüzü\nPySide6"] --> Backend["Backend Görev Çekirdeği\nmod + aşama yönetimi"]
    Perception --> Backend
    Backend --> Safety["Safety Gate\nE-stop + yasak alan + menzil kapısı"]
    Safety --> Adapter["Hardware Adapter\nserial/CAN"]
    Adapter --> MCU["MCU + pan/tilt + imha mekanizması"]
    MCU --> Adapter
    Adapter --> Backend
    Safety --> Logger["Telemetry Logger\nJSONL/CSV"]
    Backend --> Logger
    Perception --> Logger
    Backend --> UI
    Safety --> UI
```

## Şekil 2 hedef_tespit_takip_akisi

```mermaid
flowchart TD
    Frame["Kameradan kare yakala"] --> Pre["Ön işleme\nROI, renk uzayı, filtreleme"]
    Pre --> Candidate["Hedef adayı çıkar\nkontur/şekil/alan"]
    Candidate --> Track["İz güncelle\nmerkez, hız, son görülme"]
    Track --> Stage{"Aktif aşama"}
    Stage -->|Aşama 2| NoClass["Tip sınıflandırma yok\nöncelik + takip"]
    Stage -->|Aşama 3| Class["Dost-düşman + hedef tipi\nrenk/şekil/model skoru"]
    NoClass --> Output["TrackState"]
    Class --> Range["Menzil kapısı kontrolü"]
    Range --> Output
```

## Şekil 3 - guvenlik-kapisi-akisi

```mermaid
flowchart TD
    Cmd["Hareket/atış komutu"] --> EStop{"Acil Durdur aktif mi?"}
    EStop -->|Evet| BlockE["Engelle: BLOCKED_ESTOP"]
    EStop -->|Hayır| Motion{"Harekete yasak alan ihlali?"}
    Motion -->|Evet| BlockM["Engelle: BLOCKED_MOTION_ZONE"]
    Motion -->|Hayır| Fire{"Atış komutu mu?"}
    Fire -->|Hayır| Allow["İzin ver ve logla"]
    Fire -->|Evet| FireZone{"Atışa yasak alan ihlali?"}
    FireZone -->|Evet| BlockF["Engelle: BLOCKED_FIRE_ZONE"]
    FireZone -->|Hayır| Target{"Hedef/mod/menzil kapısı uygun mu?"}
    Target -->|Hayır| BlockT["Engelle: BLOCKED_TARGET_GATE"]
    Target -->|Evet| Allow
    BlockE --> Log["Telemetry log"]
    BlockM --> Log
    BlockF --> Log
    BlockT --> Log
    Allow --> HW["Donanım adaptörü"]
```

## Şekil 4 - sistem-kullanim-durumu-diyagrami

```mermaid
flowchart LR
    Operator["Operatör"] --> UC1["Manuel hedef imhası"]
    Operator --> UC2["Otonom modu başlat"]
    Referee["Hakem / güvenlik"] --> UC3["Acil Durdur"]
    System["Gökkalkan Sistemi"] --> UC4["Otonom sürü takibi"]
    System --> UC5["Dost-düşman ayrımı"]
    System --> UC6["Görev/video kanıtı kaydı"]
    UC2 --> UC4
    UC4 --> UC5
    UC1 --> UC6
    UC3 --> UC6
    UC5 --> UC6
```

## Şekil 5 - sistem_mod_durum_diyagrami

```mermaid
stateDiagram-v2
    [*] --> SafeIdle
    SafeIdle --> ManualMode: operatör manuel seçer
    SafeIdle --> AutonomousSearchTrack: operatör otonom seçer
    ManualMode --> EngagementCandidate: kullanıcı atış/yönlenme komutu
    AutonomousSearchTrack --> EngagementCandidate: hedef + görev kuralı uygun
    EngagementCandidate --> ManualMode: atış tamamlandı / reddedildi
    EngagementCandidate --> AutonomousSearchTrack: hedef kaybedildi / tur devam
    ManualMode --> BlockedSafetyLock: E-stop / yasak alan / hata
    AutonomousSearchTrack --> BlockedSafetyLock: E-stop / yasak alan / hata
    EngagementCandidate --> BlockedSafetyLock: güvenlik kapısı reddi
    BlockedSafetyLock --> SafeIdle: reset + güvenli koşullar
    SafeIdle --> MaintenancePause: bakım talebi
    MaintenancePause --> SafeIdle: bakım bitti
```

## Şekil 6 - asama1_manuel_akis

```mermaid
flowchart TD
    Start["Aşama 1 başlat"] --> Order["Hakem hedef sırasını verir"]
    Order --> UI["UI hedef sırasını gösterir"]
    UI --> Aim["Operatör pan/tilt ile hedefe yönelir"]
    Aim --> Confirm{"Operatör atış komutu verdi mi?"}
    Confirm -->|Hayır| Aim
    Confirm -->|Evet| Safety["Safety Gate kontrolü"]
    Safety -->|Engel var| Block["Atış engellenir ve gerekçe gösterilir"]
    Safety -->|Uygun| Fire["Atış tetiklenir"]
    Fire --> Log["Hedef/atış olayı loglanır"]
    Log --> Next{"Sırada hedef kaldı mı?"}
    Next -->|Evet| UI
    Next -->|Hayır| Done["Aşama 1 tamamlandı"]
```

## Şekil 7 - asama2_otonom_takip_imha

```mermaid
flowchart TD
    Start["Aşama 2 başlat"] --> Auto["Operatör otonom moda alır"]
    Auto --> Detect["Üç koldaki hedefleri tespit et"]
    Detect --> Track["Hedefleri takip et"]
    Track --> Priority["Tur bitmeden imha önceliği belirle"]
    Priority --> Aim["Pan/tilt yönlenme isteği üret"]
    Aim --> Safety["Safety Gate kontrolü"]
    Safety -->|Engel var| LogBlock["Engel/hata logla"]
    Safety -->|Uygun| Fire["Atış tetikle"]
    Fire --> Result["Vuruş / kaçırma olayını kaydet"]
    Result --> Round{"Tur bitti mi?"}
    Round -->|Hayır| Detect
    Round -->|Evet| Fail{"3 tur hedef vuramama var mı?"}
    Fail -->|Evet| Stop["Aşama başarısız"]
    Fail -->|Hayır| Done["Sonraki tur / aşama tamam"]
```

## Şekil 8 - asama3_dost_dusman_menzil

```mermaid
flowchart TD
    Start["Aşama 3 başlat"] --> Detect["Hedefleri tespit ve takip et"]
    Detect --> Class["Dost-düşman ve hedef tipi belirle"]
    Class --> Enemy{"Düşman hedef mi?"}
    Enemy -->|Hayır| Hold["Takip et, atış engelle"]
    Enemy -->|Evet| Range{"Tip için menzil uygun mu?"}
    Range -->|Hayır| HoldRange["Menzil uygun olana kadar takip"]
    Range -->|Evet| Engage["Angajman isteği üret"]
    Engage --> Safety["Safety Gate kontrolü"]
    Safety -->|Engel var| Block["Engelle ve logla"]
    Safety -->|Uygun| Fire["Atış tetikle"]
    Fire --> Result["Vuruş/kaçırma ve ceza durumunu kaydet"]
    Hold --> Detect
    HoldRange --> Detect
    Block --> Detect
```

## Şekil 9 - ui_backend_donanim_sekans

```mermaid
sequenceDiagram
    participant O as Operatör
    participant UI as PySide6 UI
    participant B as Backend
    participant S as Safety Gate
    participant H as Hardware Adapter
    participant M as MCU/Pan-Tilt

    O->>UI: Mod/komut seçer
    UI->>B: mode_request / manual_command
    B->>S: hareket veya atış isteği
    S-->>B: allowed / blocked + gerekçe
    alt allowed
        B->>H: HardwareCommand
        H->>M: seri/CAN komutu
        M-->>H: durum geri bildirimi
        H-->>B: command_result
    else blocked
        B-->>UI: kilit nedeni
    end
    B-->>UI: görev durumu
```

## Şekil 10 - perception_backend_safety_sekans

```mermaid
sequenceDiagram
    participant C as Kamera
    participant P as Perception
    participant B as Backend
    participant E as Engagement Manager
    participant S as Safety Gate
    participant L as Telemetry Logger

    C->>P: frame
    P->>P: aday çıkar + takip güncelle
    P->>B: TrackState
    B->>E: aşama kuralı + hedef durumu
    E->>S: EngagementRequest
    S-->>E: allowed / blocked
    E->>L: karar ve gerekçe
    E-->>B: angajman sonucu
```

## Şekil 11 - acil_durdur_kesme_sekans

```mermaid
sequenceDiagram
    participant Btn as Acil Durdur
    participant S as Safety Gate
    participant H as Hardware Adapter
    participant M as MCU/İmha Hattı
    participant UI as Operatör Arayüzü
    participant L as Telemetry Logger

    Btn->>S: E-stop aktif
    S->>H: stop_motion + fire_disable
    H->>M: komutları kes
    M-->>H: güvenli durum bildirimi
    H-->>S: stop confirmed
    S->>UI: BLOCKED_ESTOP göster
    S->>L: E-stop olayı kaydet
```
