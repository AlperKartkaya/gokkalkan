import { useEffect, useMemo, useRef, useState } from 'react';
import { generateTracks, targetOrder } from './missionMock';
import { blockCopy, evaluateSafety } from './safetyGate';
import { exportJsonl, makeEvent } from './telemetry';
import type { BlockReason, EventType, Mode, SafetyState, Stage, TelemetryEvent, Track } from './types';

const filters: EventType[] = ['command', 'target', 'safety', 'fire', 'mode', 'telemetry'];
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

function CameraViewport({ tracks, stage, selectedId, onSelect }: { tracks: Track[]; stage: Stage; selectedId?: string; onSelect: (id: string) => void }) {
  return (
    <section className="viewport">
      <div className="sensor-lines" />
      <div className="lane-grid">
        <span>KOL 1</span><span>KOL 2</span><span>KOL 3</span>
      </div>
      <div className="reticle"><i /><b /></div>
      <div className="angle-readout left">PAN −12.4°</div>
      <div className="angle-readout right">TILT +06.8°</div>
      <div className="stage-watermark">AŞAMA {stage}</div>
      {tracks.map((track) => (
        <button
          key={track.id}
          className={`track-box ${track.friendFoe === 'Dost' ? 'friend' : ''} ${track.friendFoe === 'Düşman' ? 'enemy' : ''} ${track.candidate ? 'candidate' : ''} ${selectedId === track.id ? 'selected' : ''}`}
          style={{ left: `${track.x}%`, top: `${track.y}%`, width: `${track.w}%`, height: `${track.h}%` }}
          onClick={() => onSelect(track.id)}
          title={`${track.id} ${track.type}`}
        >
          <span className="track-id">{track.id}</span>
          <span className="track-meta">{track.type}</span>
          <span className="track-meta">{track.friendFoe} · {(track.confidence * 100).toFixed(0)}%</span>
          <span className="track-meta">{track.range.toFixed(1)} m</span>
        </button>
      ))}
      <div className="mock-feed">MOCK KAMERA · gerçek donanım bağlı değil</div>
    </section>
  );
}

function SafetyStrip({ safety, onToggleEstop, onScenario }: { safety: SafetyState; onToggleEstop: () => void; onScenario: (reason: BlockReason) => void }) {
  const chips = [
    ['Acil Durdur', !safety.estop],
    ['Harekete Yasak Alan', safety.motionZoneOk],
    ['Atışa Yasak Alan', safety.fireZoneOk],
    ['Menzil Kapısı', safety.targetGateOk],
    ['Mod Uyumu', safety.modeOk],
    ['Donanım Bağlantısı', safety.connectionOk],
  ] as const;

  return (
    <section className="safety-strip">
      <button className={`estop ${safety.estop ? 'engaged' : ''}`} onClick={onToggleEstop}>Acil Durdur <small>sim</small></button>
      <div className="safety-chips">
        {chips.map(([label, ok]) => <span key={label} className={statusClass(ok)}><i />{label}</span>)}
      </div>
      <div className={`block-reason ${safety.blockReason === 'ALLOWED' ? 'clear' : 'locked'}`}>{safety.blockReason} · {blockCopy[safety.blockReason]}</div>
      <select onChange={(event) => onScenario(event.target.value as BlockReason)} value="ALLOWED" aria-label="Blok senaryosu">
        <option value="ALLOWED">Blok senaryosu</option>
        {blockReasons.map((reason) => <option key={reason} value={reason}>{reason}</option>)}
      </select>
    </section>
  );
}

function ManualPanel({ currentTarget, score, timeLeft, fireAllowed, onMove, onFire, onWrong }: {
  currentTarget: number;
  score: number;
  timeLeft: number;
  fireAllowed: boolean;
  onMove: (cmd: string) => void;
  onFire: () => void;
  onWrong: () => void;
}) {
  return (
    <section className="work-panel manual-panel">
      <div className="panel-title"><b>Aşama 1</b><span>Manuel · 5 dk · ≥30 puan</span></div>
      <div className="target-order">
        {targetOrder.map((target, index) => <span key={target} className={index === currentTarget ? 'now' : index < currentTarget ? 'done' : ''}>{index + 1}. {target}</span>)}
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
          {['−0.5°', '+0.5°', 'Merkez', 'Yavaş'].map((label) => <button key={label} onClick={() => onMove(label)}>{label}</button>)}
        </div>
      </div>
      <div className="mission-metrics"><span>Süre <b>{timeLeft}s</b></span><span>Puan <b>{score}</b></span><span>Hedef <b>{currentTarget + 1}/4</b></span></div>
      <div className="fire-row">
        <button className="arm" disabled={!fireAllowed} onMouseDown={() => onMove('arm-hold')} title="Basılı tutarak simülasyon atış hattını kur">Basılı Kur</button>
        <button className="fire" disabled={!fireAllowed} onClick={onFire}>ATEŞ</button>
        <button className="warn" onClick={onWrong}>Yanlış sıra</button>
      </div>
    </section>
  );
}

function AutonomousPanel({ stage, tracks, round, hits, noHitStreak, running, onToggle }: {
  stage: 2 | 3;
  tracks: Track[];
  round: number;
  hits: number;
  noHitStreak: number;
  running: boolean;
  onToggle: () => void;
}) {
  const trace = stage === 2
    ? ['detect', 'track', 'prioritize', 'safety gate', 'engage/block']
    : ['classify', 'friend lock', 'range gate', 'safety gate', 'engage/block'];
  return (
    <section className="work-panel auto-panel">
      <div className="panel-title"><b>Aşama {stage}</b><span>{stage === 2 ? '4 tur · ≥20 puan · tip yok' : '8 tur · dost/düşman · ≥10 puan'}</span></div>
      <div className="rounds"><span>Tur <b>{round}/{stage === 2 ? 4 : 8}</b></span><span>İsabet <b>{hits}</b></span><span className={noHitStreak >= 2 ? 'danger-text' : ''}>Boş seri <b>{noHitStreak}</b></span></div>
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
      <div className="decision-trace">{trace.map((step, index) => <span key={step} className={index < 4 || running ? 'lit' : ''}>{step}</span>)}</div>
    </section>
  );
}

function Stage3Intel({ selectedTrack }: { selectedTrack?: Track }) {
  const target = selectedTrack;
  return (
    <section className="work-panel intel-panel">
      <div className="panel-title"><b>Dost/Düşman</b><span>Menzil kapısı</span></div>
      <div className={`foe-card ${target?.friendFoe === 'Düşman' ? 'enemy' : 'friend'}`}>
        <span>{target?.friendFoe ?? 'İz yok'}</span>
        <b>{target?.type ?? '—'}</b>
      </div>
      <div className="range-gauge"><span style={{ width: `${target ? Math.min(100, (target.range / 20) * 100) : 0}%` }} /><b>{target ? target.range.toFixed(1) : '—'} m</b></div>
      <div className={`gate-pill ${target?.rangeGate === 'Uygun' ? 'ok' : target?.rangeGate === 'Erken' ? 'warn' : 'bad'}`}>{target?.rangeGate ?? 'Bekle'}</div>
      <div className="penalties"><span>Dost ateş kilidi</span><b>{target?.friendFoe === 'Dost' ? 'Kilitli' : 'Açık'}</b><span>Ceza</span><b>-10 max/tur</b></div>
    </section>
  );
}

function VideoEvidencePanel() {
  const items = [
    'UI/joystick/klavye',
    '15 m balon atışı',
    'Hareket + Acil Durdur',
    'Atış + Acil Durdur',
    'Yaw/elev takip',
    '5/10/15 m sınıflandırma',
  ];
  return (
    <section className="thin-panel video-panel">
      <div className="panel-title"><b>Video Kanıtı</b><span>720p+ · 2-5 dk · tek YouTube</span></div>
      {items.map((item, index) => <label key={item}><input type="checkbox" />Y{index + 1}<span>{item}</span><time>{`0${index}:00`}</time></label>)}
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
      <small>Her talep min. 30 sn düşer</small>
    </section>
  );
}

function SettingsPanel({ onReset }: { onReset: () => void }) {
  return (
    <section className="thin-panel settings-panel">
      <div className="panel-title"><b>Ayar/Kalibrasyon</b><span>mock</span></div>
      <div className="setting-grid">
        <span>Kamera</span><b>MockCam-01</b>
        <span>Serial/CAN</span><b className="amber">Sim bağlı</b>
        <span>Pan/Tilt</span><b>±75° / −10..45°</b>
        <span>Hareket yasak</span><b>arka ±105°</b>
        <span>Atış yasak</span><b>seyirci ROI</b>
        <span>Menzil</span><b>F16 10-15 · diğer 5-15</b>
        <span>Eşikler</span><b>renk/şekil TODO</b>
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
        {filters.map((item) => <button key={item} className={filter === item ? 'active' : ''} onClick={() => onFilter(item)}>{item}</button>)}
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

function CommandQueue({ safety }: { safety: SafetyState }) {
  const blocked = safety.blockReason !== 'ALLOWED';
  return (
    <section className="queue-panel">
      <div className="panel-title"><b>Komut Kuyruğu</b><span>hardware_mock</span></div>
      <div className={`queue-item ${blocked ? 'blocked' : 'ready'}`}><span>pan/tilt</span><b>{blocked ? 'blocked' : 'queued'}</b></div>
      <div className={`queue-item ${blocked ? 'blocked' : 'ready'}`}><span>fire_enable</span><b>{blocked ? 'blocked' : 'armed gate'}</b></div>
      <small>Gerçek motor/ateş komutu gönderilmez.</small>
    </section>
  );
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
  const [noHitStreak, setNoHitStreak] = useState(0);
  const [autoRunning, setAutoRunning] = useState(false);
  const [paused, setPaused] = useState(false);
  const [maintenanceBudget, setMaintenanceBudget] = useState(600);
  const [filter, setFilter] = useState<EventType | 'all'>('all');
  const [baseSafety, setBaseSafety] = useState<Omit<SafetyState, 'blockReason'>>({
    estop: false,
    motionZoneOk: true,
    fireZoneOk: true,
    targetGateOk: true,
    modeOk: true,
    connectionOk: true,
  });
  const eventId = useRef(1);
  const [events, setEvents] = useState<TelemetryEvent[]>([
    makeEvent(0, 1, 'safe', 'telemetry', 'BOOT_OK', 'Mock arayüz başlatıldı'),
  ]);

  const tracks = useMemo(() => generateTracks(stage, elapsed), [stage, elapsed]);
  const selectedTrack = tracks.find((track) => track.id === selectedId) ?? tracks.find((track) => track.candidate) ?? tracks[0];
  const commandKind = mode === 'autonomous' ? 'autonomous' : 'fire';
  const safety = evaluateSafety({ stage, mode, base: baseSafety, selectedTrack, command: commandKind });
  const fireAllowed = safety.blockReason === 'ALLOWED' && (mode === 'manual' || mode === 'autonomous' || mode === 'engagement');
  const effectiveMode = safety.blockReason === 'ALLOWED' ? mode : 'blocked';

  const addEvent = (type: EventType, decision: string, reason: string) => {
    const next = makeEvent(eventId.current++, stage, effectiveMode, type, decision, reason);
    setEvents((prev) => [next, ...prev].slice(0, 80));
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
    if (safety.blockReason !== 'ALLOWED') addEvent('safety', safety.blockReason, blockCopy[safety.blockReason]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [safety.blockReason]);

  const switchStage = (nextStage: Stage) => {
    setStage(nextStage);
    setMode(nextStage === 1 ? 'manual' : 'safe');
    setSelectedId(undefined);
    setRound(1);
    setHits(0);
    setNoHitStreak(0);
    addEvent('mode', `AŞAMA_${nextStage}`, 'Görev senaryosu değişti');
  };

  const switchMode = (nextMode: Mode) => {
    setMode(nextMode);
    setAutoRunning(nextMode === 'autonomous' ? autoRunning : false);
    addEvent('mode', modeLabel(nextMode), 'Operatör mod geçişi');
  };

  const setScenario = (reason: BlockReason) => {
    const clear = { estop: false, motionZoneOk: true, fireZoneOk: true, targetGateOk: true, modeOk: true, connectionOk: true };
    const next = { ...clear };
    if (reason === 'BLOCKED_ESTOP') next.estop = true;
    if (reason === 'BLOCKED_MOTION_ZONE') next.motionZoneOk = false;
    if (reason === 'BLOCKED_FIRE_ZONE') next.fireZoneOk = false;
    if (reason === 'BLOCKED_TARGET_GATE') next.targetGateOk = false;
    if (reason === 'BLOCKED_MODE') next.modeOk = false;
    if (reason === 'BLOCKED_CONNECTION') next.connectionOk = false;
    setBaseSafety(next);
    addEvent('safety', reason, reason === 'ALLOWED' ? 'Kilit temizlendi' : blockCopy[reason]);
  };

  const handleMove = (cmd: string) => {
    const moveGate = evaluateSafety({ stage, mode, base: baseSafety, selectedTrack, command: 'move' });
    addEvent('command', moveGate.blockReason === 'ALLOWED' ? `MOVE_${cmd}` : 'MOVE_BLOCK', blockCopy[moveGate.blockReason]);
  };

  const handleFire = () => {
    if (!fireAllowed) {
      addEvent('fire', 'FIRE_BLOCK', blockCopy[safety.blockReason]);
      return;
    }
    if (stage === 1) {
      setScore((value) => value + [5, 10, 20, 20][currentTarget]);
      setCurrentTarget((value) => Math.min(3, value + 1));
    } else {
      setHits((value) => value + 1);
      setNoHitStreak(0);
    }
    addEvent('fire', 'FIRE_MOCK', selectedTrack ? `${selectedTrack.id} · ${selectedTrack.range.toFixed(1)} m` : 'seçili iz yok');
  };

  const handleAutoToggle = () => {
    const next = !autoRunning;
    setAutoRunning(next);
    setMode(next ? 'autonomous' : 'safe');
    if (next) addEvent('mode', 'OTONOM_START', 'detect→track→safety gate');
    else addEvent('mode', 'OTONOM_STOP', 'Operatör durdurdu');
  };

  const handleMaintenance = () => {
    const next = !paused;
    setPaused(next);
    setMode(next ? 'maintenance' : 'safe');
    if (next) setMaintenanceBudget((value) => Math.max(0, value - 30));
    addEvent('mode', next ? 'MAINTENANCE_PAUSE' : 'MAINTENANCE_RESUME', next ? '30 sn min. bütçe düşüldü' : 'Göreve hazır');
  };

  const resetSimulation = () => {
    setStage(1); setMode('safe'); setElapsed(0); setSelectedId(undefined); setCurrentTarget(0); setScore(0); setRound(1); setHits(0); setNoHitStreak(0); setAutoRunning(false); setPaused(false); setMaintenanceBudget(600); setScenario('ALLOWED');
    addEvent('telemetry', 'RESET', 'Mock görev durumu sıfırlandı');
  };

  const timeLeft = Math.max(0, 300 - Math.floor(elapsed));
  const prepLeft = Math.max(0, 1800 - Math.floor(elapsed * 6));

  return (
    <main className="console-shell">
      {baseSafety.estop && <div className="estop-overlay">ACİL DURDUR AKTİF · hareket ve atış kesildi · MOCK</div>}
      <header className="topbar">
        <div className="brand"><span className="brand-mark">⬢</span><div><b>GÖKKALKAN</b><small>Operatör Konsolu · hardware_mock</small></div></div>
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

      <SafetyStrip safety={safety} onToggleEstop={() => setBaseSafety((prev) => ({ ...prev, estop: !prev.estop }))} onScenario={setScenario} />

      <section className="cockpit-grid">
        <div className="left-stack">
          <CameraViewport tracks={tracks} stage={stage} selectedId={selectedTrack?.id} onSelect={(id) => { setSelectedId(id); addEvent('target', 'TRACK_SELECT', id); }} />
          <div className="bottom-band">
            {stage === 1
              ? <ManualPanel currentTarget={currentTarget} score={score} timeLeft={timeLeft} fireAllowed={fireAllowed} onMove={handleMove} onFire={handleFire} onWrong={() => { setScore((value) => value - 5); addEvent('fire', 'WRONG_ORDER', 'Yanlış hedef sırası · -5'); }} />
              : <AutonomousPanel stage={stage} tracks={tracks} round={round} hits={hits} noHitStreak={noHitStreak} running={autoRunning} onToggle={handleAutoToggle} />}
            {stage === 3 && <Stage3Intel selectedTrack={selectedTrack} />}
            <CommandQueue safety={safety} />
          </div>
        </div>
        <aside className="right-stack">
          <VideoEvidencePanel />
          <MaintenancePanel paused={paused} prepLeft={prepLeft} budgetLeft={maintenanceBudget} onToggle={handleMaintenance} />
          <SettingsPanel onReset={resetSimulation} />
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
