# KTR Mermaid Diyagramları

Bu dosyadaki Mermaid blokları KTR yazılım mimarisi, arayüz ve görev akışı bölümleri için kaynak olarak kullanılır. Diyagramlarda `Operatör Paneli` ifadesi bilinçli olarak teknoloji-nötr tutulmuştur: mevcut simülatör React/Vite’tır; gerçek panelin ilk önerisi de React/Vite + backend API’dir, fakat Safety Gate ve donanım yetkisi backend tarafındadır.

## Şekil 1 yazilim_blok_semasi

```mermaid
flowchart LR
    OperatorUI["Operatör Paneli\nSimülatör / Gerçek Panel"] --> Api["Backend API\nREST + WebSocket"]
    Camera["Kamera"] --> Perception["Algılama\nhedef adayı / takip / sınıf"]
    RadarLidar["Radar / LiDAR Adapter\nTBD sensör arayüzü"] --> SensorFusion["Sensör Füzyonu\nmenzil + iz + sağlık"]
    Perception --> SensorFusion
    SensorFusion --> Backend["Backend Görev Çekirdeği\nmod + aşama + angajman"]
    Api --> Backend
    Backend --> Safety["Safety Gate\nE-stop + yasak alan + menzil + mod"]
    Safety --> Adapter["Hardware Adapter\nUART/RS422/CAN/Ethernet TBD"]
    Adapter --> MCU["MCU + Pan/Tilt + İmha Hattı"]
    MCU --> Adapter
    Adapter --> Backend
    Safety --> Logger["Telemetry Logger\nJSONL/CSV"]
    Backend --> Logger
    SensorFusion --> Logger
    Backend --> Api
    Api --> OperatorUI
    Safety --> Api
```

## Şekil 2 hedef_tespit_takip_akisi

```mermaid
flowchart TD
    Frame["Kameradan kare yakala"] --> Pre["Ön işleme\nROI, renk uzayı, filtreleme"]
    Pre --> Candidate["Hedef adayı çıkar\nkontur/şekil/alan"]
    Candidate --> Track["İz güncelle\nmerkez, hız, son görülme"]
    Sensor["Radar/LiDAR SensorFrame\nmenzil + açı + kalite"] --> Fuse["İz + menzil füzyonu"]
    Track --> Fuse
    Fuse --> Stage{"Aktif aşama"}
    Stage -->|Aşama 2| NoClass["Tip sınıflandırma zorunlu değil\ntakip + tur önceliği"]
    Stage -->|Aşama 3| Class["Dost-düşman + hedef tipi\nrenk/şekil/model skoru"]
    NoClass --> Output["TrackState"]
    Class --> Range["Menzil kapısı kontrolü"]
    Range --> Output
```

## Şekil 3 - guvenlik-kapisi-akisi

```mermaid
flowchart TD
    Cmd["Hareket/atış niyeti"] --> EStop{"Acil Durdur aktif mi?"}
    EStop -->|Evet| BlockE["Engelle: BLOCKED_ESTOP"]
    EStop -->|Hayır| Live{"Dry-run/live kilidi uygun mu?"}
    Live -->|Hayır| BlockLive["Engelle: BLOCKED_ARMING"]
    Live -->|Evet| Motion{"Harekete yasak alan ihlali?"}
    Motion -->|Evet| BlockM["Engelle: BLOCKED_MOTION_ZONE"]
    Motion -->|Hayır| Fire{"Atış niyeti mi?"}
    Fire -->|Hayır| Allow["İzin ver ve logla"]
    Fire -->|Evet| FireZone{"Atışa yasak alan ihlali?"}
    FireZone -->|Evet| BlockF["Engelle: BLOCKED_FIRE_ZONE"]
    FireZone -->|Hayır| Target{"Hedef/mod/menzil kapısı uygun mu?"}
    Target -->|Hayır| BlockT["Engelle: BLOCKED_TARGET_GATE"]
    Target -->|Evet| Allow
    BlockE --> Log["Telemetry log"]
    BlockLive --> Log
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
    Operator --> UC7["Gerçek panelden durum izle"]
    Referee["Hakem / güvenlik"] --> UC3["Acil Durdur / devam onayı"]
    System["Gökkalkan Sistemi"] --> UC4["Otonom sürü takibi"]
    System --> UC5["Dost-düşman ayrımı"]
    System --> UC6["Görev/video kanıtı kaydı"]
    Backend["Backend + Safety Gate"] --> UC8["Komut yetkilendir / engelle"]
    UC2 --> UC4
    UC4 --> UC5
    UC1 --> UC6
    UC3 --> UC6
    UC5 --> UC6
    UC7 --> UC8
    UC8 --> UC6
```

## Şekil 5 - sistem_mod_durum_diyagrami

```mermaid
stateDiagram-v2
    [*] --> SafeIdle
    SafeIdle --> ManualMode: operatör manuel seçer
    SafeIdle --> AutonomousSearchTrack: operatör otonom seçer
    ManualMode --> EngagementCandidate: kullanıcı atış/yönlenme niyeti
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
    Order --> UI["Operatör paneli hedef sırasını gösterir"]
    UI --> Aim["Operatör pan/tilt ile hedefe yönelir"]
    Aim --> Confirm{"Operatör FireIntent verdi mi?"}
    Confirm -->|Hayır| Aim
    Confirm -->|Evet| Backend["Backend komut niyetini alır"]
    Backend --> Safety["Safety Gate kontrolü"]
    Safety -->|Engel var| Block["Atış engellenir ve gerekçe gösterilir"]
    Safety -->|Uygun| Fire["Hardware Adapter imha hattı komutunu üretir"]
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
    Safety -->|Uygun| Fire["Hardware Adapter üzerinden atış tetikle"]
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
    Safety -->|Uygun| Fire["Hardware Adapter üzerinden atış tetikle"]
    Fire --> Result["Vuruş/kaçırma ve ceza durumunu kaydet"]
    Hold --> Detect
    HoldRange --> Detect
    Block --> Detect
```

## Şekil 9 - ui_backend_donanim_sekans

```mermaid
sequenceDiagram
    participant O as Operatör
    participant UI as Operatör Paneli
    participant API as Backend API
    participant B as Backend Görev Çekirdeği
    participant S as Safety Gate
    participant H as Hardware Adapter
    participant M as MCU/Pan-Tilt/İmha Hattı

    O->>UI: Mod/komut seçer
    UI->>API: ModeRequest / ManualAimCommand / FireIntent
    API->>B: komut niyeti + oturum/dry-run bilgisi
    B->>S: hareket veya atış isteği
    S-->>B: allowed / blocked + gerekçe
    alt allowed
        B->>H: HardwareCommand
        H->>M: seçilen protokolle komut
        M-->>H: durum geri bildirimi
        H-->>B: CommandResult
        B-->>API: görev durumu + command_result
        API-->>UI: canlı durum güncellemesi
    else blocked
        B-->>API: SafetyState + blok nedeni
        API-->>UI: kilit nedeni
    end
```

## Şekil 10 - perception_backend_safety_sekans

```mermaid
sequenceDiagram
    participant C as Kamera
    participant R as Radar/LiDAR Adapter
    participant P as Perception
    participant B as Backend
    participant E as Engagement Manager
    participant S as Safety Gate
    participant L as Telemetry Logger

    C->>P: frame + timestamp
    R->>B: SensorFrame(range/bearing/health)
    P->>P: aday çıkar + takip güncelle
    P->>B: TrackState
    B->>B: sensör/iz füzyonu
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
    participant UI as Operatör Paneli
    participant L as Telemetry Logger

    Btn->>S: E-stop aktif
    S->>H: stop_motion + fire_disable
    H->>M: komutları kes / çıkışları güvenli moda al
    M-->>H: güvenli durum bildirimi
    H-->>S: stop confirmed
    S->>UI: BLOCKED_ESTOP göster
    S->>L: E-stop olayı kaydet
```

## KTR arayüz notu

Bu diyagramlar KTR’de aşağıdaki arayüz tablolarıyla birlikte kullanılmalıdır:

- kullanıcı arayüzleri: simülatör, gerçek operatör paneli, bakım/debug paneli,
- yazılımsal mesaj arayüzleri: `ModeRequest`, `FireIntent`, `SafetyState`, `TrackState`, `HardwareCommand`, `CommandResult`,
- sensör/veri arayüzleri: kamera, radar/LiDAR adapter, perception stream,
- elektronik arayüzler: güç, Acil Durdur, MCU haberleşmesi, imha hattı interlock.

Kesin gerilim, kablo, MCU protokolü veya radar/LiDAR mesaj formatı seçilmeden bu değerler resmiymiş gibi yazılmamalıdır.
