import { type CSSProperties, useEffect, useMemo, useRef, useState } from 'react';
import gokkalkanIconUrl from '../assets/gokkalkan_icon.png';
import { COMPETITION_COURSE, displayXForRangeBand } from './competitionCourse';
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
import OperatorPanel from './OperatorPanel';
import { exportJsonl, makeEvent } from './telemetry';
import type { EventType, Mode, SafetyState, Stage, TargetType, TelemetryEvent, Track } from './types';

const modeCopy: Record<Mode, string> = {
  safe: 'Beklemede',
  manual: 'Manuel',
  autonomous: 'Otonom',
  engagement: 'Angajman',
  blocked: 'Kilitli',
  maintenance: 'Bakım',
};

const targetCopy: Record<TargetType, string> = {
  F16: 'Savaş Uçağı / F16',
  Helikopter: 'Helikopter',
  'Balistik Füze': 'Balistik Füze',
  'Mini/Micro İHA': 'Mini/Micro İHA',
};

const targetShortCopy: Record<TargetType, string> = {
  F16: 'F16',
  Helikopter: 'Helikopter',
  'Balistik Füze': 'Balistik',
  'Mini/Micro İHA': 'İHA',
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
    message: 'Aşama 1’de 5/10/15 m durağan bantlar izlenir; Aşama 2/3’te hedefler A noktasından B bölgesine ilerler. Rehber açıkken süre ve puan duraklatılır.',
    highlight: 'map',
  },
  {
    id: 'global-range',
    stage: 'global',
    title: 'Menzil bantlarını izle',
    message: '15 m, 10 m ve 5 m çizgileri angajman aralıklarını gösterir. Yeşil/parlak bant seçili hedef için geçerli ateş penceresidir.',
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
    title: 'ATEŞ düğmesi yarışma aksiyonudur',
    message: 'Doğru hedef seçiliyken ATEŞ HAZIR düğmesine bas. Basmazsan hedef imha edilmez; süre işlemeye devam eder.',
    highlight: 'fire',
  },
  {
    id: 'stage2-auto',
    stage: 2,
    title: 'Aşama 2 otonom akıştır',
    message: 'Resmi akış 4 turdur; pratik modunda ek turlar eğitim içindir. Her turda üç hedef ölçekli poligon eğrilerinde ilerler ve sistem angajmanı otonom kurar.',
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

type FireActionState = 'ready' | 'blocked' | 'penalty' | 'autonomous';

function cx(...classes: Array<string | false | undefined>) {
  return classes.filter(Boolean).join(' ');
}

function formatTime(seconds: number) {
  const bounded = Math.max(0, Math.floor(seconds));
  return `${Math.floor(bounded / 60)}:${String(bounded % 60).padStart(2, '0')}`;
}

function stageModeExpectation(stage: Stage): Mode {
  return stage === 1 ? 'manual' : 'autonomous';
}

function xForRange(range: number) {
  return displayXForRangeBand(range);
}

const DOME_SOURCE_NOSE_SCREEN_DEG = 135;
const DOME_DEFAULT_LEFT_ROTATION_DEG = 45;

function normalizeRotationNear(targetAngle: number, previousAngle: number): number {
  let nextAngle = targetAngle;
  while (nextAngle - previousAngle > 180) nextAngle -= 360;
  while (nextAngle - previousAngle < -180) nextAngle += 360;
  return nextAngle;
}

function domeRotationForTrack(track?: Track): number {
  if (!track) return DOME_DEFAULT_LEFT_ROTATION_DEG;
  const targetAngle = (Math.atan2(track.y - COMPETITION_COURSE.systemPosition.y, track.x - COMPETITION_COURSE.systemPosition.x) * 180) / Math.PI;
  return targetAngle - DOME_SOURCE_NOSE_SCREEN_DEG;
}

function roundTotalFor(stage: Stage, simulatorMode: SimulatorMode): number {
  if (stage === 2 && simulatorMode === 'practice') return competitionSimulationConfig.stage2.practiceRounds;
  return COMPETITION_STAGE_ROUNDS[stage];
}

function rangeLabel(track?: Track) {
  if (!track) return 'Hedef seçilmedi';
  if (track.type === 'Mini/Micro İHA' && track.rangeGate === 'Uygun' && !track.candidate) {
    return `YAKIN MENZİL BEKLENİYOR (≤${competitionSimulationConfig.uavPreferredAutoEngagementMaxRangeMeters} m)`;
  }
  if (track.rangeGate === 'Uygun') return 'MENZİL UYGUN';
  if (track.rangeGate === 'Erken') return 'ÇOK ERKEN';
  return 'ÇOK YAKIN / MENZİL DIŞI';
}

function targetStatusLabel(track: Track, stage: Stage) {
  if (track.candidate) return 'UYGUN';
  if (stage === 1) return 'SIRA';
  if (track.friendFoe === 'Dost') return 'DOST KİLİT';
  if (track.type === 'Mini/Micro İHA' && track.rangeGate === 'Uygun') return `≤${competitionSimulationConfig.uavPreferredAutoEngagementMaxRangeMeters} m`;
  if (track.rangeGate === 'Uygun') return 'BEKLE';
  if (track.rangeGate === 'Erken') return 'ERKEN';
  return 'DIŞI';
}

function targetTypeFromText(text: string): TargetType | undefined {
  return TARGET_ORDER.find((target) => text.includes(target) || (target === 'F16' && text.includes('Savaş Uçağı')));
}

function TargetSilhouette({ type, className = '' }: { type: TargetType; className?: string }) {
  return (
    <svg className={`target-silhouette ${className}`} viewBox="0 0 64 64" aria-hidden="true">
      {type === 'Balistik Füze' && (
        <g>
          <path d="M32 5 C26 13 24 19 24 31 L24 47 L40 47 L40 31 C40 19 38 13 32 5 Z" />
          <path d="M24 42 L12 55 L24 52 Z M40 42 L52 55 L40 52 Z" />
          <path d="M29 47 L25 61 L32 56 L39 61 L35 47 Z" />
          <circle cx="32" cy="25" r="4" />
        </g>
      )}
      {type === 'Helikopter' && (
        <g>
          <path d="M16 33 C20 24 42 24 49 33 C44 43 23 44 16 33 Z" />
          <path d="M44 32 L59 25 L61 29 L49 38 Z" />
          <path d="M24 41 L20 51 L28 51 L31 43 Z M39 41 L43 51 L51 51 L47 41 Z" />
          <path d="M13 20 H51 M29 14 H35 V26 H29 Z" />
          <path d="M8 18 L21 22 M56 18 L43 22" />
        </g>
      )}
      {type === 'F16' && (
        <g>
          <path d="M3 32 L25 25 L43 11 L53 15 L43 29 L62 32 L43 35 L53 49 L43 53 L25 39 Z" />
          <path d="M23 25 L14 15 L30 23 Z M23 39 L14 49 L30 41 Z" />
          <path d="M36 28 L45 24 L43 32 L45 40 L36 36 Z" />
          <circle cx="47" cy="32" r="2.2" />
        </g>
      )}
      {type === 'Mini/Micro İHA' && (
        <g>
          <circle cx="32" cy="32" r="8" />
          <path d="M24 24 L12 12 M40 24 L52 12 M24 40 L12 52 M40 40 L52 52" />
          <circle cx="11" cy="11" r="7" />
          <circle cx="53" cy="11" r="7" />
          <circle cx="11" cy="53" r="7" />
          <circle cx="53" cy="53" r="7" />
          <path d="M26 32 H38 M32 26 V38" />
        </g>
      )}
    </svg>
  );
}

function CourseMap({
  stage,
  tracks,
  selectedTrack,
  destroyedIds,
  strikes,
  tutorialHighlight,
  onSelect,
  aimTrack,
}: {
  stage: Stage;
  tracks: Track[];
  selectedTrack?: Track;
  aimTrack?: Track;
  destroyedIds: string[];
  strikes: StrikeEffect[];
  tutorialHighlight?: string;
  onSelect: (id: string) => void;
}) {
  const points = (items: Array<{ x: number; y: number }>) => items.map((point) => `${point.x},${point.y}`).join(' ');
  const rule = selectedTrack && stage !== 1
    ? selectedTrack.type === 'Mini/Micro İHA'
      ? { min: 0, max: competitionSimulationConfig.uavPreferredAutoEngagementMaxRangeMeters }
      : rangeRuleFor(selectedTrack.type)
    : undefined;
  const selectedBand = selectedTrack && stage === 1 ? selectedTrack.range : undefined;
  const validStart = rule ? Math.min(xForRange(rule.max), xForRange(rule.min)) : selectedBand ? xForRange(selectedBand) - 6 : xForRange(15);
  const validWidth = rule ? Math.abs(xForRange(rule.min) - xForRange(rule.max)) : selectedBand ? 12 : Math.abs(xForRange(0) - xForRange(15));
  const activeWindow = Boolean(selectedTrack?.candidate);
  const windowLabelText = activeWindow
    ? 'MENZİL UYGUN'
    : selectedTrack?.type === 'Mini/Micro İHA' && selectedTrack.rangeGate === 'Uygun'
      ? `≤${competitionSimulationConfig.uavPreferredAutoEngagementMaxRangeMeters} m BEKLE`
      : rangeLabel(selectedTrack);
  const windowLabelX = Math.min(84, Math.max(16, validStart + validWidth / 2));
  const previousDomeRotation = useRef(DOME_DEFAULT_LEFT_ROTATION_DEG);
  const domeAngle = normalizeRotationNear(domeRotationForTrack(aimTrack), previousDomeRotation.current);
  previousDomeRotation.current = domeAngle;
  const domeStyle = {
    left: `${COMPETITION_COURSE.systemPosition.x}%`,
    top: `${COMPETITION_COURSE.systemPosition.y}%`,
    '--dome-rotation': `${domeAngle}deg`,
  } as CSSProperties;

  return (
    <section
      className={cx(
        `parkour-hero stage-${stage}`,
        'relative min-h-[500px] overflow-hidden rounded-lg border border-[rgba(174,225,255,.18)] bg-[#0b1117] shadow-[inset_0_0_54px_rgba(0,0,0,.56)]',
        'max-[760px]:min-h-[430px]',
        (tutorialHighlight === 'map' || tutorialHighlight === 'ranges') && 'tutorial-pulse',
      )}
      data-testid="parkour-hero"
    >
      <svg className="parkour-overlay" viewBox="0 0 100 100" aria-label={`Aşama ${stage} parkur şeması`}>
        <defs>
          <pattern id={`grid-${stage}`} width="5" height="5" patternUnits="userSpaceOnUse">
            <path d="M 5 0 L 0 0 0 5" fill="none" stroke="rgba(174,225,255,.10)" strokeWidth=".25" />
          </pattern>
          <marker id={`arrow-${stage}`} markerWidth="5" markerHeight="5" refX="4.2" refY="2.5" orient="auto">
            <path d="M0,0 L5,2.5 L0,5 Z" fill="#ffbb42" opacity=".78" />
          </marker>
        </defs>
        <rect className="schematic-grid" x="3" y="6" width="94" height="88" rx="4" fill={`url(#grid-${stage})`} />

        {stage === 1 ? (
          <g className="stage1-practice-field">
            {[15, 10, 5].map((range) => (
              <g key={range} className={`stage1-zone zone-${range} ${selectedBand === range ? 'active' : ''}`} data-testid={`range-${range}m`}>
                <rect x={range === 15 ? 9 : range === 10 ? 36 : 63} y="15" width="25" height="66" rx="4" />
                <text x={range === 15 ? 21.5 : range === 10 ? 48.5 : 75.5} y="22">{range} m</text>
                <text x={range === 15 ? 21.5 : range === 10 ? 48.5 : 75.5} y="76">DURAĞAN</text>
              </g>
            ))}
            <text className="stage1-title" x="9" y="10">A1 · MANUEL ATIŞ</text>
          </g>
        ) : (
          <g className="moving-course-field">
            {selectedTrack && (
              <>
                <rect className={`valid-window ${activeWindow ? 'active' : ''}`} x={validStart} y="15" width={validWidth} height="77" />
                <text className={`window-label ${activeWindow ? 'active' : ''}`} x={windowLabelX} y="18.2" textAnchor="middle">
                  {windowLabelText}
                </text>
              </>
            )}
            {[15, 10, 5].map((range) => (
              <g key={range} className={`range-line ${selectedTrack?.candidate && Math.abs(selectedTrack.range - range) <= 2.5 ? 'active' : ''}`} data-testid={`range-${range}m`}>
                <line x1={xForRange(range)} y1="10" x2={xForRange(range)} y2="93" />
                <text x={xForRange(range) + 0.7} y="12">{range} m</text>
              </g>
            ))}
            <text className="point-label" x="7" y="8">POLİGON GİRİŞİ</text>
            <text className="escape-label" x="69" y="96">POLİGON ÇIKIŞI</text>
            {COMPETITION_COURSE.lanes.map((lane) => (
              <g key={lane.lane} className={`lane-path lane-${lane.lane}`}>
                <polyline points={points(lane.points)} markerEnd={`url(#arrow-${stage})`} />
                <text x="8" y={lane.points[0].y - 2}>ROTA {lane.lane}</text>
                {lane.points.slice(1, -1).map((point, index) => (
                  <text key={`${lane.lane}-${index}`} className={`lane-arrow arrow-${index}`} x={point.x} y={point.y - 2}>➜</text>
                ))}
              </g>
            ))}
          </g>
        )}

        <g className="system-anchor">
          <circle cx={COMPETITION_COURSE.systemPosition.x} cy={COMPETITION_COURSE.systemPosition.y} r="1.4" />
          <text x={COMPETITION_COURSE.systemPosition.x - 8} y={COMPETITION_COURSE.systemPosition.y + 9}>Gökkalkan</text>
        </g>
        {selectedTrack && stage === 1 && (
          <g className="target-link">
            <line x1={selectedTrack.x} y1={selectedTrack.y} x2={COMPETITION_COURSE.systemPosition.x} y2={COMPETITION_COURSE.systemPosition.y} />
            <text x="56" y="61">Seçili → Ateş</text>
          </g>
        )}
        {strikes.map((strike) => (
          <g key={strike.id} className={`strike ${strike.result}`}>
            <line className="shot-trail" x1={COMPETITION_COURSE.systemPosition.x} y1={COMPETITION_COURSE.systemPosition.y} x2={strike.x} y2={strike.y} />
            <circle className="shot-bullet" cx={COMPETITION_COURSE.systemPosition.x} cy={COMPETITION_COURSE.systemPosition.y} r="1.05">
              <animate attributeName="cx" from={COMPETITION_COURSE.systemPosition.x} to={strike.x} dur="0.26s" fill="freeze" />
              <animate attributeName="cy" from={COMPETITION_COURSE.systemPosition.y} to={strike.y} dur="0.26s" fill="freeze" />
            </circle>
            <circle className="impact-ring" cx={strike.x} cy={strike.y} r="2.8" />
            <text x={Math.min(88, strike.x + 2)} y={Math.max(9, strike.y - 2)}>{strike.label}</text>
          </g>
        ))}
      </svg>

      <div
        className="steel-dome pointer-events-none absolute z-[5] grid h-[76px] w-[76px] -translate-x-1/2 -translate-y-1/2 place-items-center [filter:drop-shadow(0_0_20px_rgba(51,230,140,.26))_drop-shadow(0_12px_24px_rgba(0,0,0,.5))]"
        style={domeStyle}
        data-testid="steel-dome"
        data-rotation={domeAngle.toFixed(1)}
        aria-hidden="true"
      >
        <img className="h-[68px] w-[68px] rounded-full object-contain opacity-90 will-change-transform [transform:rotate(var(--dome-rotation))]" src={gokkalkanIconUrl} alt="" />
      </div>

      {tracks.map((track) => {
        const selected = selectedTrack?.id === track.id;
        const destroyed = destroyedIds.includes(track.id);
        const affiliationClass = stage < 3
          ? 'enemy'
          : track.friendFoe === 'Düşman'
            ? 'enemy'
            : track.friendFoe === 'Dost'
              ? 'friend'
              : 'neutral';
        return (
          <button
            key={track.id}
            className={cx(
              'aircraft absolute z-[6] grid min-h-24 min-w-[78px] -translate-x-1/2 -translate-y-1/2 content-center place-items-center gap-[3px] rounded-full border-0 bg-transparent p-0.5 text-center text-[#ffd17a] shadow-none transition-[color,filter,transform] duration-150 will-change-[left,top]',
              affiliationClass,
              stage !== 1 ? 'moving' : 'stationary',
              selected && 'selected',
              track.candidate && 'candidate',
              destroyed && 'destroyed',
            )}
            style={{ left: `${track.x}%`, top: `${track.y}%`, width: `${track.w}%`, height: `${track.h}%` }}
            data-testid={`track-${track.id}`}
            aria-label={`${track.id} ${targetCopy[track.type]} ${track.friendFoe} ${track.range.toFixed(1)} metre`}
            onClick={() => onSelect(track.id)}
          >
            <span className="motion-trail" />
            <span className="target-visual"><TargetSilhouette type={track.type} /></span>
            <span className="target-label-stack">
              <span className="target-name">{stage === 2 ? `Rota ${track.lane}` : track.friendFoe}</span>
              <small>{targetShortCopy[track.type]}</small>
              <em className={`range-chip ${track.rangeGate.toLowerCase()}`} title={rangeLabel(track)}>{targetStatusLabel(track, stage)}</em>
            </span>
          </button>
        );
      })}

      <div className="map-legend absolute bottom-3 left-3.5 z-[8] flex flex-wrap gap-1.5 rounded-lg border border-white/10 bg-[rgba(2,4,7,.76)] px-2 py-1.5 backdrop-blur">
        {stage < 3
          ? <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="enemy-dot" />Kırmızı hedef</span>
          : <>
              <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="enemy-dot" />Kırmızı · Düşman</span>
              <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="friend-dot" />Mavi · Dost</span>
            </>}
        <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="window-dot" />Menzil uygun</span>
      </div>
      <div className="map-assumption absolute right-3.5 bottom-3 z-[8] max-w-[min(460px,48%)] rounded-lg border border-[rgba(255,187,66,.24)] bg-[rgba(255,187,66,.10)] px-2 py-1.5 text-[10px] leading-tight text-[#ffbb42] max-[760px]:right-3 max-[760px]:bottom-[62px] max-[760px]:left-3 max-[760px]:max-w-none">
        {competitionSimulationConfig.assumptionNotice}
      </div>
    </section>
  );
}

function CompetitionHeader({
  stage,
  mode,
  timer,
  score,
  round,
  roundTotal,
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
  roundTotal: number;
  safetyState: SafetyState;
  simulatorMode: SimulatorMode;
  onStage: (stage: Stage) => void;
  onSimulatorMode: (mode: SimulatorMode) => void;
}) {
  const safetyOk = safetyState.blockReason === 'ALLOWED';
  const metricClass = 'grid min-w-0 place-items-center overflow-hidden rounded-md bg-white/[.035] text-center text-[11px] leading-tight text-[#91a6b7]';
  const metricValueClass = 'mt-0.5 block max-w-full overflow-hidden text-ellipsis whitespace-nowrap text-[13px] text-[#edf8ff]';
  const chromeClass = 'rounded-lg border border-[rgba(174,225,255,.13)] bg-[rgba(9,13,17,.96)]';
  return (
    <header className="competition-header mb-2 grid min-h-14 items-stretch gap-2 [grid-template-columns:1fr_auto] min-[1051px]:max-[1320px]:[grid-template-columns:minmax(240px,1fr)_auto_112px] min-[1321px]:[grid-template-columns:minmax(190px,.72fr)_auto_minmax(390px,1.3fr)_112px]">
      <div className={`app-title flex min-w-0 items-center gap-2.5 px-3 ${chromeClass}`}>
        <span className="grid h-[30px] w-[30px] place-items-center rounded-md bg-[#25d8ff]/10 text-[#25d8ff]">⬢</span>
        <div className="min-w-0">
          <b className="block text-base font-black tracking-[.09em]">GÖKKALKAN</b>
          <small className="block overflow-hidden text-ellipsis whitespace-nowrap text-[11px] text-[#91a6b7]">Çelikkubbe yarışma konsolu</small>
        </div>
      </div>
      <nav className={`stage-switch flex gap-1.5 overflow-x-auto p-1.5 ${chromeClass}`} aria-label="Aşama seçimi">
        {([1, 2, 3] as const).map((item) => (
          <button
            key={item}
            className={cx(
              'min-w-[82px] rounded-md px-2.5 text-[13px] font-black text-[#91a6b7]',
              stage === item && 'border border-[#25d8ff]/40 bg-[#25d8ff]/15 text-[#25d8ff]',
            )}
            onClick={() => onStage(item)}
          >
            Aşama {item}
          </button>
        ))}
      </nav>
      <div className={`header-metrics col-span-full grid grid-cols-5 gap-1.5 p-1.5 max-[760px]:grid-cols-1 min-[1321px]:col-auto ${chromeClass}`}>
        <span className={metricClass}>Mod <b className={metricValueClass}>{modeCopy[mode]}</b></span>
        <span className={metricClass}>Süre <b className={metricValueClass}>{timer}</b></span>
        <span className={metricClass}>Puan <b className={metricValueClass}>{score}</b></span>
        <span className={metricClass}>Tur <b className={metricValueClass}>{round}/{roundTotal}</b></span>
        <span className={metricClass}>Güvenlik <b className={cx(metricValueClass, safetyOk ? 'text-[#33e68c]' : 'text-[#ff4757]')}>{safetyOk ? 'Hazır' : blockCopy[safetyState.blockReason]}</b></span>
      </div>
      <button
        className={cx(
          `sim-mode ${simulatorMode}`,
          chromeClass,
          'col-span-full min-h-[42px] text-[13px] font-black',
          'min-[1051px]:max-[1320px]:col-start-3 min-[1051px]:max-[1320px]:row-start-1 min-[1321px]:col-auto',
          simulatorMode === 'strict' ? 'bg-[#33e68c]/10 text-[#33e68c]' : 'bg-[#ffbb42]/10 text-[#ffbb42]',
        )}
        title={simulatorMode === 'strict' ? 'Sıkı yarışma modu' : 'Pratik modu'}
        onClick={() => onSimulatorMode(simulatorMode === 'strict' ? 'practice' : 'strict')}
      >
        {simulatorMode === 'strict' ? 'Sıkı' : 'Pratik'}
      </button>
    </header>
  );
}

function GuidancePanel({
  stage,
  mode,
  round,
  roundTotal,
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
  roundTotal: number;
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
    ? 'Zarf sırasıyla manuel imha.'
    : stage === 2
      ? 'Üç kolu B’ye varmadan temizle.'
      : 'Dostları koru, düşmanı menzilde vur.';
  const nextAction = stage === 1
    ? mode === 'manual' ? 'Beklenen hedefi seç, ateş kararını ver.' : 'Manuel moda geç.'
    : mode === 'autonomous' ? 'Otonom akışı izle; menzil penceresi angajmanı açar.' : 'Otonom modu başlat.';
  const ruleReminder = stage === 1
    ? 'A1: yakın +5, orta +10, uzun +20; yanlış sıra -5; süre bonusu.'
    : stage === 2
      ? 'A2: 4 tur, 3 kol, sınıflandırma beklenmez; kaçan hedef -5.'
      : 'A3: F16 10–15 m +30; Helikopter/Balistik 5–15 m +20; İHA 0–15 m +10.';
  const sectionClass = 'min-w-0 rounded-lg border border-white/[.07] bg-white/[.035] px-2.5 py-2';
  const labelClass = 'mb-1 block text-[10px] font-black uppercase tracking-[.05em] text-[#91a6b7]';
  const textClass = 'm-0 text-xs leading-snug text-[#e8f6ff] [overflow-wrap:anywhere]';

  return (
    <aside
      className={cx(
        'guidance-panel grid content-start gap-2 rounded-lg border border-[rgba(174,225,255,.18)] bg-[rgba(9,13,17,.96)] p-2.5 max-[1320px]:grid-cols-3 max-[760px]:grid-cols-1',
        tutorialHighlight === 'guidance' && 'tutorial-pulse',
      )}
      data-testid="competition-guidance"
    >
      <div className="panel-kicker text-[10px] font-black uppercase tracking-[.08em] text-[#33e68c] max-[1320px]:col-span-full min-[1051px]:max-[1320px]:col-auto">Görev Paneli</div>
      <h2 className="m-0 text-lg font-black leading-tight max-[1320px]:col-span-full min-[1051px]:max-[1320px]:col-auto">{stageConfig.title}</h2>
      <section className={sectionClass}>
        <span className={labelClass}>Odak</span>
        <p className={textClass}>{objective}</p>
        <p className={`${textClass} mt-1 text-[#91a6b7]`}>{nextAction}</p>
      </section>
      <section className={`${sectionClass} border-[#ff4757]/25 bg-[#ff4757]/10`}>
        <span className={labelClass}>Ateş</span>
        <b className="mb-1 block text-base text-white">{fireStatus}</b>
        <p className={textClass}>{fireReason}</p>
        <p className={`${textClass} mt-1 font-black text-[#ffbb42]`}>{scoreImpact}</p>
      </section>
      <section className={sectionClass}>
        <span className={labelClass}>Seçili</span>
        {selectedTrack ? (
          <div className="target-detail-row grid grid-cols-[32px_minmax(0,1fr)] items-center gap-2">
            <TargetSilhouette className="detail-icon" type={selectedTrack.type} />
            <div>
              <p className={textClass}><b className="text-white">{selectedTrack.id}</b> · {targetCopy[selectedTrack.type]}</p>
              <p className={`${textClass} mt-1 text-[#91a6b7]`}>{selectedTrack.friendFoe} · {selectedTrack.range.toFixed(1)} m · {rangeLabel(selectedTrack)}</p>
            </div>
          </div>
        ) : <p className={textClass}>Seçili hedef yok</p>}
      </section>
      <section className={sectionClass}>
        <span className={labelClass}>Kural</span>
        <p className={textClass}>{ruleReminder}</p>
      </section>
      <section className={sectionClass}>
        <span className={labelClass}>Tur</span>
        <p className={textClass}>{round}/{roundTotal} · {missionStatus}</p>
      </section>
      <button className="restart-tutorial min-h-8 rounded-lg border border-[#25d8ff]/30 bg-[#25d8ff]/10 text-xs font-black text-[#25d8ff] max-[1320px]:col-span-full min-[1051px]:max-[1320px]:col-auto" onClick={onRestartTutorial}>Rehber</button>
    </aside>
  );
}

function StageChecklist({ stage, currentTarget, destroyedIds, round, roundHits, roundTotal }: { stage: Stage; currentTarget: number; destroyedIds: string[]; round: number; roundHits: number; roundTotal: number }) {
  const itemClass = 'grid min-h-[50px] min-w-0 place-items-center rounded-md bg-white/[.04] p-1.5 text-center text-[11px] font-black leading-tight text-[#91a6b7] [overflow-wrap:anywhere]';
  if (stage === 1) {
    return (
      <div className="stage-checklist grid grid-cols-4 gap-1.5 rounded-lg border border-[rgba(174,225,255,.13)] bg-[rgba(9,13,17,.96)] p-2 max-[760px]:grid-cols-1" data-testid="stage-1-order">
        {TARGET_ORDER.map((target, index) => (
          <span
            key={target}
            className={cx(
              itemClass,
              index < currentTarget && 'border border-[#33e68c]/30 bg-[#33e68c]/10 text-[#33e68c]',
              index === currentTarget && 'border border-[#ffbb42]/40 bg-[#ffbb42]/10 text-[#ffbb42]',
            )}
          >
            <TargetSilhouette className="check-icon" type={target} />
            <b className="block text-[10px] leading-none">{targetShortCopy[target]}</b>
          </span>
        ))}
      </div>
    );
  }
  return (
    <div className="stage-checklist compact grid grid-cols-8 gap-1.5 rounded-lg border border-[rgba(174,225,255,.13)] bg-[rgba(9,13,17,.96)] p-2 max-[760px]:grid-cols-1">
      {Array.from({ length: roundTotal }, (_, index) => index + 1).map((item) => (
        <span
          key={item}
          className={cx(
            itemClass,
            'min-h-[42px] text-[10px]',
            item < round && 'border border-[#33e68c]/30 bg-[#33e68c]/10 text-[#33e68c]',
            item === round && 'border border-[#ffbb42]/40 bg-[#ffbb42]/10 text-[#ffbb42]',
          )}
        >
          Tur {item}{item === round ? ` · ${roundHits || destroyedIds.length} imha` : ''}
        </span>
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
  roundTotal,
  roundHits,
  paused,
  estop,
  fireDisabled,
  fireButtonText,
  fireReason,
  scoreImpact,
  fireActionState,
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
  roundTotal: number;
  roundHits: number;
  paused: boolean;
  estop: boolean;
  fireDisabled: boolean;
  fireButtonText: string;
  fireReason: string;
  scoreImpact: string;
  fireActionState: FireActionState;
  tutorialHighlight?: string;
  onFire: () => void;
  onMode: (mode: Mode) => void;
  onPause: () => void;
  onReset: () => void;
  onEstop: () => void;
}) {
  const controlButtonClass = (active = false, danger = false) => cx(
    'min-w-0 rounded-md border border-white/[.08] bg-white/[.055] text-xs font-black text-[#dcecf5] [overflow-wrap:anywhere]',
    active && 'border-[#25d8ff]/30 bg-[#25d8ff]/15 text-[#25d8ff]',
    danger && 'border-[#ff4757]/30 bg-[#ff4757]/10 text-[#ffb3ba]',
    danger && active && 'bg-[#ff4757] text-white',
  );
  const fireClusterTone: Record<FireActionState, string> = {
    ready: 'border-[#ff4757]/60 bg-[#ff4757]/10 shadow-[0_0_34px_rgba(255,71,87,.12)]',
    blocked: 'border-white/10 bg-[rgba(4,6,9,.95)]',
    penalty: 'border-[#ffbb42]/50 bg-[#ffbb42]/10',
    autonomous: 'border-[#48a8ff]/30 bg-[#48a8ff]/10',
  };
  const fireButtonTone: Record<FireActionState, string> = {
    ready: 'fire-ready-pulse bg-linear-to-b from-[#ff3146] to-[#b90819] text-white shadow-[0_14px_34px_rgba(255,71,87,.18),inset_0_0_18px_rgba(255,255,255,.07)]',
    blocked: 'bg-linear-to-b from-[#1a2028] to-[#090c11] text-[#8fa0ad] shadow-[inset_0_0_18px_rgba(255,255,255,.04)]',
    penalty: 'bg-linear-to-b from-[#ffc04f] to-[#8f5500] text-[#150c00]',
    autonomous: 'bg-linear-to-b from-[#2269ae] to-[#123452] text-[#d9f0ff] shadow-[inset_0_0_18px_rgba(255,255,255,.08)]',
  };
  return (
    <section className="bottom-action-bar mt-2 grid grid-cols-1 items-stretch gap-2 min-[1321px]:[grid-template-columns:minmax(0,1fr)_minmax(330px,.72fr)_minmax(280px,360px)]" data-testid="bottom-action-bar">
      <StageChecklist stage={stage} currentTarget={currentTarget} destroyedIds={destroyedIds} round={round} roundHits={roundHits} roundTotal={roundTotal} />
      <div className="main-controls grid grid-cols-5 gap-1.5 rounded-lg border border-[rgba(174,225,255,.13)] bg-[rgba(9,13,17,.96)] p-2 max-[760px]:grid-cols-1">
        <button className={controlButtonClass(mode === 'manual')} onClick={() => onMode('manual')}>Manuel</button>
        <button className={controlButtonClass(mode === 'autonomous')} onClick={() => onMode('autonomous')}>Otonom</button>
        <button className={controlButtonClass()} onClick={onPause}>{paused ? 'Devam' : 'Duraklat'}</button>
        <button className={controlButtonClass(estop, true)} onClick={onEstop}>Acil Durdur</button>
        <button className={controlButtonClass()} onClick={onReset}>Sıfırla</button>
      </div>
      <div
        className={cx(
          `fire-cluster ${fireActionState}`,
          'grid content-center gap-1.5 rounded-lg border p-2',
          fireClusterTone[fireActionState],
          tutorialHighlight === 'fire' && 'tutorial-pulse',
        )}
        data-testid="fire-cluster"
      >
        <button
          className={cx(
            `primary-fire ${fireActionState}`,
            'min-h-[54px] rounded-lg border border-white/20 text-[clamp(17px,1.35vw,22px)] font-black tracking-normal transition-transform enabled:hover:-translate-y-0.5',
            fireButtonTone[fireActionState],
          )}
          disabled={fireDisabled}
          onClick={onFire}
        >
          {fireButtonText}
        </button>
        <small className={cx('text-center text-[11px] font-extrabold leading-tight [overflow-wrap:anywhere]', fireActionState === 'blocked' ? 'text-[#ffbdc4]' : fireActionState === 'autonomous' ? 'text-[#cdeaff]' : 'text-[#ffe0a4]')}>{fireReason}</small>
        <strong className="block text-center text-xs leading-tight text-white [overflow-wrap:anywhere]">{scoreImpact}</strong>
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
    <details className="debug-drawer mt-2 overflow-hidden rounded-lg border border-[rgba(174,225,255,.13)] bg-[rgba(9,13,17,.96)]">
      <summary className="cursor-pointer px-3 py-2.5 text-xs font-black text-[#91a6b7]">Telemetri / Debug</summary>
      <div className="debug-grid grid grid-cols-1 gap-2 px-2.5 pb-2.5 min-[1321px]:grid-cols-[1fr_1fr_1.1fr]">
        <section className="min-w-0 rounded-lg border border-white/[.07] bg-white/[.035] p-2.5">
          <b className="mb-2 block text-[#25d8ff]">Güvenlik kapısı</b>
          <code className="block max-h-[200px] overflow-auto whitespace-pre-wrap text-[11px] text-[#d2e8f4]">{JSON.stringify({ ...baseSafety, command: fireSafety.blockReason }, null, 2)}</code>
        </section>
        <section className="min-w-0 rounded-lg border border-white/[.07] bg-white/[.035] p-2.5">
          <b className="mb-2 block text-[#25d8ff]">Simülasyon ayarı</b>
          <code className="block max-h-[200px] overflow-auto whitespace-pre-wrap text-[11px] text-[#d2e8f4]">{JSON.stringify({ elapsed: Number(elapsed.toFixed(1)), maintenanceBudget, speed: { stage2: competitionSimulationConfig.stage2.targetSpeedMps, stage3: competitionSimulationConfig.stage3.targetSpeedMps }, selectedTrack }, null, 2)}</code>
        </section>
        <section className="event-debug min-w-0 rounded-lg border border-white/[.07] bg-white/[.035] p-2.5">
          <b className="mb-2 block text-[#25d8ff]">Olay kaydı</b>
          {visibleEvents.map((event) => {
            const targetType = targetTypeFromText(`${event.decision} ${event.reason}`);
            return (
              <p className="mb-1.5 text-xs text-[#dcecf5]" key={event.id}>
                {targetType && <TargetSilhouette type={targetType} />}
                <span className="text-[#91a6b7]">{event.timestamp}</span> A{event.stage} {event.decision} · {event.reason}
              </p>
            );
          })}
          <button className="min-h-8 rounded-lg border border-[#25d8ff]/30 bg-[#25d8ff]/10 px-2.5 font-black text-[#25d8ff]" onClick={() => exportJsonl(events)}>JSONL dışa aktar</button>
        </section>
      </div>
    </details>
  );
}

function TutorialOverlay({ step, index, count, onNext, onSkip }: { step: (typeof tutorialSteps)[number]; index: number; count: number; onNext: () => void; onSkip: () => void }) {
  return (
    <div className="tutorial-overlay pointer-events-none fixed inset-0 z-40 bg-black/75 backdrop-blur-[2px]" role="dialog" aria-modal="true" data-testid="tutorial-overlay">
      <div className="tutorial-card pointer-events-auto absolute bottom-6 left-1/2 w-[min(640px,calc(100vw-24px))] -translate-x-1/2 rounded-lg border border-[#ffbb42]/55 bg-[#070b10] p-4 shadow-[0_24px_80px_rgba(0,0,0,.72),0_0_0_1px_rgba(255,187,66,.12)] min-[900px]:p-5">
        <span className="text-[10px] font-black uppercase tracking-[.08em] text-[#ffbb42] min-[640px]:text-[11px]">Rehber {index + 1}/{count} · simülasyon duraklatıldı</span>
        <h2 className="my-2 text-2xl font-black leading-tight text-[#edf8ff] min-[640px]:text-3xl">{step.title}</h2>
        <p className="max-w-[62ch] text-base leading-relaxed text-[#dfeef7] min-[640px]:text-lg">{step.message}</p>
        <div className="tutorial-actions mt-4 grid gap-2 min-[640px]:flex min-[640px]:justify-end">
          <button className="min-h-11 rounded-lg border border-white/10 bg-white/[.09] px-4 text-sm font-black text-[#edf8ff] min-[640px]:text-base" onClick={onSkip}>Bu aşamada rehberi atla</button>
          <button className="continue min-h-11 rounded-lg bg-[#fff3c8] px-4 text-sm font-black text-[#071016] min-[640px]:text-base" onClick={onNext}>{index + 1 === count ? 'Bitir ve devam et' : 'Devam'}</button>
        </div>
      </div>
    </div>
  );
}

function Landing({ onEnter, onOperatorPanel }: { onEnter: () => void; onOperatorPanel: () => void }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setProgress((value) => Math.min(100, value + 5)), 120);
    return () => window.clearInterval(id);
  }, []);

  return (
    <main className="landing relative grid min-h-screen place-items-center overflow-hidden bg-[#05070a]">
      <div className="landing-grid pointer-events-none absolute inset-0" />
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
        <g className="radar"><circle cx="600" cy="620" r="140" /><circle cx="600" cy="620" r="260" /></g>
        {[0, 1, 2, 3].map((item) => <g key={item} className={`incoming incoming-${item}`}><path d="M0 0 l34 8 l-34 8 l8 -8 z" /><line x1="-74" y1="8" x2="-16" y2="8" /></g>)}
      </svg>
      <section className="boot-card relative z-[2] w-[min(720px,calc(100vw-36px))] rounded-xl border border-[#25d8ff]/25 bg-[rgba(7,10,14,.92)] p-[clamp(24px,4vw,44px)] text-center shadow-[0_24px_70px_rgba(0,0,0,.38)] backdrop-blur">
        <h1 className="signal m-0 overflow-hidden whitespace-nowrap text-[clamp(42px,6.4vw,72px)] font-black leading-none tracking-[clamp(.06em,.9vw,.16em)] [text-shadow:0_0_28px_rgba(37,216,255,.58)] max-[760px]:text-[clamp(38px,13vw,58px)] max-[760px]:tracking-[.08em]">GÖKKALKAN</h1>
        <div className="boot-sub my-3 mb-7 text-xs uppercase tracking-[.16em] text-[#c5d8e4]">Çelikkubbe yarışma konsolu</div>
        <div className="boot-checks grid grid-cols-5 gap-2 max-[760px]:grid-cols-1">
          {['Parkur', 'Aşama Kuralları', 'Menzil Kapısı', 'Dost/Düşman', 'Puanlama'].map((check, index) => (
            <span
              key={check}
              className={cx(
                'min-w-0 overflow-hidden text-ellipsis whitespace-nowrap rounded-full border border-white/[.07] bg-[rgba(12,18,24,.88)] px-2 py-2.5 text-[#91a6b7]',
                progress > index * 18 && 'border-[#33e68c]/30 text-[#edf8ff]',
              )}
            >
              <i className={cx('mr-2 inline-block h-2 w-2 rounded-full bg-[#354553]', progress > index * 18 && 'bg-[#33e68c] shadow-[0_0_12px_#33e68c]')} />
              {check}
            </span>
          ))}
        </div>
        <div className="boot-progress my-6 h-1 overflow-hidden rounded-full bg-white/10"><span className="block h-full bg-linear-to-r from-[#25d8ff] to-[#33e68c] transition-[width]" style={{ width: `${progress}%` }} /></div>
        <div className="grid gap-2 justify-items-center">
          <button className="enter-console rounded-lg bg-[#e5fbff] px-6 py-3 text-[#001319] shadow-[0_12px_28px_rgba(37,216,255,.18)] font-black" onClick={onEnter}>Simülatöre Başla</button>
          <button className="operator-entry rounded-lg border border-[#ffbb42]/35 bg-[#ffbb42]/10 px-5 py-2.5 text-sm font-black text-[#ffe4ad] shadow-[0_10px_24px_rgba(255,187,66,.08)]" onClick={onOperatorPanel}>Operatör Paneli</button>
          <span className="max-w-[42ch] text-xs font-bold leading-snug text-[#91a6b7]">Gerçek sistem entegrasyonu için dry-run güvenli panel</span>
        </div>
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
  const [selectionCleared, setSelectionCleared] = useState(false);
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
  const [dismissedTutorialStages, setDismissedTutorialStages] = useState<Stage[]>([]);
  const eventId = useRef(1);
  const strikeId = useRef(1);
  const autoFireAt = useRef(-10);
  const roundResolved = useRef(false);

  const stageSteps = useMemo(() => tutorialSteps.filter((step) => step.stage === 'global' || step.stage === stage), [stage]);
  const tutorialStep = tutorialVisible ? stageSteps[Math.min(tutorialIndex, stageSteps.length - 1)] : undefined;
  const tutorialHighlight = tutorialStep?.highlight;
  const hardPaused = paused || tutorialVisible || baseSafety.estop || mode === 'maintenance';
  const roundTotal = roundTotalFor(stage, simulatorMode);
  const timeLeft = stage === 1 ? Math.max(0, competitionSimulationConfig.stage1.timeLimitSeconds - elapsed) : Math.max(0, roundDurationFor(stage) - elapsed);

  const rawTracks = useMemo(() => generateCompetitionTracks(stage, elapsed, round), [stage, elapsed, round]);
  const tracks = useMemo(() => rawTracks
    .filter((track) => !destroyedIds.includes(track.id))
    .map((track) => ({
      ...track,
      candidate: stage === 1 ? TARGET_ORDER[currentTarget] === track.type : track.candidate,
    })), [currentTarget, destroyedIds, rawTracks, stage]);
  const defaultStage3Enemy = stage === 3 && !selectionCleared ? tracks.find((track) => track.friendFoe === 'Düşman') : undefined;
  const selectedTrack = tracks.find((track) => track.id === selectedId) ?? defaultStage3Enemy;
  const aimTrack = selectedTrack ?? tracks.find((track) => track.candidate);
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
    setSelectionCleared(false);
    setStrikes([]);
    setMode(stageModeExpectation(nextStage));
    setBaseSafety((previous) => ({ ...previous, estop: false, targetGateOk: true, modeOk: true }));
  };

  const dismissTutorialForCurrentStage = () => {
    setDismissedTutorialStages((previous) => previous.includes(stage) ? previous : [...previous, stage]);
    setTutorialVisible(false);
    setTutorialIndex(0);
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
    setTutorialVisible(!dismissedTutorialStages.includes(nextStage));
    addEvent('mode', `AŞAMA_${nextStage}`, 'Yarışma aşaması değiştirildi');
  };

  const finishRound = (forced = false, resolution?: { stage2Hits?: number; stage3HostileDestroyed?: boolean }) => {
    if (stage === 1 || roundResolved.current) return;
    roundResolved.current = true;
    const maxRound = roundTotal;
    if (stage === 2) {
      const hits = resolution?.stage2Hits ?? destroyedIds.length;
      const delta = stage2RoundScore(hits);
      setScore((value) => value + delta);
      setMissionStatus(`Tur ${round} tamam · ${hits} imha · ${delta > 0 ? '+' : ''}${delta}`);
      addEvent('telemetry', 'ROUND_SCORE', `Aşama 2 tur ${round}: ${hits} imha, ${delta} puan${forced ? ' · süre doldu' : ''}`);
    } else {
      const hostileDestroyed = resolution?.stage3HostileDestroyed ?? destroyedIds.some((id) => id.includes('-X'));
      const nextStreak = hostileDestroyed ? 0 : noHitStreak + 1;
      const failed = nextStreak >= competitionSimulationConfig.stage3.failIfConsecutiveHostileMisses;
      if (!hostileDestroyed) setScore((value) => (failed ? 0 : value + competitionSimulationConfig.stage3.maxRoundPenalty));
      setNoHitStreak(nextStreak);
      setMissionStatus(failed ? 'Başarısız · 4 ardışık düşman kaçtı' : hostileDestroyed ? `Tur ${round} tamam · düşman vuruldu` : `Tur ${round} ceza · -10`);
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
      setSelectionCleared(false);
      autoFireAt.current = -10;
      roundResolved.current = false;
    }, 700);
  };

  const handleTrackSelect = (id: string) => {
    const activeSelectionId = selectedTrack?.id;
    if (activeSelectionId === id) {
      setSelectedId(undefined);
      setSelectionCleared(true);
      addEvent('target', 'TRACK_DESELECT', id);
      return;
    }
    setSelectedId(id);
    setSelectionCleared(false);
    addEvent('target', 'TRACK_SELECT', id);
  };

  const handleFire = () => {
    if (stage !== 1) {
      addEvent('fire', 'AUTO_ONLY', 'Aşama 2/3 resmi modda manuel ateş komutu gerektirmez; otonom angajman görselleştirilir');
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
      dismissTutorialForCurrentStage();
      addEvent('telemetry', 'TUTORIAL_DONE', 'Bağlamsal rehber tamamlandı');
      return;
    }
    setTutorialIndex((value) => value + 1);
  };

  useEffect(() => {
    if (hardPaused) return undefined;
    let frameId = 0;
    let previousTimestamp = window.performance.now();
    const tick = (timestamp: number) => {
      const deltaSeconds = Math.min(0.05, Math.max(0, (timestamp - previousTimestamp) / 1000));
      previousTimestamp = timestamp;
      setElapsed((value) => value + deltaSeconds);
      frameId = window.requestAnimationFrame(tick);
    };
    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [hardPaused]);

  useEffect(() => {
    roundResolved.current = false;
    setSelectionCleared(false);
  }, [round, stage]);

  useEffect(() => {
    if (selectedId && !tracks.some((track) => track.id === selectedId)) setSelectedId(undefined);
  }, [selectedId, tracks]);

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
      addEvent('fire', 'AUTO_ENGAGE', `${candidate.id} · Rota ${candidate.lane} · eğitim angajman penceresi`);
      if (destroyedIds.length + 1 >= 3) window.setTimeout(() => finishRound(false, { stage2Hits: destroyedIds.length + 1 }), 150);
      return;
    }
    const enemy = tracks.find((track) => track.friendFoe === 'Düşman' && track.candidate);
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
  const noSelectedStage1 = stage === 1 && !selectedTrack;
  const fireWrongStage1 = stage === 1 && selectedTrack && selectedExpected && selectedTrack.type !== selectedExpected;
  const blockedFireReason = fireSafety.blockReason === 'BLOCKED_TARGET_GATE' && stage === 3
    ? selectedTrack?.friendFoe === 'Dost'
      ? 'Ateş engelli: dost hedef korunuyor'
      : selectedTrack
        ? 'Ateş engelli: hedef geçerli menzil dışında'
        : 'Ateş engelli: hedef seçilmedi'
    : `Ateş engelli: ${blockCopy[fireSafety.blockReason]}`;
  const fireStatus = noSelectedStage1
    ? 'İzin yok'
    : fireSafety.blockReason !== 'ALLOWED'
    ? 'İzin yok'
    : stage === 1
      ? fireWrongStage1 ? 'Ceza riski' : 'Ateş serbest'
      : mode === 'autonomous' ? 'Otonom mantık aktif' : 'İzin yok';
  const fireReason = noSelectedStage1
    ? 'Ateş engelli: hedef seçilmedi'
    : fireSafety.blockReason !== 'ALLOWED'
    ? blockedFireReason
    : stage === 1
      ? fireWrongStage1
        ? `Ceza riski: yanlış hedef seçildi; beklenen ${selectedExpected}`
        : selectedTrack ? `Ateş hazır: ${targetCopy[selectedTrack.type]} ${selectedTrack.range.toFixed(1)} m bandında` : 'Ateş engelli: hedef seçilmedi'
      : mode !== 'autonomous'
        ? 'Ateş engelli: bu resmi aşamada otonom moda geçilmeli'
        : stage === 2
          ? 'Otonom angajman: sistem hedefleri parkur girişinde değil, eğitim penceresinde vurur'
          : selectedTrack?.friendFoe === 'Dost'
            ? 'Ateş engelli: dost hedef korunuyor'
            : selectedTrack?.candidate
              ? `Otonom hazır: ${targetCopy[selectedTrack.type]} düşman hedef için menzil uygun`
              : `Otonom bekliyor: ${rangeLabel(selectedTrack)}`;
  const scoreImpact = stage === 1
    ? noSelectedStage1
      ? 'Puan etkisi: 0'
      : fireWrongStage1
      ? '-5 ceza'
      : selectedTrack ? `Puan etkisi: +${stage1ScoreForRange(selectedTrack.range)}` : 'Puan etkisi: 0'
    : stage === 2
      ? `Tur puanı: ${stage2RoundScore(destroyedIds.length)} şimdi, ${stage2RoundScore(Math.min(3, destroyedIds.length + 1))} olası`
      : selectedTrack?.friendFoe === 'Düşman' && selectedTrack.rangeGate === 'Uygun'
        ? `Puan etkisi: +${stage3TargetScore(selectedTrack.type)}`
        : selectedTrack?.friendFoe === 'Dost' ? 'Puan etkisi: -10 ceza riski' : 'Puan etkisi: -10 tur cezası riski';
  const fireActionState: FireActionState = stage !== 1
    ? 'autonomous'
    : fireSafety.blockReason !== 'ALLOWED' || !selectedTrack
      ? 'blocked'
      : fireWrongStage1 ? 'penalty' : 'ready';
  const fireDisabled = fireActionState === 'blocked' || fireActionState === 'autonomous';
  const timer = stage === 1 ? formatTime(timeLeft) : `${formatTime(timeLeft)} / tur`;
  const fireButtonText = fireActionState === 'autonomous'
    ? 'OTONOM AKTİF'
    : fireActionState === 'ready'
      ? 'ATEŞ HAZIR'
      : fireActionState === 'penalty'
        ? 'CEZA RİSKİ'
        : 'ATEŞ KİLİTLİ';

  return (
    <main className="sim-shell min-h-screen bg-[#05070a] p-2.5 text-[#ecf7ff]">
      <CompetitionHeader
        stage={stage}
        mode={mode}
        timer={timer}
        score={score}
        round={round}
        roundTotal={roundTotal}
        safetyState={systemHealth}
        simulatorMode={simulatorMode}
        onStage={switchStage}
        onSimulatorMode={setSimulatorMode}
      />
      <section className="sim-grid grid min-h-[calc(100vh-216px)] grid-cols-1 gap-2 min-[1051px]:max-[1320px]:[grid-template-columns:minmax(0,1fr)_minmax(292px,320px)] min-[1321px]:[grid-template-columns:minmax(0,1fr)_minmax(292px,330px)]">
        <CourseMap
          stage={stage}
          tracks={tracks}
          selectedTrack={selectedTrack}
          aimTrack={aimTrack}
          destroyedIds={destroyedIds}
          strikes={strikes}
          tutorialHighlight={tutorialHighlight}
          onSelect={handleTrackSelect}
        />
        <GuidancePanel
          stage={stage}
          mode={mode}
          round={round}
          roundTotal={roundTotal}
          selectedTrack={selectedTrack}
          fireStatus={fireStatus}
          fireReason={fireReason}
          scoreImpact={scoreImpact}
          missionStatus={missionStatus}
          tutorialHighlight={tutorialHighlight}
          onRestartTutorial={() => {
            setDismissedTutorialStages((previous) => previous.filter((item) => item !== stage));
            setTutorialVisible(true);
            setTutorialIndex(0);
          }}
        />
      </section>
      <BottomActionBar
        stage={stage}
        mode={mode}
        currentTarget={currentTarget}
        destroyedIds={destroyedIds}
        round={round}
        roundTotal={roundTotal}
        roundHits={roundHits}
        paused={paused || tutorialVisible}
        estop={baseSafety.estop}
        fireDisabled={fireDisabled}
        fireButtonText={fireButtonText}
        fireReason={fireReason}
        scoreImpact={scoreImpact}
        fireActionState={fireActionState}
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
          onSkip={() => { dismissTutorialForCurrentStage(); addEvent('telemetry', 'TUTORIAL_SKIPPED', `Aşama ${stage} rehberi atlandı`); }}
        />
      )}
    </main>
  );
}

type AppSurface = 'landing' | 'simulator' | 'operator';

function initialSurface(): AppSurface {
  const params = new URLSearchParams(window.location.search);
  if (params.has('landing')) return 'landing';
  if (params.has('console')) return 'simulator';
  return 'operator';
}

export default function App() {
  const [surface, setSurface] = useState<AppSurface>(initialSurface);
  if (surface === 'simulator') return <Console />;
  if (surface === 'operator') return <OperatorPanel onBack={() => setSurface('landing')} onOpenSimulator={() => setSurface('simulator')} />;
  return <Landing onEnter={() => setSurface('simulator')} onOperatorPanel={() => setSurface('operator')} />;
}
