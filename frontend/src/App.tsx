import { useEffect, useMemo, useRef, useState } from 'react';
import { COMPETITION_COURSE } from './competitionCourse';
import { generateTracks } from './missionMock';
import { clampPan, clampTilt, mechanicsConfig, signedDegrees } from './mechanicsConfig';
import { EVENT_FILTERS, TARGET_ORDER, VIDEO_EVIDENCE_STEPS, maxRoundFor, rangeRuleFor, stageConfigFor, thresholdFor } from './missionConfig';
import { generateRealWorldTelemetry, generateRealWorldTracks, generateSensorFusionFrame, realWorldSimulationConfig, type RealWorldTelemetry, type SensorFusionFrame } from './realWorldSimulation';
import { blockCopy, evaluateSafety, evaluateSystemHealth } from './safetyGate';
import { exportJsonl, makeEvent } from './telemetry';
import type { BlockReason, CommandIntent, EventType, Mode, SafetyState, Stage, TelemetryEvent, Track } from './types';

const blockReasons: Exclude<BlockReason, 'ALLOWED'>[] = [
  'BLOCKED_ESTOP',
  'BLOCKED_MOTION_ZONE',
  'BLOCKED_FIRE_ZONE',
  'BLOCKED_TARGET_GATE',
  'BLOCKED_MODE',
  'BLOCKED_CONNECTION',
];

const bootChecks = ['Kamera', 'Pan/Tilt', 'Safety Gate', 'Telemetri', 'Backend'];

function modeLabel(mode: Mode) {
  return {
    safe: 'Safe/Idle',
    manual: 'Manuel',
    autonomous: 'Otonom Takip',
    engagement: 'Angajman Adayı',
    blocked: 'Kilitli',
    maintenance: 'Bakım',
  }[mode];
}

function statusClass(ok: boolean) {
  return ok ? 'ok' : 'bad';
}

function IconButton({ label, icon, active, danger, disabled, onClick, title }: {
  label: string;
  icon: string;
  active?: boolean;
  danger?: boolean;
  disabled?: boolean;
  title?: string;
  onClick: () => void;
}) {
  return (
    <button
      className={`control-btn ${active ? 'active' : ''} ${danger ? 'danger' : ''}`}
      disabled={disabled}
      onClick={onClick}
      title={title ?? label}
    >
      <span>{icon}</span>
      <b>{label}</b>
    </button>
  );
}

function Landing({ onEnter }: { onEnter: () => void }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setProgress((value) => Math.min(100, value + 4)), 110);
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape' || event.key === 'Enter') onEnter();
    };
    window.addEventListener('keydown', key);
    return () => {
      window.clearInterval(id);
      window.removeEventListener('keydown', key);
    };
  }, [onEnter]);

  return (
    <main className="landing">
      <div className="landing-grid" />
      <svg className="dome-scene" viewBox="0 0 1200 760" role="img" aria-label="Çelikkubbe animasyonu">
        <defs>
          <radialGradient id="domeGlow" cx="50%" cy="70%" r="65%">
            <stop offset="0%" stopColor="#00e5ff" stopOpacity="0.28" />
            <stop offset="65%" stopColor="#00e5ff" stopOpacity="0.08" />
            <stop offset="100%" stopColor="#00e5ff" stopOpacity="0" />
          </radialGradient>
          <filter id="soft"><feGaussianBlur stdDeviation="3" /></filter>
        </defs>
        <rect width="1200" height="760" fill="#020304" />
        <ellipse cx="600" cy="620" rx="390" ry="90" fill="#071016" stroke="#183646" />
        <path className="dome-fill" d="M190 622 A410 410 0 0 1 1010 622" fill="url(#domeGlow)" />
        <path className="dome-arc arc-main" d="M190 622 A410 410 0 0 1 1010 622" />
        <path className="dome-arc arc-mid" d="M278 622 A322 322 0 0 1 922 622" />
        <path className="dome-arc arc-low" d="M374 622 A226 226 0 0 1 826 622" />
        <g className="radar">
          <circle cx="600" cy="620" r="92" />
          <circle cx="600" cy="620" r="180" />
          <circle cx="600" cy="620" r="268" />
          <circle cx="600" cy="620" r="356" />
          <path d="M600 620 L930 462" className="radar-sweep" />
        </g>
        {[0, 1, 2, 3, 4].map((i) => (
          <g key={i} className={`incoming incoming-${i}`}>
            <path d="M0 0 l34 8 l-34 8 l8 -8 z" />
            <line x1="-74" y1="8" x2="-16" y2="8" />
          </g>
        ))}
        {[0, 1, 2].map((i) => (
          <path key={i} className={`interceptor trail-${i}`} d={`M${480 + i * 80} 620 C${500 + i * 50} ${520 - i * 26}, ${560 + i * 64} ${420 - i * 18}, ${650 + i * 72} ${338 - i * 52}`} />
        ))}
        <g className="protected-zone">
          <rect x="470" y="600" width="260" height="32" rx="4" />
          <path d="M508 600 v-42 h34 v42 M584 600 v-64 h34 v64 M660 600 v-50 h34 v50" />
        </g>
      </svg>
      <section className="boot-card">
        <div className="signal">GÖKKALKAN</div>
        <div className="boot-sub">Çelikkubbe operatör konsolu · MOCK</div>
        <div className="boot-checks">
          {bootChecks.map((check, index) => {
            const done = progress > index * 18;
            return <span key={check} className={done ? 'done' : ''}><i />{check}</span>;
          })}
        </div>
        <div className="boot-progress"><span style={{ width: `${progress}%` }} /></div>
        <button className="enter-console" onClick={onEnter}>Konsola Geç</button>
        <small>Enter/Esc ile atla</small>
      </section>
    </main>
  );
}

function CourseOverlay({ stage }: { stage: Stage }) {
  const points = (items: Array<{ x: number; y: number }>) => items.map((point) => `${point.x},${point.y}`).join(' ');
  return (
    <svg className="course-svg" data-testid="competition-course" viewBox="0 0 100 100" aria-hidden="true">
      <defs>
        <filter id="courseGlow"><feGaussianBlur stdDeviation="0.6" /></filter>
      </defs>
      <rect className="course-frame" x="6" y="16" width="78" height="76" rx="1.5" />
      <line className="range-ruler" x1="8" y1="20" x2="80" y2="20" />
      {COMPETITION_COURSE.rangeMarkers.map((marker) => (
        <g key={marker.range} className="range-marker" data-testid={`range-${marker.range}m`}>
          <line x1={marker.x} y1="16" x2={marker.x} y2="24" />
          <text x={marker.x - 4} y="15">{marker.range} metre</text>
        </g>
      ))}
      <text className="course-point" data-testid="course-point-a" x={COMPETITION_COURSE.aPoint.x - 1} y={COMPETITION_COURSE.aPoint.y - 2}>A</text>
      <text className="course-point" data-testid="course-point-b" x={COMPETITION_COURSE.bPoint.x - 1} y={COMPETITION_COURSE.bPoint.y - 2}>B</text>
      {[44, 58, 72].map((radius, index) => (
        <g key={radius} className={`range-ring ring-${index + 1}`}>
          <circle cx={COMPETITION_COURSE.systemPosition.x} cy={COMPETITION_COURSE.systemPosition.y} r={radius / 2.4} />
          <text x={COMPETITION_COURSE.systemPosition.x - radius / 2.4 + 1} y={COMPETITION_COURSE.systemPosition.y - 1}>{[5, 10, 15][index]} m</text>
        </g>
      ))}
      {COMPETITION_COURSE.lanes.map((lane) => (
        <g key={lane.lane} className={`course-lane course-lane-${lane.lane}`}>
          <polyline points={points(lane.points)} />
          <text x="9" y={lane.points[0].y - 2}>{lane.label.toUpperCase()}</text>
        </g>
      ))}
      <g className="system-node">
        <circle cx={COMPETITION_COURSE.systemPosition.x} cy={COMPETITION_COURSE.systemPosition.y} r="2.5" />
        <text x={COMPETITION_COURSE.systemPosition.x - 7} y={COMPETITION_COURSE.systemPosition.y + 7}>Gökkalkan</text>
      </g>
      {stage === 3 && <text className="foe-legend" x="9" y="96">Kırmızı ok: Düşman · Mavi ok: Dost</text>}
    </svg>
  );
}

function SensorReadout({ sensorFrame, realWorldSim }: { sensorFrame: SensorFusionFrame; realWorldSim: boolean }) {
  const lidar = sensorFrame.lidarReturns[0];
  const radar = sensorFrame.radarReturns[0];
  const cameraCount = sensorFrame.cameraDetections.length;
  return (
    <div className="sensor-readout" data-testid="sensor-fusion-panel">
      <b>Sensör Füzyonu</b>
      <span>Kamera <strong>{cameraCount} bbox</strong></span>
      <span>LiDAR MOCK <strong>{lidar ? `${lidar.rangeM.toFixed(1)} m` : 'bekle'}</strong></span>
      <span>Radar MOCK <strong>{radar ? `${radar.radialVelocityMps.toFixed(1)} m/s` : 'A1 yok'}</strong></span>
      <span>Füzyon <strong>{sensorFrame.fusedTargetId ?? '—'}</strong></span>
      <small>{realWorldSim ? 'Şartname-temsili saha akışı' : 'hardware_mock'} · radar/LiDAR modeli şartnamede tanımlı değil</small>
    </div>
  );
}

function CameraViewport({
  tracks,
  stage,
  selectedId,
  onSelect,
  panAngle = 0,
  tiltAngle = 0,
  feedLabel,
  sensorFrame,
  strikes,
  realWorldSim,
}: {
  tracks: Track[];
  stage: Stage;
  selectedId?: string;
  onSelect: (id: string) => void;
  panAngle?: number;
  tiltAngle?: number;
  feedLabel: string;
  sensorFrame: SensorFusionFrame;
  strikes: StrikeEffect[];
  realWorldSim: boolean;
}) {
  return (
    <section className="viewport">
      <div className="sensor-lines" />
      <CourseOverlay stage={stage} />
      <div className="lane-grid">
        <span>KOL 1</span><span>KOL 2</span><span>KOL 3</span>
      </div>
      <div className="reticle"><i /><b /></div>
      <svg className="strike-layer" viewBox="0 0 100 100" aria-live="polite">
        {strikes.map((strike) => (
          <g key={strike.id} className={`strike-effect ${strike.result === 'yanlış sıra' ? 'miss' : 'hit'}`} data-testid="mock-strike">
            <line x1={COMPETITION_COURSE.systemPosition.x} y1={COMPETITION_COURSE.systemPosition.y} x2={strike.x} y2={strike.y} />
            <circle cx={strike.x} cy={strike.y} r="3.2" />
            <text x={Math.min(88, strike.x + 2)} y={Math.max(8, strike.y - 2)}>{strike.label}</text>
          </g>
        ))}
      </svg>
      <SensorReadout sensorFrame={sensorFrame} realWorldSim={realWorldSim} />
      <div className="angle-readout left">PAN {panAngle >= 0 ? '+' : ''}{panAngle.toFixed(1)}°</div>
      <div className="angle-readout right">TILT {tiltAngle >= 0 ? '+' : ''}{tiltAngle.toFixed(1)}°</div>
      <div className="stage-watermark">AŞAMA {stage}</div>
      {tracks.map((track) => (
        <button
          key={track.id}
          data-testid={`track-${track.id}`}
          aria-label={`${track.id} ${track.type} ${track.friendFoe} ${track.range.toFixed(1)} metre`}
          className={`track-box ${track.friendFoe === 'Dost' ? 'friend' : ''} ${track.friendFoe === 'Düşman' ? 'enemy' : ''} ${track.candidate ? 'candidate' : ''} ${selectedId === track.id ? 'selected' : ''}`}
          style={{ left: `${track.x}%`, top: `${track.y}%`, width: `${track.w}%`, height: `${track.h}%` }}
          onClick={() => onSelect(track.id)}
          title={`${track.id} ${track.type}`}
        >
          <span className="track-id">{track.id}</span>
          <span className="track-meta">{track.type}</span>
          <span className="track-meta">{track.friendFoe} · {(track.confidence * 100).toFixed(0)}%</span>
          <span className="track-meta">{track.range.toFixed(1)} m · {track.rangeGate}</span>
        </button>
      ))}
      <div className="mock-feed">{feedLabel}</div>
      <div className="assumption-pill" title={sensorFrame.assumptionNotice}>Şartname-temsili parkur</div>
    </section>
  );
}

function SafetyStrip({
  systemHealth,
  commandSafety,
  scenario,
  mode,
  onToggleEstop,
  onScenario,
}: {
  systemHealth: SafetyState;
  commandSafety: SafetyState;
  scenario: BlockReason;
  mode: Mode;
  onToggleEstop: () => void;
  onScenario: (reason: BlockReason) => void;
}) {
  const chips = [
    ['Acil Durdur', !commandSafety.estop],
    ['Harekete Yasak Alan', commandSafety.motionZoneOk],
    ['Atışa Yasak Alan', commandSafety.fireZoneOk],
    ['Menzil Kapısı', commandSafety.targetGateOk],
    ['Mod Uyumu', commandSafety.modeOk],
    ['Donanım Bağlantısı', commandSafety.connectionOk],
  ] as const;
  const systemOk = systemHealth.blockReason === 'ALLOWED';
  const commandOk = commandSafety.blockReason === 'ALLOWED';
  const commandWarnOnly = commandSafety.blockReason === 'BLOCKED_MODE' && (mode === 'safe' || mode === 'maintenance');
  const commandText = commandOk
    ? 'Kapı açık'
    : commandWarnOnly
      ? `${modeLabel(mode)} · beklemede`
      : `${commandSafety.blockReason} · ${blockCopy[commandSafety.blockReason]}`;

  return (
    <section className="safety-strip">
      <button className={`estop ${commandSafety.estop ? 'engaged' : ''}`} onClick={onToggleEstop}>Acil Durdur <small>sim</small></button>
      <div className="safety-chips">
        {chips.map(([label, ok]) => <span key={label} className={statusClass(ok)}><i />{label}</span>)}
      </div>
      <div className={`block-reason ${systemOk ? 'clear' : 'locked'}`}>SİSTEM · {systemOk ? 'Hazır' : blockCopy[systemHealth.blockReason]}</div>
      <div className={`block-reason ${commandOk ? 'clear' : commandWarnOnly ? 'warn' : 'locked'}`}>
        KOMUT · {commandText}
      </div>
      <select onChange={(event) => onScenario(event.target.value as BlockReason)} value={scenario} aria-label="Mock blok senaryosu">
        <option value="ALLOWED">Mock blok senaryosu</option>
        {blockReasons.map((reason) => <option key={reason} value={reason}>{reason}</option>)}
      </select>
    </section>
  );
}

type ArmState = 'idle' | 'holding' | 'armed';

interface StrikeEffect {
  id: number;
  trackId: string;
  x: number;
  y: number;
  stage: Stage;
  result: 'isabet' | 'yanlış sıra';
  label: string;
  createdAt: number;
}

function ManualPanel({
  currentTarget,
  selectedTrack,
  score,
  timeLeft,
  fireGateAllowed,
  fireAllowed,
  armState,
  onArmStart,
  onArmClick,
  onMove,
  onFire,
  onWrong,
}: {
  currentTarget: number;
  selectedTrack?: Track;
  score: number;
  timeLeft: number;
  fireGateAllowed: boolean;
  fireAllowed: boolean;
  armState: ArmState;
  onArmStart: () => void;
  onArmClick: () => void;
  onMove: (cmd: string) => void;
  onFire: () => void;
  onWrong: () => void;
}) {
  const expectedTarget = TARGET_ORDER[Math.min(currentTarget, TARGET_ORDER.length - 1)];
  const wrongSelection = Boolean(selectedTrack && selectedTrack.type !== expectedTarget);
  const armCopy = {
    idle: 'Kurulu değil',
    holding: 'Kuruluyor',
    armed: 'Atış hattı kuruldu',
  }[armState];
  const stageConfig = stageConfigFor(1);

  return (
    <section className="work-panel manual-panel">
      <div className="panel-title"><b>Aşama 1</b><span>{stageConfig.summary}</span></div>
      <div className={`expected-target ${wrongSelection ? 'warn' : ''}`}>
        <span>Beklenen hedef</span>
        <b>{expectedTarget}</b>
        <small>{wrongSelection ? `${selectedTrack?.type} seçili · -5 ceza riski` : 'Sıra doğru veya hedef seçilmedi'}</small>
      </div>
      <div className="target-order">
        {TARGET_ORDER.map((target, index) => <span key={target} className={index === currentTarget ? 'now' : index < currentTarget ? 'done' : ''}>{index + 1}. {target}</span>)}
      </div>
      <div className="manual-controls">
        <div className="dpad" aria-label="Manuel pan tilt">
          <button onClick={() => onMove('tilt+')}>▲</button>
          <button onClick={() => onMove('pan-')}>◀</button>
          <button className="center" onClick={() => onMove('hold')}>●</button>
          <button onClick={() => onMove('pan+')}>▶</button>
          <button onClick={() => onMove('tilt-')}>▼</button>
        </div>
        <div className="fine-controls">
          <button onClick={() => onMove('fine-')}>{signedDegrees(-mechanicsConfig.fineStepDeg)}</button>
          <button onClick={() => onMove('fine+')}>{signedDegrees(mechanicsConfig.fineStepDeg)}</button>
          <button onClick={() => onMove('Merkez')}>Merkez</button>
          <button onClick={() => onMove('Yavaş')}>Yavaş</button>
        </div>
      </div>
      <div className="mission-metrics"><span>Süre <b>{timeLeft}s</b></span><span>Puan <b>{score}</b></span><span>Hedef <b>{Math.min(currentTarget + 1, 4)}/4</b></span></div>
      <div className={`arm-status ${armState}`}>Atış hattı: <b>{armCopy}</b><small>{fireGateAllowed ? `${mechanicsConfig.armHoldMs} ms basılı tut veya tıkla` : 'Güvenlik/mod kapısı kilitli'}</small></div>
      <div className="fire-row">
        <button
          className={`arm ${armState}`}
          disabled={!fireGateAllowed}
          onPointerDown={onArmStart}
          onClick={onArmClick}
          title="Tıklayarak veya basılı tutarak simülasyon atış hattını kur"
        >
          Basılı Kur
        </button>
        <button className="fire" disabled={!fireAllowed} onClick={onFire}>ATEŞ</button>
        <button className="warn" onClick={onWrong}>Yanlış sıra</button>
      </div>
    </section>
  );
}

function RehearsalStrip({
  stage,
  mode,
  worldTelemetry,
}: {
  stage: Stage;
  mode: Mode;
  worldTelemetry: RealWorldTelemetry;
}) {
  const nextStep = stage === 1
    ? mode === 'manual'
      ? 'Hedef sırasını izle, pan/tilt ile hizala, atış hattını kur ve kullanıcı komutuyla ateşle.'
      : 'Aşama 1 için Manuel Mod’a geç.'
    : stage === 2
      ? mode === 'autonomous'
        ? 'Üç koldaki hedefleri parkurdan çıkmadan otonom takip/angajmanla imha et.'
        : 'Aşama 2 için Otonom Mod’u başlat.'
      : mode === 'autonomous'
        ? 'Dost hedefleri kilitle, yalnızca uygun menzildeki düşman adaya angaje ol.'
        : 'Aşama 3 için Otonom Mod’u başlat ve düşman adayı seç.';

  return (
    <section className="rehearsal-strip">
      <b>Yarışma Provası</b>
      <span>{nextStep}</span>
      <small>{worldTelemetry.fps} FPS · {worldTelemetry.latencyMs} ms · {worldTelemetry.windMps} m/s rüzgâr · {worldTelemetry.batteryV} V</small>
    </section>
  );
}

function AutonomousPanel({
  stage,
  tracks,
  round,
  hits,
  roundHits,
  noHitStreak,
  score,
  missionStatus,
  running,
  engageAllowed,
  onToggle,
  onEngage,
  onNextRound,
}: {
  stage: 2 | 3;
  tracks: Track[];
  round: number;
  hits: number;
  roundHits: number;
  noHitStreak: number;
  score: number;
  missionStatus: string;
  running: boolean;
  engageAllowed: boolean;
  onToggle: () => void;
  onEngage: () => void;
  onNextRound: () => void;
}) {
  const stageConfig = stageConfigFor(stage);
  const trace = stage === 2
    ? ['Tespit', 'Takip', 'Öncelik', 'Güvenlik Kapısı', 'Angajman/Blok']
    : ['Sınıflandır', 'Dost Kilidi', 'Menzil Kapısı', 'Güvenlik Kapısı', 'Angajman/Blok'];
  return (
    <section className="work-panel auto-panel">
      <div className="panel-title"><b>Aşama {stage}</b><span>{stageConfig.summary}</span></div>
      {stage === 2 && <div className="stage-note">Şartname notu: Bu aşamada hedef tipi sınıflandırması beklenmez.</div>}
      <div className="rounds">
        <span>Tur <b>{round}/{maxRoundFor(stage)}</b></span>
        <span>İsabet <b>{hits}</b></span>
        <span className={noHitStreak >= 2 ? 'danger-text' : ''}>Boş seri <b>{noHitStreak}</b></span>
      </div>
      <div className="rounds">
        <span>Puan <b>{score}</b></span>
        <span>Tur içi <b>{roundHits}/3</b></span>
        <span>Durum <b>{missionStatus}</b></span>
      </div>
      <button className={`auto-toggle ${running ? 'running' : ''}`} onClick={onToggle}>{running ? 'Otonom Durdur' : 'Otonom Başlat'}</button>
      <div className="lane-bars">
        {[1, 2, 3].map((lane) => {
          const track = tracks.find((item) => item.lane === lane);
          return <span key={lane}><i style={{ width: `${track ? Math.min(100, track.confidence * 100) : 0}%` }} />Kol {lane}</span>;
        })}
      </div>
      <div className="track-list">
        {tracks.map((track) => <button key={track.id} className={track.candidate ? 'hot' : ''}>{track.id}<b>{track.friendFoe}</b><small>{track.velocity.toFixed(1)} m/s · {track.direction}</small></button>)}
      </div>
      <div className="auto-actions">
        <button className="fire" disabled={!running || !engageAllowed} onClick={onEngage}>ANGAJMAN</button>
        <button className="warn" onClick={onNextRound}>Turu Bitir</button>
      </div>
      <small className="sim-note">`Turu Bitir` yalnızca mock/senaryo provası içindir.</small>
      <div className="decision-trace">{trace.map((step, index) => <span key={step} className={index < 4 || running ? 'lit' : ''}>{step}</span>)}</div>
    </section>
  );
}

function Stage3Intel({ selectedTrack }: { selectedTrack?: Track }) {
  const target = selectedTrack;
  const rule = target ? rangeRuleFor(target.type) : undefined;
  const lockMessage = !target
    ? 'İz yok'
    : target.friendFoe === 'Dost'
      ? 'DOST HEDEF — ATEŞ KİLİTLİ'
      : target.friendFoe === 'Bilinmeyen'
        ? 'Bilinmeyen hedef — sınıflandırma bekleniyor'
        : target.rangeGate === 'Uygun'
          ? 'Düşman hedef — menzil uygun'
          : 'Düşman hedef — menzil kapısı kapalı';
  return (
    <section className="work-panel intel-panel">
      <div className="panel-title"><b>Dost/Düşman</b><span>{rule ? `Geçerli menzil ${rule.label}` : 'Menzil kapısı'}</span></div>
      <div className={`foe-card ${target?.friendFoe === 'Düşman' ? 'enemy' : target?.friendFoe === 'Dost' ? 'friend' : 'unknown'}`}>
        <span>{target?.friendFoe ?? 'İz yok'}</span>
        <b>{target?.type ?? '—'}</b>
      </div>
      <div className="range-gauge"><span style={{ width: `${target ? Math.min(100, (target.range / 20) * 100) : 0}%` }} /><b>{target ? target.range.toFixed(1) : '—'} m</b></div>
      <div className={`gate-pill ${target?.rangeGate === 'Uygun' ? 'ok' : target?.rangeGate === 'Erken' ? 'warn' : 'bad'}`}>{target?.rangeGate ?? 'Bekle'}</div>
      <div className={`lock-message ${target?.friendFoe === 'Dost' || target?.rangeGate !== 'Uygun' ? 'locked' : 'clear'}`}>{lockMessage}</div>
      <div className="penalties"><span>Dost ateş kilidi</span><b>{target?.friendFoe === 'Dost' ? 'Kilitli' : 'Açık'}</b><span>Ceza</span><b>-10 max/tur</b></div>
    </section>
  );
}

function VideoEvidencePanel({ events }: { events: TelemetryEvent[] }) {
  return (
    <section className="thin-panel video-panel">
      <div className="panel-title"><b>Görev Kabiliyeti Kanıtı</b><span>720p+ · 2-5 dk · tek YouTube</span></div>
      {VIDEO_EVIDENCE_STEPS.map((item) => {
        const marker = events.find(item.match);
        return <label key={item.id} title={item.description}><input type="checkbox" readOnly checked={Boolean(marker)} />{item.id}<span>{item.label}</span><time>{marker?.timestamp ?? '--:--'}</time></label>;
      })}
    </section>
  );
}

function MaintenancePanel({ paused, prepLeft, budgetLeft, onToggle }: { paused: boolean; prepLeft: number; budgetLeft: number; onToggle: () => void }) {
  return (
    <section className="thin-panel maintenance-panel">
      <div className="panel-title"><b>Bakım/Zaman</b><span>{paused ? 'Duraklatıldı' : 'Hazır'}</span></div>
      <div className="budget"><span>Hazırlık</span><b>{Math.ceil(prepLeft / 60)} dk</b></div>
      <div className="budget"><span>Bakım bütçesi</span><b>{Math.floor(budgetLeft / 60)}:{String(budgetLeft % 60).padStart(2, '0')}</b></div>
      <button className={paused ? 'resume' : 'pause'} onClick={onToggle}>{paused ? 'Devam' : 'Bakım Molası'}</button>
      <small>Her talep min. {mechanicsConfig.maintenanceMinimumSeconds} sn düşer</small>
    </section>
  );
}

function SettingsPanel({
  onReset,
  realWorldSim,
  onToggleRealWorldSim,
  worldTelemetry,
}: {
  onReset: () => void;
  realWorldSim: boolean;
  onToggleRealWorldSim: () => void;
  worldTelemetry: RealWorldTelemetry;
}) {
  return (
    <section className="thin-panel settings-panel">
      <div className="panel-title"><b>Ayar/Kalibrasyon</b><span>{realWorldSim ? 'saha sim' : 'mock'}</span></div>
      <div className="setting-grid">
        <span>Kamera</span><b>MockCam-01</b>
        <span>Serial/CAN</span><b className="amber">{mechanicsConfig.mockConnectionOk ? 'Sim bağlı' : 'Sim kopuk'}</b>
        <span>Pan/Tilt</span><b>{signedDegrees(mechanicsConfig.panMinDeg)}..{signedDegrees(mechanicsConfig.panMaxDeg)} / {signedDegrees(mechanicsConfig.tiltMinDeg)}..{signedDegrees(mechanicsConfig.tiltMaxDeg)}</b>
        <span>Hareket yasak</span><b>{mechanicsConfig.motionForbiddenLabel}</b>
        <span>Atış yasak</span><b>{mechanicsConfig.fireForbiddenLabel}</b>
        <span>Menzil</span><b>F16 10-15 · Hel/Bal 5-15 · Mini 0-15</b>
        <span>Sensör mock</span><b>Kamera {realWorldSimulationConfig.cameraFovDeg}° · LiDAR σ{realWorldSimulationConfig.lidarRangeStdM}m · Radar σ{realWorldSimulationConfig.radarRangeStdM}m</b>
        <span>Eşikler</span><b>env + şartname</b>
      </div>
      <div className={`rehearsal-card ${realWorldSim ? 'active' : ''}`}>
        <button onClick={onToggleRealWorldSim}>{realWorldSim ? 'Gerçek Yarışma Simülasyonu Açık' : 'Tam Yarışma Simülasyonu'}</button>
        <small>Canlı kamera gibi jitter, gecikme, rüzgâr ve batarya düşümü üretir.</small>
      </div>
      <div className="world-grid">
        <span>Kaynak</span><b>{worldTelemetry.source}</b>
        <span>Frame</span><b>#{worldTelemetry.frameId}</b>
        <span>FPS/gecikme</span><b>{worldTelemetry.fps} / {worldTelemetry.latencyMs} ms</b>
        <span>Gürültü</span><b>{worldTelemetry.sensorNoisePx} px</b>
        <span>LiDAR/Radar</span><b>{worldTelemetry.lidarReturns} dönüş · {worldTelemetry.radarTracks} iz</b>
        <span>Füzyon</span><b>{worldTelemetry.fusionLocks} kilit</b>
        <span>Rüzgâr/batarya</span><b>{worldTelemetry.windMps} m/s · {worldTelemetry.batteryV} V</b>
      </div>
      <button className="reset" onClick={onReset}>Simülasyonu Sıfırla</button>
    </section>
  );
}

function TelemetryPanel({ events, filter, onFilter, onExport }: { events: TelemetryEvent[]; filter: EventType | 'all'; onFilter: (filter: EventType | 'all') => void; onExport: () => void }) {
  const visible = events.filter((event) => filter === 'all' || event.type === filter).slice(0, 12);
  return (
    <section className="log-panel">
      <div className="panel-title"><b>Telemetri</b><span>JSONL mock</span></div>
      <div className="log-filters">
        <button className={filter === 'all' ? 'active' : ''} onClick={() => onFilter('all')}>tümü</button>
        {EVENT_FILTERS.map((item) => <button key={item} className={filter === item ? 'active' : ''} onClick={() => onFilter(item)}>{item}</button>)}
        <button onClick={onExport}>dışa aktar</button>
      </div>
      <div className="event-stream">
        {visible.map((event) => (
          <div key={event.id} className={`event ${event.type}`}>
            <time>{event.timestamp}</time><b>A{event.stage}</b><span>{event.type}</span><strong>{event.decision}</strong><small>{event.reason}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function CommandQueue({
  moveSafety,
  fireSafety,
  fireReady,
  fireLabel,
  fireDetail,
}: {
  moveSafety: SafetyState;
  fireSafety: SafetyState;
  fireReady: boolean;
  fireLabel: string;
  fireDetail: string;
}) {
  const moveBlocked = moveSafety.blockReason !== 'ALLOWED';
  const fireBlocked = !fireReady;
  return (
    <section className="queue-panel">
      <div className="panel-title"><b>Komut Kuyruğu</b><span>hardware_mock</span></div>
      <div className={`queue-item ${moveBlocked ? 'blocked' : 'ready'}`}><span>pan/tilt</span><b>{moveBlocked ? 'blocked' : 'queued'}</b></div>
      <div className={`queue-item ${fireBlocked ? 'blocked' : 'ready'}`}><span>fire_enable</span><b>{fireBlocked ? 'blocked' : 'armed gate'}</b></div>
      <small>{fireLabel || (fireBlocked ? fireSafety.blockReason : 'ALLOWED')} · {fireBlocked ? fireDetail : 'angajman kapısı açık'}</small>
      <small>Gerçek motor/ateş komutu gönderilmez.</small>
    </section>
  );
}

function scoreForTrack(track: Track) {
  if (track.range <= 7.5) return 5;
  if (track.range <= 12.5) return 10;
  return 20;
}

function stage2RoundScore(roundHits: number) {
  if (roundHits >= 3) return 30;
  if (roundHits === 2) return 15;
  if (roundHits === 1) return 5;
  return -5;
}

function stage3TargetScore(track: Track) {
  if (track.type === 'F16') return 30;
  if (track.type === 'Mini/Micro İHA') return 10;
  return 20;
}

function Console() {
  const [stage, setStage] = useState<Stage>(1);
  const [mode, setMode] = useState<Mode>('safe');
  const [elapsed, setElapsed] = useState(0);
  const [selectedId, setSelectedId] = useState<string>();
  const [currentTarget, setCurrentTarget] = useState(0);
  const [score, setScore] = useState(0);
  const [round, setRound] = useState(1);
  const [hits, setHits] = useState(0);
  const [roundHits, setRoundHits] = useState(0);
  const [enemyHitThisRound, setEnemyHitThisRound] = useState(false);
  const [noHitStreak, setNoHitStreak] = useState(0);
  const [missionStatus, setMissionStatus] = useState('Hazır');
  const [autoRunning, setAutoRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [maintenanceBudget, setMaintenanceBudget] = useState(mechanicsConfig.maintenanceBudgetSeconds);
  const [panAngle, setPanAngle] = useState(0);
  const [tiltAngle, setTiltAngle] = useState(0);
  const [manualArmState, setManualArmState] = useState<ArmState>('idle');
  const [realWorldSim, setRealWorldSim] = useState(realWorldSimulationConfig.enabledByDefault);
  const [strikes, setStrikes] = useState<StrikeEffect[]>([]);
  const [filter, setFilter] = useState<EventType | 'all'>('all');
  const [scenario, setScenarioState] = useState<BlockReason>('ALLOWED');
  const [baseSafety, setBaseSafety] = useState<Omit<SafetyState, 'blockReason'>>({
    estop: false,
    motionZoneOk: true,
    fireZoneOk: true,
    targetGateOk: true,
    modeOk: true,
    connectionOk: mechanicsConfig.mockConnectionOk,
  });
  const eventId = useRef(1);
  const strikeId = useRef(1);
  const armHoldTimer = useRef<number | undefined>(undefined);
  const armExpireTimer = useRef<number | undefined>(undefined);
  const armPointerStarted = useRef(false);
  const [events, setEvents] = useState<TelemetryEvent[]>([
    makeEvent(0, 1, 'safe', 'telemetry', 'BOOT_OK', 'Mock arayüz başlatıldı'),
  ]);

  const stageConfig = stageConfigFor(stage);
  const timeLeft = Math.max(0, (stageConfig.durationSeconds ?? 300) - Math.floor(elapsed));
  const prepLeft = Math.max(0, mechanicsConfig.prepSeconds - Math.floor(elapsed * 6));
  const tracks = useMemo(() => realWorldSim ? generateRealWorldTracks(stage, elapsed) : generateTracks(stage, elapsed), [stage, elapsed, realWorldSim]);
  const worldTelemetry = useMemo(() => generateRealWorldTelemetry(stage, elapsed, realWorldSim, tracks.length), [stage, elapsed, realWorldSim, tracks.length]);
  const sensorFrame = useMemo(() => generateSensorFusionFrame(stage, elapsed, tracks), [stage, elapsed, tracks]);
  const selectedTrack = tracks.find((track) => track.id === selectedId) ?? tracks.find((track) => track.candidate) ?? tracks[0];
  const moveIntent: CommandIntent = mode === 'autonomous' ? 'autonomous_move' : 'move';
  const fireIntent: CommandIntent = mode === 'autonomous' ? 'autonomous_engage' : 'fire';
  const systemHealth = evaluateSystemHealth(baseSafety);
  const moveSafety = evaluateSafety({ stage, mode, base: baseSafety, selectedTrack, command: moveIntent });
  const fireSafety = evaluateSafety({ stage, mode, base: baseSafety, selectedTrack, command: fireIntent });
  const manualFireGateAllowed = stage === 1 && timeLeft > 0 && mode === 'manual' && fireSafety.blockReason === 'ALLOWED';
  const autonomousFireGateAllowed = stage !== 1 && (mode === 'autonomous' || mode === 'engagement') && autoRunning && fireSafety.blockReason === 'ALLOWED';
  const autonomousRoundReady = stage === 2 ? roundHits < 3 : !enemyHitThisRound;
  const fireAllowed = stage === 1 ? manualFireGateAllowed && manualArmState === 'armed' : autonomousFireGateAllowed && autonomousRoundReady;
  const fireQueueSafety: SafetyState = fireAllowed || fireSafety.blockReason !== 'ALLOWED' ? fireSafety : { ...fireSafety, blockReason: 'BLOCKED_MODE' };
  const fireQueueLabel = fireSafety.blockReason !== 'ALLOWED'
    ? fireSafety.blockReason
    : stage === 1 && timeLeft <= 0
      ? 'Aşama 1 süresi doldu'
      : stage === 1 && manualArmState !== 'armed'
      ? 'Atış hattı kurulmadı'
      : stage !== 1 && !autoRunning
        ? 'Otonom çalışma bekleniyor'
        : stage === 2 && roundHits >= 3
          ? 'Tur hedefleri vuruldu'
          : stage === 3 && enemyHitThisRound
            ? 'Tur düşmanı vuruldu'
            : '';
  const fireQueueDetail = fireSafety.blockReason !== 'ALLOWED'
    ? blockCopy[fireSafety.blockReason]
    : stage === 1 && timeLeft <= 0
      ? 'zaman kapısı kapalı'
      : stage === 1 && manualArmState !== 'armed'
      ? 'basılı kurma bekleniyor'
      : stage !== 1 && !autoRunning
        ? 'operatör başlatma bekleniyor'
        : stage === 2 && roundHits >= 3
          ? 'Turu Bitir bekleniyor'
          : stage === 3 && enemyHitThisRound
            ? 'Turu Bitir bekleniyor'
            : 'hazır';
  const effectiveMode: Mode = systemHealth.blockReason !== 'ALLOWED'
    ? 'blocked'
    : mode === 'safe'
      ? 'safe'
      : fireSafety.blockReason === 'ALLOWED' || mode === 'maintenance'
        ? mode
        : 'blocked';
  const activeBlockReason = systemHealth.blockReason !== 'ALLOWED'
    ? systemHealth.blockReason
    : fireSafety.blockReason !== 'ALLOWED' && mode !== 'safe' && mode !== 'maintenance'
      ? fireSafety.blockReason
      : 'ALLOWED';

  const addEvent = (type: EventType, decision: string, reason: string) => {
    const next = makeEvent(eventId.current++, stage, effectiveMode, type, decision, reason);
    setEvents((prev) => [next, ...prev].slice(0, 80));
  };

  const recordStrike = (track: Track | undefined, result: StrikeEffect['result']) => {
    if (!track) return;
    const id = strikeId.current++;
    const effect: StrikeEffect = {
      id,
      trackId: track.id,
      x: track.x,
      y: track.y,
      stage,
      result,
      label: result === 'isabet' ? `STRIKE ${track.id}` : `RİSK ${track.id}`,
      createdAt: Date.now(),
    };
    setStrikes((prev) => [effect, ...prev].slice(0, 5));
    window.setTimeout(() => setStrikes((prev) => prev.filter((item) => item.id !== id)), 2_800);
  };

  useEffect(() => {
    const id = window.setInterval(() => {
      if (!paused) setElapsed((value) => value + 0.5);
    }, 500);
    return () => window.clearInterval(id);
  }, [paused]);

  useEffect(() => {
    if (!selectedId && tracks[0]) setSelectedId(tracks[0].id);
  }, [selectedId, tracks]);

  useEffect(() => {
    if (activeBlockReason !== 'ALLOWED') addEvent('safety', activeBlockReason, blockCopy[activeBlockReason]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBlockReason]);

  useEffect(() => {
    if (stage === 1 && timeLeft === 0 && mode !== 'safe' && missionStatus !== 'Süre doldu') {
      disarmManualFire('Aşama 1 süresi doldu');
      setAutoRunning(false);
      setMode('safe');
      setMissionStatus('Süre doldu');
      addEvent('mode', 'TIME_EXPIRED', 'Aşama 1 süresi doldu; hareket/atış operatör onayına kapatıldı');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stage, timeLeft, mode, missionStatus]);

  const clearArmTimers = () => {
    if (armHoldTimer.current !== undefined) window.clearTimeout(armHoldTimer.current);
    if (armExpireTimer.current !== undefined) window.clearTimeout(armExpireTimer.current);
    armHoldTimer.current = undefined;
    armExpireTimer.current = undefined;
  };

  useEffect(() => () => clearArmTimers(), []);

  const disarmManualFire = (reason: string, log = false) => {
    clearArmTimers();
    setManualArmState('idle');
    if (log) addEvent('command', 'ARM_RESET', reason);
  };

  const startManualArm = (forceRestart = false) => {
    if (manualArmState === 'armed' || (manualArmState === 'holding' && !forceRestart)) return;
    if (!manualFireGateAllowed) {
      addEvent('fire', 'ARM_BLOCK', fireSafety.blockReason === 'ALLOWED' ? 'Manuel Mod/Aşama 1 bekleniyor' : blockCopy[fireSafety.blockReason]);
      return;
    }
    clearArmTimers();
    setManualArmState('holding');
    addEvent('command', 'ARM_HOLD_START', `${mechanicsConfig.armHoldMs} ms basılı kurma başladı`);
    armHoldTimer.current = window.setTimeout(() => {
      setManualArmState('armed');
      addEvent('command', 'ARM_READY', `Atış hattı ${mechanicsConfig.armTimeoutMs} ms için kuruldu`);
      armExpireTimer.current = window.setTimeout(() => {
        setManualArmState('idle');
        addEvent('command', 'ARM_TIMEOUT', 'Atış hattı zaman aşımıyla düştü');
      }, mechanicsConfig.armTimeoutMs);
    }, mechanicsConfig.armHoldMs);
  };

  const startManualArmFromPointer = () => {
    armPointerStarted.current = true;
    startManualArm();
  };

  const startManualArmFromClick = () => {
    if (armPointerStarted.current) {
      armPointerStarted.current = false;
      return;
    }
    startManualArm(true);
  };

  const switchStage = (nextStage: Stage) => {
    if (nextStage > stage && ((stage === 1 && score < thresholdFor(1)) || (stage === 2 && score < thresholdFor(2)))) {
      addEvent('safety', 'EŞİK_BİLGİ', 'Mock prototipte aşama geçişine izin verildi; eşik durumu panelde izlenir');
    }
    disarmManualFire('Aşama değişimi');
    setStage(nextStage);
    setMode('safe');
    setElapsed(0);
    setSelectedId(undefined);
    setCurrentTarget(0);
    setScore(0);
    setRound(1);
    setHits(0);
    setRoundHits(0);
    setEnemyHitThisRound(false);
    setNoHitStreak(0);
    setMissionStatus('Hazır');
    setAutoRunning(false);
    setStrikes([]);
    setPanAngle(0);
    setTiltAngle(0);
    setScenario('ALLOWED');
    addEvent('mode', `AŞAMA_${nextStage}`, 'Görev senaryosu değişti');
  };

  const switchMode = (nextMode: Mode) => {
    if (nextMode !== 'manual') disarmManualFire('Mod değişimi');
    setMode(nextMode);
    if (nextMode !== 'autonomous') setAutoRunning(false);
    if (nextMode === 'safe' || nextMode === 'maintenance') setMissionStatus(nextMode === 'safe' ? 'Beklemede' : 'Bakım');
    addEvent('mode', modeLabel(nextMode), 'Operatör mod geçişi');
  };

  const setScenario = (reason: BlockReason) => {
    setScenarioState(reason);
    const clear = { estop: false, motionZoneOk: true, fireZoneOk: true, targetGateOk: true, modeOk: true, connectionOk: mechanicsConfig.mockConnectionOk };
    const next = { ...clear };
    if (reason === 'BLOCKED_ESTOP') next.estop = true;
    if (reason === 'BLOCKED_MOTION_ZONE') next.motionZoneOk = false;
    if (reason === 'BLOCKED_FIRE_ZONE') next.fireZoneOk = false;
    if (reason === 'BLOCKED_TARGET_GATE') next.targetGateOk = false;
    if (reason === 'BLOCKED_MODE') next.modeOk = false;
    if (reason === 'BLOCKED_CONNECTION') next.connectionOk = false;
    if (reason !== 'ALLOWED') disarmManualFire('Güvenlik senaryosu değişti');
    setBaseSafety(next);
    addEvent('safety', reason, reason === 'ALLOWED' ? 'Kilit temizlendi' : blockCopy[reason]);
  };

  const toggleEstop = () => {
    const nextEstop = !baseSafety.estop;
    if (nextEstop) {
      disarmManualFire('Acil Durdur', false);
      setAutoRunning(false);
      addEvent('safety', 'ESTOP_ON', 'Acil Durdur: hareket ve atış kesildi');
    } else {
      addEvent('safety', 'ESTOP_OFF', 'Acil Durdur bırakıldı; hakem/operatör onayı beklenir');
    }
    setBaseSafety((prev) => ({ ...prev, estop: nextEstop }));
  };

  const handleMove = (cmd: string) => {
    const moveGate = evaluateSafety({ stage, mode, base: baseSafety, selectedTrack, command: moveIntent });
    if (moveGate.blockReason === 'ALLOWED') {
      const coarse = mechanicsConfig.coarseStepDeg;
      const fine = mechanicsConfig.fineStepDeg;
      if (cmd === 'tilt+') setTiltAngle((v) => clampTilt(v + coarse));
      else if (cmd === 'tilt+fine') setTiltAngle((v) => clampTilt(v + fine));
      else if (cmd === 'pan-') setPanAngle((v) => clampPan(v - coarse));
      else if (cmd === 'pan-fine') setPanAngle((v) => clampPan(v - fine));
      else if (cmd === 'pan+') setPanAngle((v) => clampPan(v + coarse));
      else if (cmd === 'pan+fine') setPanAngle((v) => clampPan(v + fine));
      else if (cmd === 'tilt-') setTiltAngle((v) => clampTilt(v - coarse));
      else if (cmd === 'tilt-fine') setTiltAngle((v) => clampTilt(v - fine));
      else if (cmd === 'fine+') setPanAngle((v) => clampPan(v + fine));
      else if (cmd === 'fine-') setPanAngle((v) => clampPan(v - fine));
      else if (cmd === 'Merkez') { setPanAngle(0); setTiltAngle(0); }
    }
    addEvent('command', moveGate.blockReason === 'ALLOWED' ? `MOVE_${cmd}` : 'MOVE_BLOCK', blockCopy[moveGate.blockReason]);
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (target && ['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(target.tagName)) return;
      if (stage !== 1 || mode !== 'manual') return;
      const suffix = event.shiftKey ? 'fine' : '';
      const commandByKey: Record<string, string> = {
        ArrowUp: suffix ? 'tilt+fine' : 'tilt+',
        ArrowDown: suffix ? 'tilt-fine' : 'tilt-',
        ArrowLeft: suffix ? 'pan-fine' : 'pan-',
        ArrowRight: suffix ? 'pan+fine' : 'pan+',
        a: 'arm',
        A: 'arm',
        k: 'arm',
        K: 'arm',
        ' ': 'hold',
      };
      const command = commandByKey[event.key];
      if (!command) return;
      event.preventDefault();
      if (command === 'arm') {
        startManualArm();
        return;
      }
      handleMove(command);
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  });

  const handleFire = () => {
    if (!fireAllowed) {
      addEvent('fire', 'FIRE_BLOCK', fireSafety.blockReason === 'ALLOWED' ? fireQueueLabel || 'Atış izni hazır değil' : blockCopy[fireSafety.blockReason]);
      return;
    }
    if (stage === 1) {
      const expected = TARGET_ORDER[currentTarget];
      if (!selectedTrack || selectedTrack.type !== expected) {
        setScore((value) => value - 5);
        recordStrike(selectedTrack, 'yanlış sıra');
        addEvent('fire', 'WRONG_ORDER', `${selectedTrack?.type ?? 'İz yok'} seçildi · beklenen ${expected} · -5`);
        disarmManualFire('Yanlış hedef sonrası atış hattı düştü');
        return;
      }
      const hitScore = scoreForTrack(selectedTrack);
      const nextTarget = currentTarget + 1;
      setScore((value) => {
        const base = Math.min(80, value + hitScore);
        const eligibleBonus = nextTarget >= TARGET_ORDER.length && base >= 80;
        return eligibleBonus ? Math.min(100, base + Math.round(20 * (timeLeft / (stageConfig.durationSeconds ?? 300)))) : base;
      });
      setCurrentTarget((value) => Math.min(TARGET_ORDER.length, value + 1));
      setMissionStatus(nextTarget >= TARGET_ORDER.length ? 'Tamam' : 'Sıradaki');
      recordStrike(selectedTrack, 'isabet');
      disarmManualFire('Atış sonrası atış hattı düştü');
    } else if (stage === 2) {
      setRoundHits((value) => Math.min(3, value + 1));
      setHits((value) => value + 1);
      setNoHitStreak(0);
      setMissionStatus(roundHits + 1 >= 3 ? 'Tur hedefleri vuruldu' : 'Angajman');
      recordStrike(selectedTrack, 'isabet');
      addEvent('fire', 'AUTO_ENGAGE', selectedTrack ? `${selectedTrack.id} · kol ${selectedTrack.lane}` : 'seçili iz yok');
      return;
    } else {
      setHits((value) => value + 1);
      setRoundHits(1);
      setEnemyHitThisRound(true);
      setNoHitStreak(0);
      setMissionStatus('Düşman vuruldu · turu bitir');
      setScore((value) => value + (selectedTrack ? stage3TargetScore(selectedTrack) : 0));
      recordStrike(selectedTrack, 'isabet');
      addEvent('fire', 'AUTO_ENGAGE', selectedTrack ? `${selectedTrack.id} · ${selectedTrack.type} · ${selectedTrack.range.toFixed(1)} m` : 'seçili iz yok');
      return;
    }
    addEvent('fire', 'FIRE_MOCK', selectedTrack ? `${selectedTrack.id} · ${selectedTrack.range.toFixed(1)} m` : 'seçili iz yok');
  };

  const handleAutoToggle = () => {
    const next = !autoRunning;
    if (next && stage === 1) {
      addEvent('mode', 'OTONOM_BLOCK', 'Aşama 1 şartname gereği Manuel Mod');
      return;
    }
    if (next && systemHealth.blockReason !== 'ALLOWED') {
      addEvent('mode', 'OTONOM_BLOCK', blockCopy[systemHealth.blockReason]);
      return;
    }
    disarmManualFire('Otonom mod geçişi');
    setAutoRunning(next);
    setMode(next ? 'autonomous' : 'safe');
    setMissionStatus(next ? 'Aktif' : 'Beklemede');
    if (next) addEvent('mode', 'OTONOM_START', 'Tespit→Takip→Güvenlik Kapısı');
    else addEvent('mode', 'OTONOM_STOP', 'Operatör durdurdu');
  };

  const finishRound = () => {
    if (stage === 1) return;
    const maxRound = maxRoundFor(stage);
    let nextNoHitStreak = noHitStreak;
    if (stage === 2) {
      const roundScore = stage2RoundScore(roundHits);
      nextNoHitStreak = roundHits === 0 ? noHitStreak + 1 : 0;
      setScore((value) => (nextNoHitStreak >= 3 ? 0 : value + roundScore));
      addEvent('telemetry', 'ROUND_SCORE', `A2 tur ${round}: ${roundHits} isabet · ${roundScore} puan`);
    } else {
      nextNoHitStreak = enemyHitThisRound ? 0 : noHitStreak + 1;
      const penalty = enemyHitThisRound ? 0 : -10;
      setScore((value) => (nextNoHitStreak >= 3 ? 0 : value + penalty));
      addEvent('telemetry', enemyHitThisRound ? 'ENEMY_HIT_ROUND' : 'ENEMY_MISSED_PENALTY', `A3 tur ${round}: ${penalty} puan`);
    }
    setNoHitStreak(nextNoHitStreak);
    setRoundHits(0);
    setEnemyHitThisRound(false);
    if (nextNoHitStreak >= 3) {
      setMissionStatus('Başarısız');
      setAutoRunning(false);
      setMode('safe');
      addEvent('mode', 'MISSION_FAIL', '3 ardışık tur isabetsiz');
      return;
    }
    if (round >= maxRound) {
      const threshold = thresholdFor(stage);
      const projectedScore = stage === 2 ? score + stage2RoundScore(roundHits) : score + (enemyHitThisRound ? 0 : -10);
      setMissionStatus(projectedScore >= threshold ? 'Geçti' : 'Yetersiz');
      setAutoRunning(false);
      setMode('safe');
      addEvent('mode', 'MISSION_COMPLETE', `Puan ${projectedScore} / eşik ${threshold}`);
      return;
    }
    setRound((value) => value + 1);
    setSelectedId(undefined);
    setMissionStatus('Sonraki tur');
  };

  const handleMaintenance = () => {
    const next = !paused;
    setPaused(next);
    setMode(next ? 'maintenance' : 'safe');
    if (next) {
      disarmManualFire('Bakım molası');
      setMaintenanceBudget((value) => Math.max(0, value - mechanicsConfig.maintenanceMinimumSeconds));
    }
    addEvent('mode', next ? 'MAINTENANCE_PAUSE' : 'MAINTENANCE_RESUME', next ? `${mechanicsConfig.maintenanceMinimumSeconds} sn min. bütçe düşüldü` : 'Göreve hazır');
  };

  const resetSimulation = () => {
    disarmManualFire('Simülasyon sıfırlandı');
    setStage(1); setMode('safe'); setElapsed(0); setSelectedId(undefined); setCurrentTarget(0); setScore(0); setRound(1); setHits(0); setRoundHits(0); setEnemyHitThisRound(false); setNoHitStreak(0); setMissionStatus('Hazır'); setAutoRunning(false); setStrikes([]); setPaused(false); setMaintenanceBudget(mechanicsConfig.maintenanceBudgetSeconds); setPanAngle(0); setTiltAngle(0); setScenario('ALLOWED');
    addEvent('telemetry', 'RESET', 'Mock görev durumu sıfırlandı');
  };

  const toggleRealWorldSimulation = () => {
    const next = !realWorldSim;
    disarmManualFire('Gerçek yarışma simülasyonu geçişi');
    setRealWorldSim(next);
    setStage(1);
    setMode('safe');
    setElapsed(0);
    setSelectedId(undefined);
    setCurrentTarget(0);
    setScore(0);
    setRound(1);
    setHits(0);
    setRoundHits(0);
    setEnemyHitThisRound(false);
    setNoHitStreak(0);
    setMissionStatus(next ? 'Yarışma provası' : 'Hazır');
    setAutoRunning(false);
    setStrikes([]);
    setPaused(false);
    setMaintenanceBudget(mechanicsConfig.maintenanceBudgetSeconds);
    setPanAngle(0);
    setTiltAngle(0);
    setScenario('ALLOWED');
    addEvent('telemetry', next ? 'REALWORLD_SIM_ON' : 'REALWORLD_SIM_OFF', next ? 'Saha benzeri kamera/hardware akışı açıldı' : 'Mock akışa dönüldü');
  };

  return (
    <main className="console-shell">
      {baseSafety.estop && <div className="estop-overlay">ACİL DURDUR AKTİF · hareket ve atış kesildi · MOCK</div>}
      <header className="topbar">
        <div className="brand"><span className="brand-mark">⬢</span><div><b>GÖKKALKAN</b><small>Operatör Konsolu · {realWorldSim ? 'real_camera_sim' : 'hardware_mock'}</small></div></div>
        <nav className="segmented">
          {[1, 2, 3].map((item) => <button key={item} className={stage === item ? 'active' : ''} onClick={() => switchStage(item as Stage)}>Aşama {item}</button>)}
        </nav>
        <nav className="modebar">
          <IconButton label="Safe" icon="●" active={mode === 'safe'} onClick={() => switchMode('safe')} />
          <IconButton label="Manuel" icon="✣" active={mode === 'manual'} onClick={() => switchMode('manual')} />
          <IconButton label="Otonom" icon="◉" active={mode === 'autonomous'} onClick={() => switchMode('autonomous')} />
          <IconButton label="Bakım" icon="Ⅱ" active={mode === 'maintenance'} onClick={() => switchMode('maintenance')} />
        </nav>
        <div className={`mode-badge ${effectiveMode}`}>{modeLabel(effectiveMode)}</div>
      </header>

      <SafetyStrip systemHealth={systemHealth} commandSafety={fireSafety} scenario={scenario} mode={mode} onToggleEstop={toggleEstop} onScenario={setScenario} />
      {realWorldSim && <RehearsalStrip stage={stage} mode={mode} worldTelemetry={worldTelemetry} />}

      <section className="cockpit-grid">
        <div className="left-stack">
          <CameraViewport tracks={tracks} stage={stage} selectedId={selectedTrack?.id} onSelect={(id) => { setSelectedId(id); addEvent('target', 'TRACK_SELECT', id); }} panAngle={panAngle} tiltAngle={tiltAngle} feedLabel={realWorldSim ? 'GERÇEK YARIŞMA SİM · kamera + LiDAR/Radar mock + mekanik telemetri' : 'MOCK KAMERA · gerçek donanım bağlı değil'} sensorFrame={sensorFrame} strikes={strikes} realWorldSim={realWorldSim} />
          <div className="bottom-band">
            {stage === 1
              ? <ManualPanel currentTarget={currentTarget} selectedTrack={selectedTrack} score={score} timeLeft={timeLeft} fireGateAllowed={manualFireGateAllowed} fireAllowed={fireAllowed} armState={manualArmState} onArmStart={startManualArmFromPointer} onArmClick={startManualArmFromClick} onMove={handleMove} onFire={handleFire} onWrong={() => { setScore((value) => value - 5); disarmManualFire('Yanlış sıra simülasyonu'); addEvent('fire', 'WRONG_ORDER', 'Yanlış hedef sırası · -5'); }} />
              : <AutonomousPanel stage={stage} tracks={tracks} round={round} hits={hits} roundHits={roundHits} noHitStreak={noHitStreak} score={score} missionStatus={missionStatus} running={autoRunning} engageAllowed={fireAllowed} onToggle={handleAutoToggle} onEngage={handleFire} onNextRound={finishRound} />}
            {stage === 3 && <Stage3Intel selectedTrack={selectedTrack} />}
            <CommandQueue moveSafety={moveSafety} fireSafety={fireQueueSafety} fireReady={fireAllowed} fireLabel={fireQueueLabel} fireDetail={fireQueueDetail} />
          </div>
        </div>
        <aside className="right-stack">
          <VideoEvidencePanel events={events} />
          <MaintenancePanel paused={paused} prepLeft={prepLeft} budgetLeft={maintenanceBudget} onToggle={handleMaintenance} />
          <SettingsPanel onReset={resetSimulation} realWorldSim={realWorldSim} onToggleRealWorldSim={toggleRealWorldSimulation} worldTelemetry={worldTelemetry} />
          <TelemetryPanel events={events} filter={filter} onFilter={setFilter} onExport={() => exportJsonl(events)} />
        </aside>
      </section>
    </main>
  );
}

export default function App() {
  const [entered, setEntered] = useState(() => new URLSearchParams(window.location.search).has('console'));
  return entered ? <Console /> : <Landing onEnter={() => setEntered(true)} />;
}
