import { useEffect, useMemo, useRef, useState } from 'react';
import stage1MapUrl from './assets/stage1-parkour.png';
import stage2MapUrl from './assets/stage2-parkour.png';
import stage3MapUrl from './assets/stage3-parkour.png';
import { COMPETITION_COURSE } from './competitionCourse';
import {
  COMPETITION_STAGE_ROUNDS,
  competitionSimulationConfig,
  generateCompetitionTracks,
  roundDurationFor,
  stage1ScoreForRange,
  stage2RoundScore,
  stage3TargetScore,
  type SimulatorMode,
} from './competitionSimulation';
import { mechanicsConfig } from './mechanicsConfig';
import { TARGET_ORDER, rangeRuleFor, stageConfigFor, thresholdFor } from './missionConfig';
import { blockCopy, evaluateSafety, evaluateSystemHealth } from './safetyGate';
import { exportJsonl, makeEvent } from './telemetry';
import type { EventType, Mode, SafetyState, Stage, TelemetryEvent, Track } from './types';

const mapByStage: Record<Stage, string> = {
  1: stage1MapUrl,
  2: stage2MapUrl,
  3: stage3MapUrl,
};

const modeCopy: Record<Mode, string> = {
  safe: 'Beklemede',
  manual: 'Manuel',
  autonomous: 'Otonom',
  engagement: 'Angajman',
  blocked: 'Kilitli',
  maintenance: 'Bakım',
};

const targetIcon: Record<Track['type'], string> = {
  F16: '✈',
  Helikopter: '✚',
  'Balistik Füze': '◆',
  'Mini/Micro İHA': '✦',
};

const tutorialSteps: Array<{
  id: string;
  stage: 'global' | Stage;
  title: string;
  message: string;
  highlight: 'map' | 'fire' | 'mode' | 'guidance' | 'ranges' | 'stage-order';
}> = [
  {
    id: 'global-map',
    stage: 'global',
    title: 'Parkur ana çalışma alanıdır',
    message: 'Hedefler A noktasından başlayıp B bölgesine doğru ilerler. Simülasyon, rehberlik açıkken hedefleri, süreyi ve puanı tamamen duraklatır.',
    highlight: 'map',
  },
  {
    id: 'global-range',
    stage: 'global',
    title: 'Menzil bantlarını izle',
    message: '15 m, 10 m ve 5 m çizgileri resmi parkur diyagramındaki angajman aralıklarını temsil eder. Yeşil bant seçili hedef için geçerli ateş penceresidir.',
    highlight: 'ranges',
  },
  {
    id: 'stage1-order',
    stage: 1,
    title: 'Aşama 1 manuel sıraya bağlıdır',
    message: 'Zarf sırası Balistik Füze → Helikopter → F16 → Mini/Micro İHA olarak gösterilir. Yanlış hedefe ateş edersen simülasyon hemen -5 ceza uygular.',
    highlight: 'stage-order',
  },
  {
    id: 'stage1-fire',
    stage: 1,
    title: 'FIRE düğmesi yarışma aksiyonudur',
    message: 'Doğru hedef seçiliyken FIRE düğmesine bas. Basmazsan hedef imha edilmez; süre işlemeye devam eder.',
    highlight: 'fire',
  },
  {
    id: 'stage2-auto',
    stage: 2,
    title: 'Aşama 2 otonomdur',
    message: 'Dört tur vardır. Her turda üç kolda birer hedef A→B hareket eder. Görevin otonom modu başlatmak ve sistemin hedefleri B’ye ulaşmadan imha etmesini izlemektir.',
    highlight: 'mode',
  },
  {
    id: 'stage3-friend',
    stage: 3,
    title: 'Dost hedefler korunur',
    message: 'Aşama 3’te her turda 1 kırmızı/düşman ve 2 mavi/dost unsur vardır. Dost hedef vurulmamalı; düşman hedef kendi menzil kapısında imha edilmelidir.',
    highlight: 'guidance',
  },
];

interface StrikeEffect {
  id: number;
  trackId: string;
  x: number;
  y: number;
  label: string;
  result: 'hit' | 'penalty' | 'miss';
}

function formatTime(seconds: number) {
  const bounded = Math.max(0, Math.floor(seconds));
  return `${Math.floor(bounded / 60)}:${String(bounded % 60).padStart(2, '0')}`;
}

function stageModeExpectation(stage: Stage): Mode {
  return stage === 1 ? 'manual' : 'autonomous';
}

function CourseMap({
  stage,
  tracks,
  selectedTrack,
  destroyedIds,
  strikes,
  tutorialHighlight,
  onSelect,
}: {
  stage: Stage;
  tracks: Track[];
  selectedTrack?: Track;
  destroyedIds: string[];
  strikes: StrikeEffect[];
  tutorialHighlight?: string;
  onSelect: (id: string) => void;
}) {
  const points = (items: Array<{ x: number; y: number }>) => items.map((point) => `${point.x},${point.y}`).join(' ');
  const rule = selectedTrack && stage === 3 ? rangeRuleFor(selectedTrack.type) : undefined;
  const xForRange = (range: number) => 88 - range * 5;
  const validStart = rule ? Math.min(xForRange(rule.max), xForRange(rule.min)) : xForRange(15);
  const validWidth = rule ? Math.abs(xForRange(rule.min) - xForRange(rule.max)) : Math.abs(xForRange(0) - xForRange(15));

  return (
    <section className={`parkour-hero stage-${stage} ${tutorialHighlight === 'map' || tutorialHighlight === 'ranges' ? 'tutorial-pulse' : ''}`} data-testid="parkour-hero">
      <img src={mapByStage[stage]} alt={`Aşama ${stage} resmi parkur kırpımı`} />
      <svg className="parkour-overlay" viewBox="0 0 100 100" aria-hidden="true">
        <rect className="valid-window" x={validStart} y="15" width={validWidth} height="77" />
        {[15, 10, 5].map((range) => (
          <g key={range} className="range-line" data-testid={`range-${range}m`}>
            <line x1={xForRange(range)} y1="10" x2={xForRange(range)} y2="93" />
            <text x={xForRange(range) + 0.7} y="12">{range} m</text>
          </g>
        ))}
        {stage !== 1 && <>
          <text className="point-label" x="7" y="11">A</text>
          <text className="point-label" x="78" y="11">B</text>
          {COMPETITION_COURSE.lanes.map((lane) => (
            <g key={lane.lane} className={`lane-path lane-${lane.lane}`}>
              <polyline points={points(lane.points)} />
              <text x="8" y={lane.points[0].y - 2}>KOL {lane.lane}</text>
            </g>
          ))}
        </>}
        <g className="system-anchor">
          <circle cx={COMPETITION_COURSE.systemPosition.x} cy={COMPETITION_COURSE.systemPosition.y} r="2.6" />
          <text x="78" y="62">Gökkalkan</text>
        </g>
        {strikes.map((strike) => (
          <g key={strike.id} className={`strike ${strike.result}`}>
            <line x1={COMPETITION_COURSE.systemPosition.x} y1={COMPETITION_COURSE.systemPosition.y} x2={strike.x} y2={strike.y} />
            <circle cx={strike.x} cy={strike.y} r="3.2" />
            <text x={Math.min(88, strike.x + 2)} y={Math.max(9, strike.y - 2)}>{strike.label}</text>
          </g>
        ))}
      </svg>
      {tracks.map((track) => {
        const selected = selectedTrack?.id === track.id;
        const destroyed = destroyedIds.includes(track.id);
        const affiliationClass = track.friendFoe === 'Düşman' ? 'enemy' : track.friendFoe === 'Dost' ? 'friend' : 'neutral';
        return (
          <button
            key={track.id}
            className={`aircraft ${affiliationClass} ${selected ? 'selected' : ''} ${track.candidate ? 'candidate' : ''} ${destroyed ? 'destroyed' : ''}`}
            style={{ left: `${track.x}%`, top: `${track.y}%`, width: `${track.w}%`, height: `${track.h}%` }}
            data-testid={`track-${track.id}`}
            aria-label={`${track.id} ${track.type} ${track.friendFoe} ${track.range.toFixed(1)} metre`}
            onClick={() => onSelect(track.id)}
          >
            <b>{targetIcon[track.type]}</b>
            <span>{stage === 2 ? `Kol ${track.lane}` : track.friendFoe}</span>
            <small>{track.type}</small>
          </button>
        );
      })}
      <div className="map-legend">
        <span><i className="enemy-dot" />Düşman</span>
        <span><i className="friend-dot" />Dost</span>
        <span><i className="window-dot" />Geçerli ateş penceresi</span>
      </div>
      <div className="map-assumption">{competitionSimulationConfig.assumptionNotice}</div>
    </section>
  );
}

function CompetitionHeader({
  stage,
  mode,
  timer,
  score,
  round,
  safetyState,
  simulatorMode,
  onStage,
  onSimulatorMode,
}: {
  stage: Stage;
  mode: Mode;
  timer: string;
  score: number;
  round: number;
  safetyState: SafetyState;
  simulatorMode: SimulatorMode;
  onStage: (stage: Stage) => void;
  onSimulatorMode: (mode: SimulatorMode) => void;
}) {
  const safetyOk = safetyState.blockReason === 'ALLOWED';
  return (
    <header className="competition-header">
      <div className="app-title"><span>⬢</span><div><b>GÖKKALKAN</b><small>TEKNOFEST Çelikkubbe Final Simülatörü</small></div></div>
      <nav className="stage-switch" aria-label="Aşama seçimi">
        {([1, 2, 3] as const).map((item) => <button key={item} className={stage === item ? 'active' : ''} onClick={() => onStage(item)}>Aşama {item}</button>)}
      </nav>
      <div className="header-metrics">
        <span>Mod <b>{modeCopy[mode]}</b></span>
        <span>Süre <b>{timer}</b></span>
        <span>Puan <b>{score}</b></span>
        <span>Tur <b>{round}/{COMPETITION_STAGE_ROUNDS[stage]}</b></span>
        <span className={safetyOk ? 'safe' : 'unsafe'}>Güvenlik <b>{safetyOk ? 'Hazır' : blockCopy[safetyState.blockReason]}</b></span>
      </div>
      <button className={`sim-mode ${simulatorMode}`} onClick={() => onSimulatorMode(simulatorMode === 'strict' ? 'practice' : 'strict')}>
        {simulatorMode === 'strict' ? 'Sıkı yarışma' : 'Pratik modu'}
      </button>
    </header>
  );
}

function GuidancePanel({
  stage,
  mode,
  round,
  selectedTrack,
  fireStatus,
  fireReason,
  scoreImpact,
  missionStatus,
  tutorialHighlight,
  onRestartTutorial,
}: {
  stage: Stage;
  mode: Mode;
  round: number;
  selectedTrack?: Track;
  fireStatus: string;
  fireReason: string;
  scoreImpact: string;
  missionStatus: string;
  tutorialHighlight?: string;
  onRestartTutorial: () => void;
}) {
  const stageConfig = stageConfigFor(stage);
  const objective = stage === 1
    ? 'Zarf sırasındaki durağan hedefleri manuel ateşle imha et.'
    : stage === 2
      ? 'Üç koldaki hedefleri her turda B’ye ulaşmadan otonom imha et.'
      : 'Dostları koru; sadece düşman hedefi doğru menzil kapısında imha et.';
  const nextAction = stage === 1
    ? mode === 'manual' ? 'Beklenen hedefi seç ve FIRE kararını ver.' : 'Manuel moda geç.'
    : mode === 'autonomous' ? 'Otonom akışı izleyip tur sonucunu takip et.' : 'Otonom modu başlat.';
  const ruleReminder = stage === 1
    ? 'Aşama 1: yakın +5, orta +10, uzun +20; yanlış hedef -5; 80 taban puana zaman bonusu eklenir.'
    : stage === 2
      ? 'Aşama 2: 4 tur, tur başına 1/2/3 imha = +5/+15/+30; 0 imha = -5; sınıflandırma beklenmez.'
      : 'Aşama 3: F16 10–15 m +30; Helikopter/Balistik Füze 5–15 m +20; Mini/Micro İHA 0–15 m +10; dost/kaçan düşman cezası -10 max/tur.';

  return (
    <aside className={`guidance-panel ${tutorialHighlight === 'guidance' ? 'tutorial-pulse' : ''}`} data-testid="competition-guidance">
      <div className="panel-kicker">Competition Guidance</div>
      <h2>{stageConfig.title}</h2>
      <section>
        <span>Current Objective</span>
        <p>{objective}</p>
      </section>
      <section>
        <span>Next Required Action</span>
        <p>{nextAction}</p>
      </section>
      <section className="fire-card">
        <span>Fire Status</span>
        <b>{fireStatus}</b>
        <p>{fireReason}</p>
      </section>
      <section>
        <span>Score impact if fired now</span>
        <p>{scoreImpact}</p>
      </section>
      <section>
        <span>Current target details</span>
        <p>{selectedTrack ? `${selectedTrack.id} · ${selectedTrack.type} · ${selectedTrack.friendFoe} · ${selectedTrack.range.toFixed(1)} m · ${selectedTrack.rangeGate}` : 'Seçili hedef yok'}</p>
      </section>
      <section>
        <span>Mini rule reminder</span>
        <p>{ruleReminder}</p>
      </section>
      <section>
        <span>Round state</span>
        <p>Tur {round}/{COMPETITION_STAGE_ROUNDS[stage]} · {missionStatus}</p>
      </section>
      <button className="restart-tutorial" onClick={onRestartTutorial}>Rehberi yeniden başlat</button>
    </aside>
  );
}

function StageChecklist({ stage, currentTarget, destroyedIds, round, roundHits }: { stage: Stage; currentTarget: number; destroyedIds: string[]; round: number; roundHits: number }) {
  if (stage === 1) {
    return (
      <div className="stage-checklist" data-testid="stage-1-order">
        {TARGET_ORDER.map((target, index) => (
          <span key={target} className={index < currentTarget ? 'done' : index === currentTarget ? 'current' : ''}>{target}</span>
        ))}
      </div>
    );
  }
  return (
    <div className="stage-checklist compact">
      {Array.from({ length: COMPETITION_STAGE_ROUNDS[stage] }, (_, index) => index + 1).map((item) => (
        <span key={item} className={item < round ? 'done' : item === round ? 'current' : ''}>Tur {item}{item === round ? ` · ${roundHits || destroyedIds.length} imha` : ''}</span>
      ))}
    </div>
  );
}

function BottomActionBar({
  stage,
  mode,
  currentTarget,
  destroyedIds,
  round,
  roundHits,
  paused,
  estop,
  fireDisabled,
  fireButtonText,
  fireReason,
  tutorialHighlight,
  onFire,
  onMode,
  onPause,
  onReset,
  onEstop,
}: {
  stage: Stage;
  mode: Mode;
  currentTarget: number;
  destroyedIds: string[];
  round: number;
  roundHits: number;
  paused: boolean;
  estop: boolean;
  fireDisabled: boolean;
  fireButtonText: string;
  fireReason: string;
  tutorialHighlight?: string;
  onFire: () => void;
  onMode: (mode: Mode) => void;
  onPause: () => void;
  onReset: () => void;
  onEstop: () => void;
}) {
  return (
    <section className="bottom-action-bar" data-testid="bottom-action-bar">
      <StageChecklist stage={stage} currentTarget={currentTarget} destroyedIds={destroyedIds} round={round} roundHits={roundHits} />
      <div className="main-controls">
        <button className={mode === 'manual' ? 'active' : ''} onClick={() => onMode('manual')}>Manuel</button>
        <button className={mode === 'autonomous' ? 'active' : ''} onClick={() => onMode('autonomous')}>Otonom</button>
        <button onClick={onPause}>{paused ? 'Devam' : 'Duraklat'}</button>
        <button className={estop ? 'danger active' : 'danger'} onClick={onEstop}>Acil Durdur</button>
        <button onClick={onReset}>Aşamayı Sıfırla</button>
      </div>
      <div className={`fire-cluster ${tutorialHighlight === 'fire' ? 'tutorial-pulse' : ''}`} data-testid="fire-cluster">
        <button className="primary-fire" disabled={fireDisabled} onClick={onFire}>{fireButtonText}</button>
        <small>{fireReason}</small>
      </div>
    </section>
  );
}

function DebugDrawer({
  baseSafety,
  fireSafety,
  events,
  selectedTrack,
  elapsed,
  maintenanceBudget,
}: {
  baseSafety: Omit<SafetyState, 'blockReason'>;
  fireSafety: SafetyState;
  events: TelemetryEvent[];
  selectedTrack?: Track;
  elapsed: number;
  maintenanceBudget: number;
}) {
  const visibleEvents = events.slice(0, 10);
  return (
    <details className="debug-drawer">
      <summary>Advanced / Debug</summary>
      <div className="debug-grid">
        <section>
          <b>Safety gate</b>
          <code>{JSON.stringify({ ...baseSafety, command: fireSafety.blockReason }, null, 2)}</code>
        </section>
        <section>
          <b>Simulation config</b>
          <code>{JSON.stringify({ elapsed: Number(elapsed.toFixed(1)), maintenanceBudget, speed: { stage2: competitionSimulationConfig.stage2.targetSpeedMps, stage3: competitionSimulationConfig.stage3.targetSpeedMps }, selectedTrack }, null, 2)}</code>
        </section>
        <section className="event-debug">
          <b>Event log</b>
          {visibleEvents.map((event) => <p key={event.id}><span>{event.timestamp}</span> A{event.stage} {event.decision} · {event.reason}</p>)}
          <button onClick={() => exportJsonl(events)}>JSONL dışa aktar</button>
        </section>
      </div>
    </details>
  );
}

function TutorialOverlay({ step, index, count, onNext, onSkip }: { step: (typeof tutorialSteps)[number]; index: number; count: number; onNext: () => void; onSkip: () => void }) {
  return (
    <div className="tutorial-overlay" role="dialog" aria-modal="true" data-testid="tutorial-overlay">
      <div className="tutorial-card">
        <span>Rehber {index + 1}/{count} · simülasyon duraklatıldı</span>
        <h2>{step.title}</h2>
        <p>{step.message}</p>
        <div className="tutorial-actions">
          <button onClick={onSkip}>Rehberi atla</button>
          <button className="continue" onClick={onNext}>{index + 1 === count ? 'Bitir ve devam et' : 'Devam'}</button>
        </div>
      </div>
    </div>
  );
}

function Landing({ onEnter }: { onEnter: () => void }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setProgress((value) => Math.min(100, value + 5)), 120);
    return () => window.clearInterval(id);
  }, []);

  return (
    <main className="landing">
      <div className="landing-grid" />
      <svg className="dome-scene" viewBox="0 0 1200 760" role="img" aria-label="Çelikkubbe simülatörü">
        <defs>
          <radialGradient id="domeGlow" cx="50%" cy="70%" r="65%">
            <stop offset="0%" stopColor="#00e5ff" stopOpacity="0.26" />
            <stop offset="70%" stopColor="#00e5ff" stopOpacity="0.06" />
            <stop offset="100%" stopColor="#00e5ff" stopOpacity="0" />
          </radialGradient>
        </defs>
        <rect width="1200" height="760" fill="#020304" />
        <path className="dome-fill" d="M190 622 A410 410 0 0 1 1010 622" fill="url(#domeGlow)" />
        <path className="dome-arc arc-main" d="M190 622 A410 410 0 0 1 1010 622" />
        <path className="dome-arc arc-mid" d="M278 622 A322 322 0 0 1 922 622" />
        <g className="radar"><circle cx="600" cy="620" r="140" /><circle cx="600" cy="620" r="260" /><path d="M600 620 L930 462" className="radar-sweep" /></g>
        {[0, 1, 2, 3].map((item) => <g key={item} className={`incoming incoming-${item}`}><path d="M0 0 l34 8 l-34 8 l8 -8 z" /><line x1="-74" y1="8" x2="-16" y2="8" /></g>)}
      </svg>
      <section className="boot-card">
        <h1 className="signal">GÖKKALKAN</h1>
        <div className="boot-sub">Çelikkubbe final aşama eğitim simülatörü</div>
        <div className="boot-checks">
          {['Parkur', 'Aşama Kuralları', 'Menzil Kapısı', 'Dost/Düşman', 'Puanlama'].map((check, index) => <span key={check} className={progress > index * 18 ? 'done' : ''}><i />{check}</span>)}
        </div>
        <div className="boot-progress"><span style={{ width: `${progress}%` }} /></div>
        <button className="enter-console" onClick={onEnter}>Simülatöre Başla</button>
      </section>
    </main>
  );
}

function Console() {
  const [stage, setStage] = useState<Stage>(1);
  const [mode, setMode] = useState<Mode>('manual');
  const [simulatorMode, setSimulatorMode] = useState<SimulatorMode>('practice');
  const [elapsed, setElapsed] = useState(0);
  const [round, setRound] = useState(1);
  const [score, setScore] = useState(0);
  const [currentTarget, setCurrentTarget] = useState(0);
  const [destroyedIds, setDestroyedIds] = useState<string[]>([]);
  const [roundHits, setRoundHits] = useState(0);
  const [noHitStreak, setNoHitStreak] = useState(0);
  const [missionStatus, setMissionStatus] = useState('Hazır');
  const [paused, setPaused] = useState(false);
  const [selectedId, setSelectedId] = useState<string>();
  const [strikes, setStrikes] = useState<StrikeEffect[]>([]);
  const [maintenanceBudget, setMaintenanceBudget] = useState(mechanicsConfig.maintenanceBudgetSeconds);
  const [baseSafety, setBaseSafety] = useState<Omit<SafetyState, 'blockReason'>>({
    estop: false,
    motionZoneOk: true,
    fireZoneOk: true,
    targetGateOk: true,
    modeOk: true,
    connectionOk: mechanicsConfig.mockConnectionOk,
  });
  const [events, setEvents] = useState<TelemetryEvent[]>([makeEvent(0, 1, 'manual', 'telemetry', 'BOOT_OK', 'Yarışma simülatörü başlatıldı')]);
  const [tutorialVisible, setTutorialVisible] = useState(true);
  const [tutorialIndex, setTutorialIndex] = useState(0);
  const eventId = useRef(1);
  const strikeId = useRef(1);
  const autoFireAt = useRef(-10);
  const roundResolved = useRef(false);

  const stageSteps = useMemo(() => tutorialSteps.filter((step) => step.stage === 'global' || step.stage === stage), [stage]);
  const tutorialStep = tutorialVisible ? stageSteps[Math.min(tutorialIndex, stageSteps.length - 1)] : undefined;
  const tutorialHighlight = tutorialStep?.highlight;
  const hardPaused = paused || tutorialVisible || baseSafety.estop || mode === 'maintenance';
  const timeLeft = stage === 1 ? Math.max(0, competitionSimulationConfig.stage1.timeLimitSeconds - elapsed) : Math.max(0, roundDurationFor(stage) - elapsed);

  const rawTracks = useMemo(() => generateCompetitionTracks(stage, elapsed, round), [stage, elapsed, round]);
  const tracks = useMemo(() => rawTracks
    .filter((track) => !destroyedIds.includes(track.id))
    .map((track) => ({
      ...track,
      candidate: stage === 1 ? TARGET_ORDER[currentTarget] === track.type : track.candidate,
    })), [currentTarget, destroyedIds, rawTracks, stage]);
  const selectedTrack = tracks.find((track) => track.id === selectedId) ?? tracks.find((track) => track.candidate) ?? tracks[0];
  const systemHealth = evaluateSystemHealth(baseSafety);
  const fireSafety = evaluateSafety({
    stage,
    mode,
    base: baseSafety,
    selectedTrack,
    command: stage === 1 ? 'fire' : 'autonomous_engage',
  });

  const addEvent = (type: EventType, decision: string, reason: string) => {
    const event = makeEvent(eventId.current++, stage, mode, type, decision, reason);
    setEvents((previous) => [event, ...previous].slice(0, 100));
  };

  const recordStrike = (track: Track | undefined, result: StrikeEffect['result'], label: string) => {
    if (!track) return;
    const id = strikeId.current++;
    const strike: StrikeEffect = { id, trackId: track.id, x: track.x, y: track.y, label, result };
    setStrikes((previous) => [strike, ...previous].slice(0, 5));
    window.setTimeout(() => setStrikes((previous) => previous.filter((item) => item.id !== id)), 2_400);
  };

  const resetStageState = (nextStage = stage) => {
    roundResolved.current = false;
    autoFireAt.current = -10;
    setElapsed(0);
    setRound(1);
    setScore(0);
    setCurrentTarget(0);
    setDestroyedIds([]);
    setRoundHits(0);
    setNoHitStreak(0);
    setMissionStatus('Hazır');
    setPaused(false);
    setSelectedId(undefined);
    setStrikes([]);
    setMode(stageModeExpectation(nextStage));
    setBaseSafety((previous) => ({ ...previous, estop: false, targetGateOk: true, modeOk: true }));
  };

  const switchStage = (nextStage: Stage) => {
    if (simulatorMode === 'strict' && nextStage > stage && stage < 3 && score < thresholdFor(stage)) {
      setMissionStatus(`Sıkı mod: Aşama ${stage} eşiği ${thresholdFor(stage)} puan, mevcut ${score}.`);
      addEvent('safety', 'THRESHOLD_BLOCK', `Sıkı mod aşama geçişini engelledi: ${score}/${thresholdFor(stage)}`);
      return;
    }
    setStage(nextStage);
    resetStageState(nextStage);
    setTutorialIndex(0);
    addEvent('mode', `AŞAMA_${nextStage}`, 'Yarışma aşaması değiştirildi');
  };

  const finishRound = (forced = false, resolution?: { stage2Hits?: number; stage3HostileDestroyed?: boolean }) => {
    if (stage === 1 || roundResolved.current) return;
    roundResolved.current = true;
    const maxRound = COMPETITION_STAGE_ROUNDS[stage];
    if (stage === 2) {
      const hits = resolution?.stage2Hits ?? destroyedIds.length;
      const delta = stage2RoundScore(hits);
      const nextStreak = hits === 0 ? noHitStreak + 1 : 0;
      const failed = nextStreak >= competitionSimulationConfig.stage2.failIfNoHitRoundsAtLeast;
      setScore((value) => (failed ? 0 : value + delta));
      setNoHitStreak(nextStreak);
      setMissionStatus(failed ? 'Başarısız · 3 tur isabetsiz' : `Tur ${round} tamam · ${hits} imha · ${delta > 0 ? '+' : ''}${delta}`);
      addEvent('telemetry', failed ? 'STAGE_FAIL' : 'ROUND_SCORE', `Aşama 2 tur ${round}: ${hits} imha, ${delta} puan${forced ? ' · süre doldu' : ''}`);
    } else {
      const hostileDestroyed = resolution?.stage3HostileDestroyed ?? destroyedIds.some((id) => id.includes('-X'));
      const nextStreak = hostileDestroyed ? 0 : noHitStreak + 1;
      const failed = nextStreak >= competitionSimulationConfig.stage3.failIfConsecutiveHostileMisses;
      if (!hostileDestroyed) setScore((value) => (failed ? 0 : value + competitionSimulationConfig.stage3.maxRoundPenalty));
      setNoHitStreak(nextStreak);
      setMissionStatus(failed ? 'Başarısız · 3 ardışık düşman kaçtı' : hostileDestroyed ? `Tur ${round} tamam · düşman vuruldu` : `Tur ${round} ceza · -10`);
      addEvent('telemetry', failed ? 'STAGE_FAIL' : hostileDestroyed ? 'ROUND_CLEAR' : 'HOSTILE_MISSED_PENALTY', `Aşama 3 tur ${round}: ${hostileDestroyed ? 'düşman imha' : '-10 ceza'}`);
    }

    window.setTimeout(() => {
      if (round >= maxRound) {
        setMode('safe');
        setMissionStatus((previous) => `${previous} · Aşama bitti`);
        return;
      }
      setRound((value) => value + 1);
      setElapsed(0);
      setDestroyedIds([]);
      setRoundHits(0);
      setSelectedId(undefined);
      autoFireAt.current = -10;
      roundResolved.current = false;
    }, 700);
  };

  const handleFire = () => {
    if (stage !== 1) {
      addEvent('fire', 'AUTO_ONLY', 'Aşama 2/3 resmi modda manuel FIRE gerektirmez; otonom angajman görselleştirilir');
      return;
    }
    if (!selectedTrack) {
      addEvent('fire', 'FIRE_BLOCK', 'Seçili hedef yok');
      return;
    }
    if (fireSafety.blockReason !== 'ALLOWED') {
      addEvent('fire', 'FIRE_BLOCK', blockCopy[fireSafety.blockReason]);
      return;
    }
    const expected = TARGET_ORDER[currentTarget];
    if (selectedTrack.type !== expected) {
      setScore((value) => value + competitionSimulationConfig.stage1.wrongTargetPenalty);
      recordStrike(selectedTrack, 'penalty', '-5 yanlış');
      addEvent('fire', 'WRONG_TARGET_PENALTY', `${selectedTrack.type} seçildi; beklenen ${expected}; -5`);
      return;
    }
    const delta = stage1ScoreForRange(selectedTrack.range);
    const nextTarget = currentTarget + 1;
    const completed = nextTarget >= TARGET_ORDER.length;
    setScore((value) => {
      const baseScore = Math.min(competitionSimulationConfig.stage1.maxBaseScore, value + delta);
      if (!completed || baseScore < competitionSimulationConfig.stage1.maxBaseScore) return baseScore;
      return Math.round(baseScore + 20 * (timeLeft / competitionSimulationConfig.stage1.timeLimitSeconds));
    });
    setDestroyedIds((previous) => [...previous, selectedTrack.id]);
    setCurrentTarget(nextTarget);
    setMissionStatus(completed ? 'Aşama 1 tamam · zaman bonusu hesaplandı' : `Sıradaki hedef: ${TARGET_ORDER[nextTarget]}`);
    recordStrike(selectedTrack, 'hit', `+${delta}`);
    addEvent('fire', 'FIRE_HIT', `${selectedTrack.type} · ${selectedTrack.range.toFixed(1)} m · +${delta}`);
    if (completed) setMode('safe');
  };

  const handleMode = (nextMode: Mode) => {
    if (nextMode === 'manual' && stage !== 1) {
      addEvent('mode', 'MANUAL_PRACTICE_NOTE', 'Aşama 2/3 resmi akış otonomdur; manuel mod ana skora dahil edilmez');
    }
    setMode(nextMode);
    setPaused(nextMode === 'maintenance');
    if (nextMode === 'maintenance') setMaintenanceBudget((value) => Math.max(0, value - mechanicsConfig.maintenanceMinimumSeconds));
    setMissionStatus(nextMode === 'autonomous' && stage !== 1 ? 'Otonom takip aktif' : nextMode === 'manual' ? 'Manuel kontrol' : modeCopy[nextMode]);
    addEvent('mode', `MODE_${nextMode.toUpperCase()}`, `Mod ${modeCopy[nextMode]} olarak değişti`);
  };

  const toggleEstop = () => {
    setBaseSafety((previous) => ({ ...previous, estop: !previous.estop }));
    addEvent('safety', baseSafety.estop ? 'ESTOP_OFF' : 'ESTOP_ON', baseSafety.estop ? 'Hakem/operatör onayıyla devam' : 'Hareket, zaman ve atış donduruldu');
  };

  const nextTutorial = () => {
    if (tutorialIndex + 1 >= stageSteps.length) {
      setTutorialVisible(false);
      setTutorialIndex(0);
      addEvent('telemetry', 'TUTORIAL_DONE', 'Bağlamsal rehber tamamlandı');
      return;
    }
    setTutorialIndex((value) => value + 1);
  };

  useEffect(() => {
    const id = window.setInterval(() => {
      if (!hardPaused) setElapsed((value) => value + 0.25);
    }, 250);
    return () => window.clearInterval(id);
  }, [hardPaused]);

  useEffect(() => {
    roundResolved.current = false;
  }, [round, stage]);

  useEffect(() => {
    if (!selectedId && selectedTrack) setSelectedId(selectedTrack.id);
  }, [selectedId, selectedTrack]);

  useEffect(() => {
    if (stage === 1 && timeLeft <= 0 && mode !== 'safe') {
      setMode('safe');
      setMissionStatus('Aşama 1 süresi doldu');
      addEvent('mode', 'TIME_EXPIRED', 'Aşama 1 5 dakika süresi doldu');
    }
    if (stage !== 1 && elapsed >= roundDurationFor(stage)) finishRound(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [elapsed, stage, timeLeft]);

  useEffect(() => {
    if (stage === 1 || mode !== 'autonomous' || hardPaused || roundResolved.current) return;
    if (elapsed - autoFireAt.current < 1.25) return;
    if (stage === 2) {
      const candidate = tracks.find((track) => track.candidate && !destroyedIds.includes(track.id));
      if (!candidate) return;
      autoFireAt.current = elapsed;
      setDestroyedIds((previous) => [...previous, candidate.id]);
      setRoundHits((value) => value + 1);
      recordStrike(candidate, 'hit', 'AUTO');
      addEvent('fire', 'AUTO_ENGAGE', `${candidate.id} · Kol ${candidate.lane} · sınıflandırma gerekmez`);
      if (destroyedIds.length + 1 >= 3) window.setTimeout(() => finishRound(false, { stage2Hits: destroyedIds.length + 1 }), 150);
      return;
    }
    const enemy = tracks.find((track) => track.friendFoe === 'Düşman' && track.rangeGate === 'Uygun');
    if (!enemy || destroyedIds.includes(enemy.id)) return;
    autoFireAt.current = elapsed;
    setDestroyedIds((previous) => [...previous, enemy.id]);
    setRoundHits(1);
    const delta = stage3TargetScore(enemy.type);
    setScore((value) => value + delta);
    recordStrike(enemy, 'hit', `+${delta}`);
    addEvent('fire', 'AUTO_ENGAGE', `${enemy.type} düşman · ${enemy.range.toFixed(1)} m · +${delta}`);
    window.setTimeout(() => finishRound(false, { stage3HostileDestroyed: true }), 200);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [destroyedIds, elapsed, hardPaused, mode, stage, tracks]);

  const selectedExpected = stage === 1 ? TARGET_ORDER[currentTarget] : undefined;
  const fireWrongStage1 = stage === 1 && selectedTrack && selectedExpected && selectedTrack.type !== selectedExpected;
  const fireStatus = fireSafety.blockReason !== 'ALLOWED'
    ? 'Not Allowed'
    : stage === 1
      ? fireWrongStage1 ? 'Penalty if fired' : 'Allowed'
      : mode === 'autonomous' ? 'Autonomous' : 'Not Allowed';
  const blockedFireReason = fireSafety.blockReason === 'BLOCKED_TARGET_GATE' && stage === 3
    ? selectedTrack?.friendFoe === 'Dost'
      ? 'Fire blocked: friendly target protected'
      : selectedTrack
        ? 'Fire blocked: target outside valid range'
        : 'Fire blocked: no target selected'
    : `Fire blocked: ${blockCopy[fireSafety.blockReason]}`;
  const fireReason = fireSafety.blockReason !== 'ALLOWED'
    ? blockedFireReason
    : stage === 1
      ? fireWrongStage1
        ? `Fire penalty: wrong target selected; expected ${selectedExpected}`
        : selectedTrack ? `Fire ready: ${selectedTrack.type} at ${selectedTrack.range.toFixed(1)} m` : 'Fire blocked: no target selected'
      : mode !== 'autonomous'
        ? 'Fire blocked: switch to autonomous mode for this official stage'
        : stage === 2
          ? 'Autonomous engagement: system fires when a lane target is in the window'
          : selectedTrack?.friendFoe === 'Dost'
            ? 'Fire blocked: friendly target protected'
            : selectedTrack?.rangeGate === 'Uygun'
              ? `Autonomous ready: ${selectedTrack.type} enemy in valid window`
              : 'Autonomous waiting: target outside valid range';
  const scoreImpact = stage === 1
    ? fireWrongStage1
      ? '-5 ceza'
      : selectedTrack ? `+${stage1ScoreForRange(selectedTrack.range)} puan` : '0'
    : stage === 2
      ? `Tur sonucu: ${stage2RoundScore(Math.min(3, destroyedIds.length + 1))} puana kadar`
      : selectedTrack?.friendFoe === 'Düşman' && selectedTrack.rangeGate === 'Uygun'
        ? `+${stage3TargetScore(selectedTrack.type)} puan`
        : selectedTrack?.friendFoe === 'Dost' ? '-10 ceza riski' : '-10 tur cezası riski';
  const fireDisabled = stage !== 1 || !selectedTrack || fireSafety.blockReason !== 'ALLOWED';
  const timer = stage === 1 ? formatTime(timeLeft) : `${formatTime(timeLeft)} / tur`;
  const fireButtonText = stage === 1 ? 'FIRE' : 'OTONOM ATEŞ';

  return (
    <main className="sim-shell">
      <CompetitionHeader
        stage={stage}
        mode={mode}
        timer={timer}
        score={score}
        round={round}
        safetyState={systemHealth}
        simulatorMode={simulatorMode}
        onStage={switchStage}
        onSimulatorMode={setSimulatorMode}
      />
      <section className="sim-grid">
        <CourseMap
          stage={stage}
          tracks={tracks}
          selectedTrack={selectedTrack}
          destroyedIds={destroyedIds}
          strikes={strikes}
          tutorialHighlight={tutorialHighlight}
          onSelect={(id) => { setSelectedId(id); addEvent('target', 'TRACK_SELECT', id); }}
        />
        <GuidancePanel
          stage={stage}
          mode={mode}
          round={round}
          selectedTrack={selectedTrack}
          fireStatus={fireStatus}
          fireReason={fireReason}
          scoreImpact={scoreImpact}
          missionStatus={missionStatus}
          tutorialHighlight={tutorialHighlight}
          onRestartTutorial={() => { setTutorialVisible(true); setTutorialIndex(0); }}
        />
      </section>
      <BottomActionBar
        stage={stage}
        mode={mode}
        currentTarget={currentTarget}
        destroyedIds={destroyedIds}
        round={round}
        roundHits={roundHits}
        paused={paused || tutorialVisible}
        estop={baseSafety.estop}
        fireDisabled={fireDisabled}
        fireButtonText={fireButtonText}
        fireReason={fireReason}
        tutorialHighlight={tutorialHighlight}
        onFire={handleFire}
        onMode={handleMode}
        onPause={() => setPaused((value) => !value)}
        onReset={() => { resetStageState(stage); addEvent('telemetry', 'RESET_STAGE', `Aşama ${stage} sıfırlandı`); }}
        onEstop={toggleEstop}
      />
      <DebugDrawer baseSafety={baseSafety} fireSafety={fireSafety} events={events} selectedTrack={selectedTrack} elapsed={elapsed} maintenanceBudget={maintenanceBudget} />
      {tutorialStep && (
        <TutorialOverlay
          step={tutorialStep}
          index={Math.min(tutorialIndex, stageSteps.length - 1)}
          count={stageSteps.length}
          onNext={nextTutorial}
          onSkip={() => { setTutorialVisible(false); setTutorialIndex(0); addEvent('telemetry', 'TUTORIAL_SKIPPED', 'Bağlamsal rehber atlandı'); }}
        />
      )}
    </main>
  );
}

export default function App() {
  const [entered, setEntered] = useState(() => new URLSearchParams(window.location.search).has('console'));
  return entered ? <Console /> : <Landing onEnter={() => setEntered(true)} />;
}
