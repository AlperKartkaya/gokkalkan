import { type CSSProperties, useEffect, useMemo, useState } from 'react';
import gokkalkanIconUrl from '../assets/gokkalkan_icon.png';
import { COMPETITION_COURSE, displayXForRangeBand, toDisplayCourseMeters } from './competitionCourse';
import {
  canSendFireIntent,
  makeCommandResult,
  makeFireIntent,
  makeStageRequest,
  operatorBlockCopy,
  stageExpectedMode,
  stageRoundLimit,
  type CommandResult,
  type OperatorPanelConfig,
  type OperatorTrackState,
} from './operatorContracts';
import {
  fetchOperatorReplay,
  fetchOperatorReadiness,
  fetchOperatorTelemetryExport,
  resetOperatorTelemetry,
  sendOperatorEStop,
  sendOperatorFireIntent,
  sendOperatorStageRequest,
  type HardwareResult,
  type OperatorReplayBundle,
  type OperatorApiSnapshot,
  type OperatorReadinessItem,
  type OperatorTelemetryExport,
  type OperatorTelemetryLogRecord,
} from './operatorApiClient';
import type { Mode, Stage, TargetType } from './types';
import Navigation from './components/Navigation';
import { MissionHeader } from './components/MissionHeader';
import { CommandConsole } from './components/CommandConsole';
import { ReadinessDashboard } from './components/ReadinessDashboard';
import { EventStream } from './components/EventStream';
import { SafetyAuthorityPanel } from './components/SafetyAuthorityPanel';
import { HardwareHealthBadge } from './components/HardwareHealthBadge';
import { TrackList } from './components/TrackList';
import { ManualAimController } from './components/ManualAimController';
import { StageRoundSelector } from './components/StageRoundSelector';
import { VideoDemoBanner } from './components/VideoDemoBanner';
import { sendMaintenanceEnd, sendMaintenanceRequest, sendOperatorManualAimCommand } from './operatorApiClient';
import { type OperatorBackendState } from './hooks/useOperatorBackendState';


const DEFAULT_OPERATOR_STAGE: Stage = 1;
const TYPE_SYMBOL_CONFIDENCE_THRESHOLD = 0.40;

const targetLabel: Record<TargetType, string> = {
  F16: 'Savaş Uçağı / F16',
  Helikopter: 'Helikopter',
  'Balistik Füze': 'Balistik Füze',
  'Mini/Micro İHA': 'Mini/Micro İHA',
};

function makeBootCommandResult() {
  return makeCommandResult({
    commandId: 'BOOT-DRY-RUN',
    kind: 'ModeRequest',
    accepted: true,
    dryRun: true,
    safetyBlockReason: 'ALLOWED',
    createdAt: new Date('2026-05-25T20:00:00Z'),
  });
}

function affiliationClass(friendFoe: OperatorTrackState['friendFoe']) {
  if (friendFoe === 'Düşman') return 'enemy';
  if (friendFoe === 'Dost') return 'friend';
  return 'unknown';
}

function isKnownTargetType(type: string): type is TargetType {
  return Object.hasOwn(targetLabel, type);
}

function hasReliableTrackType(
  track: Pick<OperatorTrackState, 'confidence' | 'typeConfidence' | 'targetType'>,
): track is Pick<OperatorTrackState, 'confidence' | 'typeConfidence' | 'targetType'> & { targetType: TargetType } {
  return (track.typeConfidence ?? track.confidence) >= TYPE_SYMBOL_CONFIDENCE_THRESHOLD
    && isKnownTargetType(track.targetType);
}

function stageHasHostilityDetection(stage: Stage) {
  return stage === 3;
}

function operatorXForRange(range: number) {
  return displayXForRangeBand(range);
}

function clampPercent(value: number, min = 7, max = 93) {
  return Math.min(max, Math.max(min, value));
}

function clampNumber(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function formatDuration(totalSeconds: number) {
  const boundedSeconds = Math.max(0, Math.ceil(totalSeconds));
  const minutes = Math.floor(boundedSeconds / 60);
  const seconds = boundedSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

function visualSizeForTarget(type: TargetType) {
  const base = {
    F16: { w: 9.4, h: 6.2 },
    Helikopter: { w: 7.6, h: 7.6 },
    'Balistik Füze': { w: 6.4, h: 9.2 },
    'Mini/Micro İHA': { w: 6.8, h: 6.8 },
  } satisfies Record<TargetType, { w: number; h: number }>;
  return base[type];
}

function visualTrackFor(track: OperatorTrackState, index: number, stage: Stage) {
  const radians = (track.bearingDeg * Math.PI) / 180;
  const size = hasReliableTrackType(track) ? visualSizeForTarget(track.targetType) : { w: 6.2, h: 6.2 };
  const mappedPoint = track.courseState?.insidePoligon && track.courseState.projectedCourseM
    ? toDisplayCourseMeters(track.courseState.projectedCourseM)
    : undefined;
  const x = mappedPoint?.x ?? (stage === 1
    ? clampPercent(operatorXForRange(track.rangeM) + (index % 2 === 0 ? -2.4 : 2.4), 12, 82)
    : clampPercent(operatorXForRange(track.rangeM) + Math.sin(radians) * 7, 13, 72));
  const y = mappedPoint?.y ?? (stage === 1
    ? clampPercent(35 + index * 8, 24, 74)
    : clampPercent(30 + index * 13.5 + Math.sin(radians) * 4, 26, 78));
  const rangeGate = targetRangeGateOk(track) ? 'Uygun' : track.rangeM > 15 ? 'Erken' : 'Geçersiz';
  const courseGate = track.courseState == null || track.courseState.predictionValid;
  const candidate = courseGate && track.friendFoe === 'Düşman' && (stage === 1 || stage === 2 || targetRangeGateOk(track));
  const lane = track.courseState?.routeNumber
    ?? (((index % 3) + 1) as 1 | 2 | 3);
  return { ...track, x, y, w: size.w, h: size.h, rangeGate, candidate, lane };
}

function visualRangeLabel(track?: ReturnType<typeof visualTrackFor>) {
  if (!track) return 'Hedef yok';
  if (track.friendFoe === 'Dost') return 'Dost unsur';
  if (track.rangeGate === 'Uygun') return 'MENZİL UYGUN';
  if (track.rangeGate === 'Erken') return 'ÇOK ERKEN';
  return 'MENZİL DIŞI';
}

const DOME_SOURCE_NOSE_SCREEN_DEG = 135;
const DOME_DEFAULT_ROTATION_DEG = 45;
const OPERATOR_SYSTEM_POSITION = COMPETITION_COURSE.systemPosition;

function domeRotationForVisualTrack(track?: ReturnType<typeof visualTrackFor>) {
  if (!track) return DOME_DEFAULT_ROTATION_DEG;
  const targetAngle = (Math.atan2(track.y - OPERATOR_SYSTEM_POSITION.y, track.x - OPERATOR_SYSTEM_POSITION.x) * 180) / Math.PI;
  return targetAngle - DOME_SOURCE_NOSE_SCREEN_DEG;
}

function targetRangeGateOk(track: OperatorTrackState | undefined) {
  if (!track || !isKnownTargetType(track.targetType)) return false;
  const range = targetEngagementRange(track.targetType);
  return track.rangeM >= range.min && track.rangeM <= range.max;
}

function targetEngagementRange(type: TargetType) {
  if (type === 'F16') return { min: 10, max: 15 };
  if (type === 'Helikopter' || type === 'Balistik Füze') return { min: 5, max: 15 };
  return { min: 0, max: 15 };
}

function permittedRangeForStageTarget(stage: Stage, type: TargetType) {
  if (stage === 2) return { min: 0, max: 15 };
  return targetEngagementRange(type);
}

function shortRecordPayload(record: OperatorTelemetryLogRecord) {
  const value = record.payload ? JSON.stringify(record.payload) : record.raw ?? 'payload yok';
  return value.length > 120 ? `${value.slice(0, 120)}…` : value;
}

function OperatorTargetSilhouette({ type, className = '' }: { type: TargetType; className?: string }) {
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
          <path d="M4 32 L16 28 L36 28 L57 32 L36 36 L16 36 Z" />
          <path d="M32 28 L47 12 L55 15 L42 31 Z M32 36 L47 52 L55 49 L42 33 Z" />
          <path d="M17 28 L8 17 L27 27 Z M17 36 L8 47 L27 37 Z" />
          <path d="M38 29 L47 25 L44 32 L47 39 L38 35 Z" />
          <path d="M23 29 L30 23 L37 29 Z" />
          <circle cx="48" cy="32" r="2" />
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

function OperatorTrackScene({
  stage,
  tracks,
  selectedTrackId,
  shotTrackIds,
  onSelect,
  compact = false,
}: {
  stage: Stage;
  tracks: OperatorTrackState[];
  selectedTrackId: string;
  shotTrackIds: Set<string>;
  onSelect: (trackId: string) => void;
  compact?: boolean;
}) {
  const hostilityDetection = stageHasHostilityDetection(stage);
  const visualTracks = tracks.map((track, index) => visualTrackFor(track, index, stage));
  const selectedVisualTrack = visualTracks.find((track) => track.trackId === selectedTrackId) ?? visualTracks[0];
  const permittedRange = selectedVisualTrack && isKnownTargetType(selectedVisualTrack.targetType)
    ? permittedRangeForStageTarget(stage, selectedVisualTrack.targetType)
    : { min: 5, max: 15 };
  const showPermittedRangeWindow = Boolean(selectedVisualTrack && stage === 3);
  const ruleWindow = selectedVisualTrack && stage === 3
    ? {
        start: Math.min(operatorXForRange(permittedRange.max), operatorXForRange(permittedRange.min)),
        width: Math.abs(operatorXForRange(permittedRange.min) - operatorXForRange(permittedRange.max)),
      }
    : selectedVisualTrack
      ? { start: operatorXForRange(selectedVisualTrack.rangeM) - 6, width: 12 }
      : { start: operatorXForRange(15), width: Math.abs(operatorXForRange(5) - operatorXForRange(15)) };
  const domeAngle = domeRotationForVisualTrack(selectedVisualTrack);
  const domeStyle = {
    left: `${OPERATOR_SYSTEM_POSITION.x}%`,
    top: `${OPERATOR_SYSTEM_POSITION.y}%`,
    '--dome-rotation': `${domeAngle}deg`,
  } as CSSProperties;

  return (
    <section
      className={`parkour-hero operator-track-scene ${compact ? 'is-compact' : ''} stage-${stage} relative overflow-hidden rounded-xl border border-[#25d8ff]/18 bg-[#0b1117] shadow-[inset_0_0_54px_rgba(0,0,0,.56)]`}
      data-testid="operator-track-scene"
      aria-label="Operatör iz görüntüsü"
    >
      <svg className="parkour-overlay" viewBox="0 0 100 100" aria-label={`Aşama ${stage} iz şeması`}>
        <defs>
          <pattern id={`operator-grid-${stage}`} width="5" height="5" patternUnits="userSpaceOnUse">
            <path d="M 5 0 L 0 0 0 5" fill="none" stroke="rgba(174,225,255,.10)" strokeWidth=".25" />
          </pattern>
          <marker id={`operator-arrow-${stage}`} markerWidth="5" markerHeight="5" refX="4.2" refY="2.5" orient="auto">
            <path d="M0,0 L5,2.5 L0,5 Z" fill="#ffbb42" opacity=".78" />
          </marker>
        </defs>
        <rect className="schematic-grid" x="3" y="6" width="94" height="88" rx="4" fill={`url(#operator-grid-${stage})`} />

        {stage === 1 ? (
          <g className="stage1-practice-field">
            {[15, 10, 5].map((range) => (
              <g key={range} className={`stage1-zone zone-${range} ${selectedVisualTrack && Math.abs(selectedVisualTrack.rangeM - range) < 2.6 ? 'active' : ''}`} data-testid={`operator-range-${range}m`}>
                <rect x={range === 15 ? 9 : range === 10 ? 36 : 63} y="15" width="25" height="66" rx="4" />
                <text x={range === 15 ? 21.5 : range === 10 ? 48.5 : 75.5} y="22">{range} m</text>
              </g>
            ))}
            <text className="stage1-title" x="9" y="10">MANUEL ATIŞ</text>
          </g>
        ) : (
          <g className="moving-course-field">
            {showPermittedRangeWindow && selectedVisualTrack && (
              <>
                <rect className="valid-window active" x={ruleWindow.start} y="15" width={ruleWindow.width} height="77" data-testid="operator-permitted-range-window" />
                <text className="window-label active" x={Math.min(84, Math.max(16, ruleWindow.start + ruleWindow.width / 2))} y="18.2" textAnchor="middle">
                  {visualRangeLabel(selectedVisualTrack)}
                </text>
              </>
            )}
            {[15, 10, 5].map((range) => (
              <g
                key={range}
                className={`range-line ${selectedVisualTrack && range >= permittedRange.min && range <= permittedRange.max ? 'active' : ''}`}
                data-testid={`operator-range-${range}m`}
              >
                <line x1={operatorXForRange(range)} y1="10" x2={operatorXForRange(range)} y2="93" />
                <text x={operatorXForRange(range) + 0.7} y="12">{range} m</text>
              </g>
            ))}
            <text className="point-label" x="7" y="8">POLİGON GİRİŞİ</text>
            <text className="escape-label" x="69" y="96">POLİGON ÇIKIŞI</text>
            {COMPETITION_COURSE.lanes.map((lane) => (
              <g key={lane.lane} className={`lane-path lane-${lane.lane}`}>
                <polyline points={lane.points.map((point) => `${point.x},${point.y}`).join(' ')} markerEnd={`url(#operator-arrow-${stage})`} />
                <text x="8" y={lane.points[0].y - 2}>ROTA {lane.lane}</text>
              </g>
            ))}
          </g>
        )}

        <g className="system-anchor">
          <circle cx={OPERATOR_SYSTEM_POSITION.x} cy={OPERATOR_SYSTEM_POSITION.y} r="1.15" />
          <text x={OPERATOR_SYSTEM_POSITION.x} y={OPERATOR_SYSTEM_POSITION.y + 8} textAnchor="middle">GÖKKALKAN</text>
        </g>
        {selectedVisualTrack && (
          <g className="target-link" data-testid="operator-aim-line">
            <line x1={selectedVisualTrack.x} y1={selectedVisualTrack.y} x2={OPERATOR_SYSTEM_POSITION.x} y2={OPERATOR_SYSTEM_POSITION.y} />
          </g>
        )}
      </svg>

      <div className="parkour-object-layer">
        <div
          className="steel-dome pointer-events-none absolute z-[5] grid h-[62px] w-[62px] -translate-x-1/2 -translate-y-1/2 place-items-center [filter:drop-shadow(0_0_18px_rgba(51,230,140,.24))_drop-shadow(0_10px_20px_rgba(0,0,0,.48))]"
          style={domeStyle}
          data-testid="operator-steel-dome"
          data-rotation={domeAngle.toFixed(1)}
          aria-hidden="true"
        >
          <img className="h-[54px] w-[54px] rounded-full object-contain opacity-90 will-change-transform [transform:rotate(var(--dome-rotation))]" src={gokkalkanIconUrl} alt="" />
        </div>

        {visualTracks.map((track) => {
          const selected = selectedVisualTrack?.trackId === track.trackId;
          const typeReliable = hasReliableTrackType(track);
          const unknown = !typeReliable;
          const shot = shotTrackIds.has(track.trackId);
          const displayAffiliation = hostilityDetection ? track.friendFoe : 'Bilinmeyen';
          const statusText = unknown ? 'tür doğruluğu bekleniyor' : hostilityDetection ? `${targetLabel[track.targetType]} ${track.friendFoe}` : targetLabel[track.targetType];
          return (
            <button
              key={track.trackId}
              className={`aircraft absolute z-[6] grid min-h-[62px] min-w-[58px] -translate-x-1/2 -translate-y-1/2 content-center place-items-center rounded-full border-0 bg-transparent p-0.5 text-center shadow-none transition-[color,filter,transform] duration-150 will-change-[left,top] ${affiliationClass(displayAffiliation)} ${unknown ? 'unknown-object' : ''} ${stage !== 1 ? 'moving' : 'stationary'} ${selected ? 'selected' : ''} ${track.candidate && !shot ? 'candidate' : ''} ${shot ? 'is-shot' : ''}`}
              style={{ left: `${track.x}%`, top: `${track.y}%`, width: `${track.w}%`, height: `${track.h}%` }}
              data-testid={`operator-track-${track.trackId}`}
              data-track-id={track.trackId}
              data-affiliation={displayAffiliation}
              data-identification={unknown ? 'unknown' : 'identified'}
              data-shape={typeReliable ? 'symbol' : 'sphere'}
              data-shot={shot ? 'true' : 'false'}
              aria-label={`${track.trackId} ${statusText} ${track.rangeM.toFixed(1)} metre`}
              onClick={() => onSelect(track.trackId)}
            >
              <span className="motion-trail" />
              <span className="target-visual">{unknown ? <span className="target-unknown-sphere" aria-hidden="true" /> : <OperatorTargetSilhouette type={track.targetType} />}</span>
              {shot && (
                <span className="shot-eliminated-icon" data-testid={`operator-track-shot-icon-${track.trackId}`} aria-hidden="true">
                  <svg viewBox="0 0 64 64">
                    <circle cx="32" cy="32" r="23" />
                    <path d="M20 20 L44 44 M44 20 L20 44" />
                  </svg>
                </span>
              )}
            </button>
          );
        })}
      </div>

      {hostilityDetection && (
        <div className="map-legend absolute bottom-3 left-3.5 z-[8] flex flex-wrap gap-1.5 rounded-lg border border-white/10 bg-[rgba(2,4,7,.76)] px-2 py-1.5 backdrop-blur">
          <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="enemy-dot" />Düşman</span>
          <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="friend-dot" />Dost</span>
          <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="unknown-dot" />Bilinmeyen</span>
          <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="window-dot" />Menzil</span>
        </div>
      )}
    </section>
  );
}

function CameraReticleOverlay({
  ballistic,
  compact = false,
}: {
  ballistic?: OperatorApiSnapshot['ballisticCompensation'];
  compact?: boolean;
}) {
  const correction = ballistic?.active ? ballistic.elevationCorrectionDeg : null;
  const holdoverTop = correction == null ? null : clampNumber(50 + correction * 4, 12, 88);
  return (
    <div className="absolute inset-0 pointer-events-none z-10" aria-label="Kalibre nişangâh katmanı">
      <span className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 rounded-full border border-[#48a8ff] shadow-[0_0_10px_#48a8ff]" />
      <span className="absolute left-1/2 top-1/2 h-px w-16 -translate-x-1/2 bg-[#48a8ff]" />
      <span className="absolute left-1/2 top-1/2 h-16 w-px -translate-y-1/2 bg-[#48a8ff]" />
      {holdoverTop != null && (
        <span
          className={`absolute left-1/2 -translate-x-1/2 rounded-full border-2 border-dashed border-[#ffbb42] shadow-[0_0_10px_rgba(255,187,66,.55)] ${compact ? 'h-7 w-7' : 'h-10 w-10'}`}
          style={{ top: `${holdoverTop}%` }}
          data-testid="camera-ballistic-holdover"
          title={`Balistik düzeltme ${correction?.toFixed(2)}°`}
        />
      )}
    </div>
  );
}

function RawCameraDiagnosticPage({
  streamUrl,
  ballistic,
  onBack,
}: {
  streamUrl: string;
  ballistic?: OperatorApiSnapshot['ballisticCompensation'];
  onBack: () => void;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <main className="raw-camera-page min-h-screen bg-[#05070a] p-4 md:p-8 text-[#ecf7ff] overflow-y-auto flex flex-col items-center justify-start" data-testid="raw-camera-page">
      <div className="w-full max-w-[1400px] mt-4 md:mt-8 rounded-xl border border-[#25d8ff]/20 bg-[rgba(7,10,14,.94)] overflow-hidden shadow-2xl">
        <header className="flex items-center justify-between gap-3 bg-black/40 border-b border-[#25d8ff]/20 p-5 md:p-6 max-[760px]:flex-col max-[760px]:items-stretch">
          <div>
            <p className="m-0 text-xs font-black uppercase tracking-[.22em] text-[#48a8ff]">Fiziksel sensör akışı</p>
            <h1 className="m-0 mt-1 text-2xl md:text-3xl font-black tracking-[.05em] text-white">HAM KAMERA</h1>
          </div>
          <button type="button" className="min-h-12 rounded-lg border border-[#ffbb42]/35 bg-[#ffbb42]/10 px-6 text-xs md:text-sm font-black tracking-[.12em] text-[#ffe4ad] max-[760px]:w-full transition-colors hover:bg-[#ffbb42]/20 shadow-[0_0_15px_rgba(255,187,66,.15)]" data-testid="raw-camera-back-button" onClick={onBack}>
            OPERATÖR PANELİNE DÖN
          </button>
        </header>
        <section className="p-4 md:p-6 bg-black/60 relative">
          <img src={streamUrl} className={`${failed ? 'hidden' : 'block'} aspect-video w-full rounded-lg bg-black object-contain border border-[#48a8ff]/10 shadow-inner relative z-0`} alt="Kamera sensöründen gelen canlı MJPEG akışı" data-testid="raw-camera-live-stream" onError={() => setFailed(true)} />
          
          {!failed && <CameraReticleOverlay ballistic={ballistic} />}

          {failed && (
            <div className="grid aspect-video w-full place-items-center rounded-lg border border-[#ff4757]/30 bg-[#ff4757]/8 p-8 text-center" data-testid="raw-camera-offline">
              <div>
                <b className="text-lg">FİZİKSEL KAMERA AKIŞI YOK</b>
                <p className="mt-2 text-sm text-[#ffbdc4]">Sentetik görüntü üretilmedi. Perception bridge ve MJPEG servisini doğrulayın.</p>
              </div>
            </div>
          )}
          <p className="mb-0 mt-4 break-all text-xs text-[#91a6b7] text-center font-mono">Kaynak: {streamUrl}</p>
        </section>
      </div>
    </main>
  );
}

function SinglePointLidarView({
  lidarReading,
}: {
  lidarReading?: OperatorApiSnapshot['lidarReading'];
}) {
  const dist = lidarReading?.distanceM;
  const isOk = dist != null && dist > 0;
  const maxRange = 50.0;
  const percent = isOk ? Math.min(100, (dist / maxRange) * 100) : 0;

  return (
    <div className="absolute inset-0 bg-[#070b10] flex flex-col p-6 font-mono text-white select-none">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-4">
        <div>
          <span className="text-xs text-[#25d8ff] font-bold tracking-widest uppercase">Tek Nokta (1D) LiDAR Sensörü</span>
          <h2 className="text-xl font-black text-[#d7efff]">TFA50-L / TFmini Lazer Mesafe Ölçer</h2>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-white/10 bg-white/5 text-xs">
          <span className={`w-2.5 h-2.5 rounded-full ${isOk ? 'bg-[#33e68c] animate-pulse' : 'bg-[#ffbb42]'}`} />
          <span className="font-bold">{isOk ? 'CANLI UART OKUMA AKTİF' : 'BEKLENİYOR / MENZİL DIŞI'}</span>
        </div>
      </div>

      {/* Main Distance Display */}
      <div className="flex-1 flex flex-col items-center justify-center my-6">
        <div className="text-[12px] text-[#91a6b7] mb-2 uppercase tracking-widest">Ölçülen Boresight Menzili</div>
        <div className="flex items-baseline gap-3">
          <span className={`text-6xl md:text-7xl font-black font-mono tracking-tight ${isOk ? 'text-[#33e68c]' : 'text-[#ffbb42]'}`}>
            {isOk ? dist.toFixed(2) : '---'}
          </span>
          <span className="text-2xl font-bold text-[#91a6b7]">metre</span>
        </div>

        {/* Distance Bar Visualizer */}
        <div className="w-full max-w-lg mt-8">
          <div className="flex justify-between text-xs text-[#91a6b7] mb-1.5 font-bold">
            <span>0 m</span>
            <span>15 m (Angajman Sınırı)</span>
            <span>30 m</span>
            <span>50 m (Maks)</span>
          </div>
          <div className="h-4 bg-white/10 rounded-full overflow-hidden p-0.5 border border-white/20 relative">
            <div className="absolute top-0 bottom-0 left-[30%] w-0.5 bg-[#ff4757] z-10" title="15m Sınırı" />
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                isOk && dist <= 15 ? 'bg-gradient-to-r from-[#33e68c] to-[#25d8ff]' : 'bg-gradient-to-r from-[#ffbb42] to-[#ff4757]'
              }`}
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>
      </div>

      {/* Hardware & Telemetry Details */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 border-t border-white/10 pt-4 text-xs">
        <div className="bg-white/5 p-3 rounded-lg border border-white/5">
          <span className="text-[#91a6b7] block">Donanım Portu:</span>
          <b className="text-white mt-1 block">/dev/ttyAMA0 (UART)</b>
        </div>
        <div className="bg-white/5 p-3 rounded-lg border border-white/5">
          <span className="text-[#91a6b7] block">Raspberry Pi 5 Bağlantısı:</span>
          <b className="text-white mt-1 block">Pin 8 (TX) · Pin 10 (RX) · Pin 9 (GND)</b>
        </div>
        <div className="bg-white/5 p-3 rounded-lg border border-white/5">
          <span className="text-[#91a6b7] block">Sensör Protokolü:</span>
          <b className="text-white mt-1 block">115200 / 460800 Baud · 1000 Hz</b>
        </div>
      </div>
    </div>
  );
}



function AccuracyCircle({ label, value, tone, testId }: { label: string; value: number; tone: string; testId: string }) {
  const percent = Math.round(clampNumber(value, 0, 1) * 100);
  return (
    <span
      className={`accuracy-circle ${tone}`}
      style={{ '--accuracy': `${percent}%` } as CSSProperties}
      data-testid={testId}
      aria-label={`${label} doğruluk ${percent}%`}
    >
      <b>{percent}%</b>
      <small>{label}</small>
    </span>
  );
}

function ConfidencePanel({ stage, tracks, selectedTrackId }: { stage: Stage; tracks: OperatorTrackState[]; selectedTrackId: string }) {
  const hostilityDetection = stageHasHostilityDetection(stage);

  return (
    <section className="operator-confidence-panel mt-3 rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-confidence-panel" aria-label="Sınıf ve dost düşman doğruluk yüzdeleri">
      <div
        className="operator-confidence-grid"
        style={{ '--confidence-count': Math.max(1, tracks.length) } as CSSProperties}
      >
        {tracks.map((track) => {
          const unknown = !hasReliableTrackType(track);
          const typeValue = track.typeConfidence ?? track.confidence;
          const colorValue = track.friendFoeConfidence;
          const selected = track.trackId === selectedTrackId;
          const displayType = unknown ? 'Bilinmeyen cisim' : targetLabel[track.targetType];
          const displayAffiliation = hostilityDetection ? track.friendFoe : 'Bilinmeyen';
          return (
            <article
              key={track.trackId}
              className={`confidence-row rounded-lg border p-2.5 ${selected ? 'border-[#ffbb42]/35 bg-[#ffbb42]/10' : 'border-white/[.07] bg-white/[.04]'}`}
              data-testid={`operator-confidence-${track.trackId}`}
              data-affiliation={displayAffiliation}
              data-identification={unknown ? 'unknown' : 'identified'}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <b className="block overflow-hidden text-ellipsis whitespace-nowrap text-sm text-white">{displayType}</b>
                  {hostilityDetection && <span className="block overflow-hidden text-ellipsis whitespace-nowrap text-xs font-black text-[#91a6b7]">{track.friendFoe}</span>}
                </div>
                {hostilityDetection && <i className={`confidence-swatch ${affiliationClass(track.friendFoe)}`} aria-hidden="true" />}
              </div>
              <div className={`accuracy-circle-grid mt-3 ${hostilityDetection ? '' : 'type-only'}`}>
                {hostilityDetection && (
                  colorValue == null ? (
                    <div className="grid place-items-center text-center text-[10px] font-bold text-[#91a6b7]" data-testid={`operator-accuracy-${track.trackId}-color`}>
                      Renk<br />ölçülmedi
                    </div>
                  ) : (
                    <AccuracyCircle
                      label="Renk"
                      value={colorValue}
                      tone={affiliationClass(track.friendFoe)}
                      testId={`operator-accuracy-${track.trackId}-color`}
                    />
                  )
                )}
                <AccuracyCircle
                  label="Tür"
                  value={typeValue}
                  tone={unknown ? 'unknown' : 'type'}
                  testId={`operator-accuracy-${track.trackId}-type`}
                />
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default function OperatorPanel({
  apiBaseUrl,
  backendState,
  onOpenAI,
}: {
  apiBaseUrl: string;
  backendState: OperatorBackendState;
  onBack: () => void;
  onOpenSimulator: () => void;
  onOpenAI: () => void;
}) {
  const queryParams = useMemo(() => new URLSearchParams(window.location.search), []);
  const queryApiBaseUrl = queryParams.get('operatorApi')?.trim() ?? '';
  const isDesktopShell = queryParams.get('desktop') === '1';
  const envApiBaseUrl = (import.meta.env.VITE_GOKKALKAN_OPERATOR_API_BASE as string | undefined)?.trim() ?? '';
  const resolvedApiBaseUrl = apiBaseUrl || queryApiBaseUrl || envApiBaseUrl;
  const cameraStreamUrl = queryParams.get('cameraStream')?.trim()
    || (import.meta.env.VITE_GOKKALKAN_CAMERA_STREAM_URL as string | undefined)?.trim()
    || 'http://127.0.0.1:8090/camera/live.mjpg';
  const liveArmEnabled = import.meta.env.VITE_GOKKALKAN_OPERATOR_LIVE_ARMED === '1';
  const [, setMode] = useState<Mode>(stageExpectedMode(DEFAULT_OPERATOR_STAGE));
  const [stage, setStage] = useState<Stage>(DEFAULT_OPERATOR_STAGE);
  const [round, setRound] = useState(1);
  const [selectedTrackId, setSelectedTrackId] = useState('');
  const [, setLastHardwareResult] = useState<HardwareResult>();
  const [maintenanceOpen, setMaintenanceOpen] = useState(false);
  const {
    snapshot: apiSnapshot,
    setSnapshot: setApiSnapshot,
    readiness: readinessReport,
    setReadiness: setReadinessReport,
    busy: backendBusy,
    error: backendError,
    readinessError: backendReadinessError,
  } = backendState;
  const shotTrackIds = useMemo(
    () => new Set(apiSnapshot?.missionFlow?.completedTargetIds ?? []),
    [apiSnapshot?.missionFlow?.completedTargetIds],
  );
  const [commandBusy, setCommandBusy] = useState(false);
  const [commandApiError, setCommandApiError] = useState('');
  const [readinessRefreshError, setReadinessRefreshError] = useState('');
  const apiBusy = backendBusy || commandBusy;
  const apiError = backendError || commandApiError;
  const readinessError = backendReadinessError || readinessRefreshError;
  const setApiBusy = setCommandBusy;
  const setApiError = setCommandApiError;
  const setReadinessError = setReadinessRefreshError;
  const [telemetryExport, setTelemetryExport] = useState<OperatorTelemetryExport>();
  const [replayBundle, setReplayBundle] = useState<OperatorReplayBundle>();
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  
  const [viewMode, setViewMode] = useState<'lidar' | 'camera'>('camera');
  const [evidenceError, setEvidenceError] = useState('');
  const [evidenceNotice, setEvidenceNotice] = useState('');
  const [rawCameraOpen, setRawCameraOpen] = useState(false);
  const [commandResults, setCommandResults] = useState<CommandResult[]>([makeBootCommandResult()]);

  useEffect(() => {
    if (!apiSnapshot) return;
    setMode(apiSnapshot.mode);
    setStage(apiSnapshot.stage);
    setRound(apiSnapshot.round);
    if (apiSnapshot.commandResults.length > 0) setCommandResults(apiSnapshot.commandResults);
    setSelectedTrackId((current) => {
      const stillVisible = apiSnapshot.tracks.some((track) => track.trackId === current);
      const completed = apiSnapshot.missionFlow?.completedTargetIds.includes(current);
      if (stillVisible && !completed) return current;
      return apiSnapshot.missionFlow?.selectedTargetId
        ?? apiSnapshot.tracks[0]?.trackId
        ?? '';
    });
  }, [apiSnapshot]);

  const config: OperatorPanelConfig = useMemo(() => {
    const apiReady = Boolean(apiSnapshot && !apiError);
    const connectionState = apiReady
      ? apiSnapshot?.runtimeMode === 'HIL'
        ? 'hil'
        : apiSnapshot?.dryRun
          ? 'dry-run'
          : 'live'
      : 'offline';
    return {
      apiBaseUrl: resolvedApiBaseUrl || 'backend-required',
      connectionState,
      dryRun: apiSnapshot?.dryRun ?? true,
      liveArmEnabled: apiSnapshot?.liveArmEnabled ?? (liveArmEnabled && apiReady),
    };
  }, [resolvedApiBaseUrl, apiError, apiSnapshot, liveArmEnabled]);

  const displayStage = apiSnapshot?.stage ?? stage;
  const displayRound = apiSnapshot?.round ?? round;
  useEffect(() => {
    setViewMode('camera');
  }, [displayStage]);
  const visibleTracks = apiSnapshot?.tracks ?? [];
  const authoritativeTargetId = apiSnapshot?.missionFlow?.selectedTargetId ?? '';
  const authoritativeTrack = visibleTracks.find(
    (track) => track.trackId === authoritativeTargetId,
  );
  const safety = apiSnapshot?.safety ?? {
    estop: false,
    motionZoneOk: false,
    fireZoneOk: false,
    targetGateOk: false,
    modeOk: false,
    backendConnected: false,
    perceptionConnected: false,
    sensorAdapterConnected: false,
    dryRun: true,
    liveArmEnabled: false,
    blockReason: 'BLOCKED_BACKEND' as const,
    explanation: 'Backend snapshot yok; panel fail-closed.',
  };
  const missionStatus = apiSnapshot?.missionFlow?.status ?? 'IDLE';
  const maintenanceSessionActive = missionStatus === 'MAINTENANCE';
  const operatorStopActive = missionStatus === 'PAUSED' || missionStatus === 'ESTOP_LATCHED';
  const safetyFireReady = canSendFireIntent(safety, authoritativeTrack?.trackId)
    && missionStatus === 'ACTIVE'
    && authoritativeTrack?.trackId === authoritativeTargetId;
  const isAutonomousFireStage = stageExpectedMode(displayStage) !== 'manual';
  const arduinoHilFireUnsupported = apiSnapshot?.runtimeMode === 'HIL';
  const fireReady = safetyFireReady && Boolean(apiBaseUrl) && !arduinoHilFireUnsupported;
  const fireCaption = fireReady
    ? (isAutonomousFireStage ? 'Backend öncelikli hedef Hazır' : 'Manuel hedef sırası Hazır')
    : arduinoHilFireUnsupported
      ? 'Arduino HIL firmware: FIRE desteklenmiyor'
      : operatorBlockCopy[safety.blockReason];
  const maintenanceCountdownSeconds = apiSnapshot?.maintenanceRemainingBudgetSec ?? 0;
  const maintenanceReady = Boolean(
    apiBaseUrl
    && !apiBusy
    && missionStatus !== 'MAINTENANCE'
    && missionStatus !== 'ESTOP_LATCHED'
    && maintenanceCountdownSeconds >= 30,
  );
  const maintenanceStatusCopy = maintenanceSessionActive
    ? `Aktif · ${formatDuration(maintenanceCountdownSeconds)}`
    : `${formatDuration(maintenanceCountdownSeconds)} bütçe`;
  const telemetryMetadata = telemetryExport?.telemetry ?? apiSnapshot?.telemetry;
  const evidenceEntries = telemetryExport?.entries ?? replayBundle?.entries ?? [];
  const replayHardwareCount = replayBundle?.hardwareResults.length ?? 0;
  const replayCommandCount = replayBundle?.commandResults.length ?? 0;
  const replayEventCount = replayBundle?.events.length ?? 0;
  const unsafeReplayEvidence = Boolean(telemetryExport?.unsafeReplayEvidence || replayBundle?.unsafeReplayEvidence);
  const replayEvidenceWarning = telemetryExport?.evidenceWarning || replayBundle?.evidenceWarning;
  const readinessById = Object.fromEntries(
    (readinessReport?.items ?? []).map((item) => [item.id, item]),
  ) as Record<string, OperatorReadinessItem | undefined>;

  const pushResult = (result: CommandResult) => {
    setCommandResults((previous) => [
      result,
      ...previous.filter((item) => item.commandId !== result.commandId),
    ].slice(0, 8));
  };

  const loadTelemetryEvidence = async () => {
    if (!apiBaseUrl) {
      setEvidenceError('Backend API bağlantısı yok; export/replay için dry-run API başlatılmalı.');
      setEvidenceNotice('Yerel panel olay akışı görüntüleniyor.');
      return;
    }

    const [exported, replay, readiness] = await Promise.all([
      fetchOperatorTelemetryExport(apiBaseUrl),
      fetchOperatorReplay(apiBaseUrl),
      fetchOperatorReadiness(apiBaseUrl).catch((error: unknown) => {
        setReadinessError(error instanceof Error ? error.message : 'Readiness raporu alınamadı.');
        return undefined;
      }),
    ]);
    setTelemetryExport(exported);
    setReplayBundle(replay);
    if (readiness) {
      setReadinessReport(readiness);
      setReadinessError('');
    }
    setApiSnapshot(exported.state);
    if (exported.commandResults.length > 0) setCommandResults(exported.commandResults);
    setEvidenceError('');
    setEvidenceNotice('Kanıt paketi güncellendi; replay yalnız kayıt okur.');
  };

  const refreshTelemetryEvidence = () => {
    setEvidenceBusy(true);
    void loadTelemetryEvidence()
      .catch((error: unknown) => {
        setEvidenceError(error instanceof Error ? error.message : 'Telemetri kanıtı alınamadı.');
        setEvidenceNotice('');
      })
      .finally(() => setEvidenceBusy(false));
  };

  const resetTelemetryEvidence = () => {
    if (!apiBaseUrl) {
      setEvidenceError('Backend API bağlantısı yok; sıfırlama yalnız API üzerinden yapılır.');
      return;
    }

    setEvidenceBusy(true);
    void resetOperatorTelemetry(apiBaseUrl)
      .then(async (response) => {
        setApiSnapshot(response.state);
        setCommandResults(response.state.commandResults);
        setEvidenceNotice('Telemetri sıfırlandı; safe moda dönüldü ve fiziksel çıkış üretilmedi.');
        setEvidenceError('');
        const [exported, replay, readiness] = await Promise.all([
          fetchOperatorTelemetryExport(apiBaseUrl),
          fetchOperatorReplay(apiBaseUrl),
          fetchOperatorReadiness(apiBaseUrl).catch((error: unknown) => {
            setReadinessError(error instanceof Error ? error.message : 'Readiness raporu alınamadı.');
            return undefined;
          }),
        ]);
        setTelemetryExport(exported);
        setReplayBundle(replay);
        if (readiness) {
          setReadinessReport(readiness);
          setReadinessError('');
        }
      })
      .catch((error: unknown) => {
        setEvidenceError(error instanceof Error ? error.message : 'Telemetri sıfırlanamadı.');
        setEvidenceNotice('');
      })
      .finally(() => setEvidenceBusy(false));
  };

  const resetOperatorPanel = () => {
    setSelectedTrackId(authoritativeTargetId);
    setMaintenanceOpen(false);
    setEvidenceError('');
    setCommandApiError('');
    setRawCameraOpen(false);
    setEvidenceNotice('Görünüm backend snapshot durumuna yeniden eşitlendi; görev state değiştirilmedi.');
  };


  const recordStage = (nextStage: Stage, nextRound = 1) => {
    if (!apiBaseUrl) {
      setApiError('Backend API bağlantısı yok; StageRequest fail-closed.');
      return;
    }
    const boundedRound = Math.max(1, Math.min(stageRoundLimit(nextStage), nextRound));
    const request = makeStageRequest({
      stage: nextStage,
      round: boundedRound,
      dryRun: config.dryRun,
      reason: 'operator-stage-control',
    });
    setApiBusy(true);
    void sendOperatorStageRequest(apiBaseUrl, request)
      .then((response) => {
        pushResult(response.result);
        setApiSnapshot(response.state);
        setApiError('');
      })
      .catch((error: unknown) => {
        setApiError(error instanceof Error ? error.message : 'Backend StageRequest komutunu kabul etmedi.');
      })
      .finally(() => setApiBusy(false));
  };

  const startOrAdvanceMission = () => {
    if (missionStatus === 'IDLE') {
      recordStage(1, 1);
      return;
    }
    if (missionStatus !== 'ROUND_COMPLETE') return;
    const roundLimit = stageRoundLimit(displayStage);
    if (displayRound < roundLimit) {
      recordStage(displayStage, displayRound + 1);
    } else if (displayStage < 3) {
      recordStage((displayStage + 1) as Stage, 1);
    }
  };

  const sendManualAim = (panDeltaDeg: number, tiltDeltaDeg: number) => {
    if (!apiBaseUrl) {
      setApiError('Backend API bağlantısı yok; manuel yönelim fail-closed.');
      return;
    }
    setApiBusy(true);
    void sendOperatorManualAimCommand(apiBaseUrl, {
      kind: 'ManualAimCommand',
      panDeltaDeg,
      tiltDeltaDeg,
      rateLimitDegPerSec: 12,
      deadmanActive: true,
      dryRun: false,
    })
      .then((response) => {
        pushResult(response.result);
        setApiSnapshot(response.state);
        setApiError('');
      })
      .catch((error: unknown) => {
        setApiError(error instanceof Error ? error.message : 'Manuel yönelim niyeti reddedildi.');
      })
      .finally(() => setApiBusy(false));
  };

  const sendFireIntent = () => {
    if (!apiBaseUrl || !authoritativeTrack || !fireReady) {
      setApiError('Backend-selected hedef veya Safety izni yok; FireIntent gönderilmedi.');
      return;
    }
    const intent = makeFireIntent({
      targetId: authoritativeTrack.trackId,
      stage: displayStage,
      round: displayRound,
      dryRun: config.dryRun,
    });
    setApiBusy(true);
    void sendOperatorFireIntent(apiBaseUrl, intent)
      .then((response) => {
        pushResult(response.result);
        setApiSnapshot(response.state);
        setLastHardwareResult(response.hardwareResult ?? undefined);
        setApiError('');
      })
      .catch((error: unknown) => {
        setLastHardwareResult(undefined);
        setApiError(error instanceof Error ? error.message : 'Backend FireIntent komutunu kabul etmedi.');
      })
      .finally(() => setApiBusy(false));
  };

  const handleEStop = () => {
    if (!apiBaseUrl) {
      setApiError('Backend API bağlantısı yok. Fiziksel E-Stop birincil güvence olarak kullanılmalıdır.');
      return;
    }
    setApiBusy(true);
    void sendOperatorEStop(apiBaseUrl, { active: true })
      .then((response) => {
        setApiSnapshot(response.state);
        setApiError('');
      })
      .catch((error: unknown) => {
        setApiError(error instanceof Error ? error.message : 'Yazılım E-Stop doğrulanamadı.');
      })
      .finally(() => setApiBusy(false));
  };

  const finishMaintenanceSession = () => {
    if (!apiBaseUrl || !maintenanceSessionActive) return;
    setApiBusy(true);
    void sendMaintenanceEnd(apiBaseUrl)
      .then((response) => {
        setApiSnapshot(response.state);
        setMaintenanceOpen(false);
        setApiError(response.accepted ? '' : 'Backend bakım bitişini reddetti.');
      })
      .catch((error: unknown) => setApiError(error instanceof Error ? error.message : 'Bakım bitirilemedi.'))
      .finally(() => setApiBusy(false));
  };

  const openMaintenance = () => {
    if (!apiBaseUrl || !maintenanceReady) return;
    setApiBusy(true);
    void sendMaintenanceRequest(apiBaseUrl)
      .then((response) => {
        setApiSnapshot(response.state);
        setMaintenanceOpen(response.accepted);
        setApiError(response.accepted ? '' : 'Backend bakım geçişini reddetti.');
      })
      .catch((error: unknown) => setApiError(error instanceof Error ? error.message : 'Bakım başlatılamadı.'))
      .finally(() => setApiBusy(false));
  };

  useEffect(() => {
    const lockPage = maintenanceSessionActive || operatorStopActive;
    if (!lockPage) return undefined;
    const rootOverflow = document.documentElement.style.overflow;
    const bodyOverflow = document.body.style.overflow;
    document.documentElement.style.overflow = 'hidden';
    document.body.style.overflow = 'hidden';
    return () => {
      document.documentElement.style.overflow = rootOverflow;
      document.body.style.overflow = bodyOverflow;
    };
  }, [maintenanceSessionActive, operatorStopActive]);

  if (rawCameraOpen) {
    return <RawCameraDiagnosticPage streamUrl={cameraStreamUrl} ballistic={apiSnapshot?.ballisticCompensation} onBack={() => setRawCameraOpen(false)} />;
  }

  return (
    <main className="operator-shell min-h-screen bg-[#05070a] p-3 text-[#ecf7ff] pt-20" data-testid="operator-panel" data-desktop-shell={isDesktopShell ? 'true' : 'false'}>
      <Navigation activeSurface="operator" onOpenOperator={() => undefined} onOpenAI={onOpenAI} />
      <MissionHeader
        apiBusy={apiBusy}
        config={config}
        missionRemainingSeconds={apiSnapshot?.missionRemainingSeconds === undefined ? undefined : Math.ceil(apiSnapshot.missionRemainingSeconds)}
        onRawCameraOpen={() => setRawCameraOpen(true)}
        onReset={resetOperatorPanel}
      />
      <VideoDemoBanner session={backendState.videoDemoSession} />

      {(apiError || readinessError) && (
        <div
          role="status"
          className="mb-3 rounded-xl border border-[#ff4757]/30 bg-[#ff4757]/10 p-3 text-sm font-bold text-[#ffbdc4]"
          data-testid="operator-backend-error"
        >
          {apiError || readinessError}
        </div>
      )}

      <section className="operator-primary-grid">
        <section className={`operator-3d-panel rounded-xl border ${maintenanceSessionActive ? 'border-[#ffbb42] shadow-[0_0_30px_rgba(255,187,66,.15)]' : 'border-[#48a8ff]/18'} bg-[rgba(7,10,14,.94)] p-0 flex flex-col overflow-hidden relative transition-colors duration-500`} data-testid="operator-sensor-fusion-panel" aria-label="Kamera ve 1D LiDAR yazılım füzyon katmanı">
          <div className="bg-[#48a8ff]/5 border-b border-[#48a8ff]/20 w-full">
            <StageRoundSelector
              displayStage={displayStage}
              displayRound={displayRound}
              missionStatus={missionStatus}
              apiBusy={apiBusy}
              onStartOrAdvance={startOrAdvanceMission}
            />
          </div>
          
          <div className="flex-1 flex flex-col relative min-h-[550px]">
            <div className="absolute top-4 left-1/2 -translate-x-1/2 z-20 flex bg-[#05070a]/90 backdrop-blur-md rounded-lg border border-[#48a8ff]/30 overflow-hidden shadow-2xl">
              <button
                className={`px-3.5 py-1.5 text-xs font-black transition-colors ${viewMode === 'camera' ? 'bg-[#33e68c]/30 text-[#bfffe0]' : 'text-[#8ba7be] hover:bg-white/10'}`}
                onClick={() => setViewMode('camera')}
              >
                OPTİK KAMERA (IMX708)
              </button>
              <button
                className={`px-3.5 py-1.5 text-xs font-black transition-colors ${viewMode === 'lidar' ? 'bg-[#25d8ff]/30 text-[#cbe9ff]' : 'text-[#8ba7be] hover:bg-white/10'}`}
                onClick={() => setViewMode('lidar')}
              >
                1D LİDAR (TFA50-L)
              </button>
            </div>
            {viewMode === 'lidar' ? (
              <SinglePointLidarView lidarReading={apiSnapshot?.lidarReading} />
            ) : (
              <div className="absolute inset-0 bg-black flex flex-col justify-center items-center" data-testid={displayStage === 1 ? 'stage1-camera-support' : undefined}>
                <img src={cameraStreamUrl} className="w-full h-full object-contain" alt="Canlı Kamera Akışı" />
                <CameraReticleOverlay ballistic={apiSnapshot?.ballisticCompensation} compact />
                <div className="absolute left-4 top-16 z-10 rounded-lg border border-[#25d8ff]/30 bg-black/80 backdrop-blur px-3 py-2 font-mono shadow-lg" data-testid="stage1-lidar-range">
                  <span className="block text-[10px] text-[#91a6b7]">1D LİDAR · BORESIGHT · {apiSnapshot?.lidarReading?.distanceM != null ? 'CANLI OKUMA' : 'BEKLENİYOR'}</span>
                  <b className="text-xl text-white">{apiSnapshot?.lidarReading?.distanceM == null ? '---' : `${apiSnapshot.lidarReading.distanceM.toFixed(2)} m`}</b>
                </div>
                
                <div className="absolute bottom-4 left-4 z-10 pointer-events-auto">
                  <ManualAimController
                    apiBusy={apiBusy}
                    manualAimReady={Boolean(
                      apiBaseUrl
                      && displayStage === 1
                      && apiSnapshot?.mode === 'manual'
                      && missionStatus === 'ACTIVE'
                      && !safety.estop
                    )}
                    onManualAim={sendManualAim}
                    turretCalibration={apiSnapshot?.turretCalibration}
                    currentPanDeg={apiSnapshot?.turretPosition?.panDeg}
                    currentTiltDeg={apiSnapshot?.turretPosition?.tiltDeg}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => setRawCameraOpen(true)}
                  className="absolute bottom-4 right-4 z-10 bg-black/60 hover:bg-black/80 text-white p-2.5 rounded-lg border border-white/20 transition-colors flex items-center justify-center"
                  aria-label="Tam Ekran Ham Kamera"
                  title="Tam Ekran Ham Kamera"
                  data-testid="operator-raw-camera-expand-button"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="15 3 21 3 21 9"></polyline>
                    <polyline points="9 21 3 21 3 15"></polyline>
                    <line x1="21" y1="3" x2="14" y2="10"></line>
                    <line x1="3" y1="21" x2="10" y2="14"></line>
                  </svg>
                </button>
              </div>
            )}
          </div>
        </section>

        <aside className="operator-side-rail flex flex-col gap-3 min-h-0">
          <CommandConsole
            apiBusy={apiBusy}
            fireReady={fireReady}
            fireCaption={fireCaption}
            operatorStopActive={operatorStopActive}
            maintenanceReady={maintenanceReady}
            maintenanceStatusCopy={maintenanceStatusCopy}
            onSendFireIntent={sendFireIntent}
            onTriggerOperatorStop={handleEStop}
            onOpenMaintenance={maintenanceSessionActive ? finishMaintenanceSession : openMaintenance}
            maintenanceSessionActive={maintenanceSessionActive}
            maintenanceRemainingSeconds={maintenanceCountdownSeconds}
          >
            <TrackList
              tracks={visibleTracks}
              selectedTrackId={selectedTrackId}
              authoritativeTargetId={authoritativeTargetId}
              onSelect={setSelectedTrackId}
            />
            <OperatorTrackScene
              compact
              stage={displayStage}
              tracks={visibleTracks}
              selectedTrackId={selectedTrackId}
              shotTrackIds={shotTrackIds}
              onSelect={setSelectedTrackId}
            />
          </CommandConsole>
        </aside>
      </section>

      <ConfidencePanel stage={displayStage} tracks={visibleTracks} selectedTrackId={selectedTrackId} />

      <section className="operator-utility-grid mt-3 grid gap-3 min-[1100px]:grid-cols-[minmax(0,.75fr)_minmax(0,.75fr)_minmax(0,1fr)]">
        <SafetyAuthorityPanel safety={safety} />

        <ReadinessDashboard
          maintenanceOpen={maintenanceOpen}
          setMaintenanceOpen={setMaintenanceOpen}
          readinessById={readinessById}
          config={config}
        />

        <div className="relative min-h-0">
          <div className="absolute inset-0 flex flex-col">
            <EventStream commandResults={commandResults} />
          </div>
        </div>
      </section>

      <div className="mt-3">
        <HardwareHealthBadge apiBaseUrl={apiBaseUrl ?? ''} snapshot={apiSnapshot} />
      </div>

      <details className="mt-3 rounded-xl border border-[#48a8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-evidence-drawer">
        <summary className="cursor-pointer list-none text-xl font-black text-[#d7efff]">
          Kayıt / Replay
          <span className="ml-2 rounded-full border border-[#48a8ff]/25 bg-[#48a8ff]/10 px-2 py-1 align-middle text-xs text-[#bfe7ff]">Log</span>
        </summary>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button className="rounded-lg border border-[#48a8ff]/30 bg-[#48a8ff]/10 px-3 py-2 text-sm font-black text-[#cbe9ff] disabled:cursor-not-allowed disabled:opacity-45" disabled={!apiBaseUrl || evidenceBusy} onClick={refreshTelemetryEvidence}>
            {evidenceBusy ? 'Kanıt alınıyor' : 'Kanıtı Yenile'}
          </button>
          <button className="rounded-lg border border-[#ffbb42]/30 bg-[#ffbb42]/10 px-3 py-2 text-sm font-black text-[#ffe4ad] disabled:cursor-not-allowed disabled:opacity-45" disabled={!apiBaseUrl || evidenceBusy} onClick={resetTelemetryEvidence}>
            Telemetriyi Sıfırla
          </button>
        </div>
        {!apiBaseUrl && <p className="m-0 mt-3 rounded-lg border border-[#ffbb42]/25 bg-[#ffbb42]/10 p-3 text-sm font-bold text-[#ffe4ad]">Backend API yok: panel yerel dry-run modunda. Export/replay için `operatorApi` veya VITE_GOKKALKAN_OPERATOR_API_BASE gerekir.</p>}
        {evidenceError && <p className="m-0 mt-3 rounded-lg border border-[#ff4757]/25 bg-[#ff4757]/10 p-3 text-sm font-bold text-[#ffbdc4]">{evidenceError}</p>}
        {evidenceNotice && !evidenceError && <p className="m-0 mt-3 rounded-lg border border-[#33e68c]/25 bg-[#33e68c]/10 p-3 text-sm font-bold text-[#bfffe0]">{evidenceNotice}</p>}
        {unsafeReplayEvidence && <p className="m-0 mt-3 rounded-lg border border-[#ff4757]/30 bg-[#ff4757]/10 p-3 text-sm font-black text-[#ffbdc4]">{replayEvidenceWarning || 'Replay kanıtı güvenli değil: physicalOutput=true kaydı görüldü.'}</p>}
        <div className="mt-3 grid gap-2 text-sm min-[760px]:grid-cols-2">
          <EvidenceRow label="JSONL kayıt yolu" value={telemetryMetadata?.path ?? 'Henüz backend kanıtı alınmadı'} />
          <EvidenceRow label="Kayıt sayısı" value={String(telemetryMetadata?.recordCount ?? evidenceEntries.length)} />
          <EvidenceRow label="Replay özeti" value={`${replayEventCount} olay · ${replayCommandCount} komut · ${replayHardwareCount} hardware sonucu`} />
          <EvidenceRow label="Fiziksel çıkış" value={(telemetryExport?.physicalOutputEnabled ?? replayBundle?.physicalOutputEnabled ?? apiSnapshot?.physicalOutputEnabled) ? 'AÇIK' : 'KAPALI / YOK'} />
        </div>
        <div className="mt-3 grid max-h-64 gap-2 overflow-auto pr-1" aria-label="Replay kayıtları">
          {evidenceEntries.length === 0 && <p className="m-0 rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm text-[#91a6b7]">Henüz export/replay kaydı alınmadı.</p>}
          {evidenceEntries.slice(0, 8).map((record, index) => (
            <article key={`${record.recordId ?? index}-${record.timestamp ?? 'no-time'}`} className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-xs">
              <b className="text-[#d7efff]">{record.recordType}</b>
              <small className="ml-2 text-[#91a6b7]">{record.timestamp ?? 'timestamp yok'}</small>
              <p className="m-0 mt-1 break-words text-[#c8d8e2]">{shortRecordPayload(record)}</p>
            </article>
          ))}
        </div>
      </details>

      {maintenanceSessionActive && (
        <div className="operator-lock-overlay operator-lock-overlay-maintenance" data-testid="operator-maintenance-overlay" role="dialog" aria-modal="true" aria-label="Bakım oturumu">
          <section className="operator-lock-card">
            <span>BAKIM</span>
            <b data-testid="operator-maintenance-countdown">{formatDuration(maintenanceCountdownSeconds)}</b>
            <p data-testid="operator-maintenance-sessions-left">KALAN BÜTÇE: {formatDuration(maintenanceCountdownSeconds)}</p>
            <button type="button" data-testid="operator-maintenance-finish-button" onClick={finishMaintenanceSession}>
              Bakımı Bitir
            </button>
          </section>
        </div>
      )}

      {operatorStopActive && (
        <div className="operator-lock-overlay operator-lock-overlay-emergency" data-testid="operator-stop-overlay" role="dialog" aria-modal="true" aria-label="Acil durdurma">
          <section className="operator-lock-card">
            <span>ACİL DURDUR</span>
            <b>KİLİTLİ</b>
            <p>Fiziksel sinyal bırakılmalı ve kontrollü backend reset uygulanmalıdır.</p>
          </section>
        </div>
      )}

    </main>
  );
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/[.07] bg-white/[.04] p-3">
      <span className="block text-xs font-black uppercase tracking-[.12em] text-[#91a6b7]">{label}</span>
      <b className="mt-1 block break-words text-[#eaf7ff]">{value}</b>
    </div>
  );
}
