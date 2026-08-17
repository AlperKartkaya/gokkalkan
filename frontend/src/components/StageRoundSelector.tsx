import type { Stage } from '../types';

type MissionStatus = 'IDLE' | 'ACTIVE' | 'PAUSED' | 'MAINTENANCE' | 'ESTOP_LATCHED' | 'ROUND_COMPLETE';

export function StageRoundSelector({
  displayStage,
  displayRound,
  missionStatus,
  apiBusy,
  onStartOrAdvance,
}: {
  displayStage: Stage;
  displayRound: number;
  missionStatus: MissionStatus;
  apiBusy: boolean;
  onStartOrAdvance: () => void;
}) {
  const canStart = missionStatus === 'IDLE' || missionStatus === 'ROUND_COMPLETE';
  const actionLabel = missionStatus === 'IDLE'
    ? 'AŞAMA 1 · TUR 1 BAŞLAT'
    : missionStatus === 'ROUND_COMPLETE'
      ? 'SONRAKİ TUR / AŞAMAYI BAŞLAT'
      : null;

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 p-3" data-testid="operator-stage-control">
      <div>
        <p className="m-0 text-[10px] font-black uppercase tracking-[.16em] text-[#25d8ff]">Backend görev sırası</p>
        <div className="mt-1 flex items-center gap-2">
          <strong className="rounded border border-[#33e68c]/35 bg-[#33e68c]/12 px-3 py-1 text-sm text-[#ccffe2]">Aşama {displayStage}</strong>
          <strong className="rounded border border-[#ffbb42]/35 bg-[#ffbb42]/12 px-3 py-1 text-sm text-[#ffe4ad]">Tur {displayRound}</strong>
          <span className="text-xs font-bold text-[#91a6b7]" data-testid="operator-mission-status">{missionStatus}</span>
        </div>
      </div>
      {actionLabel && (
        <button
          type="button"
          className="min-h-11 rounded-lg border border-[#33e68c]/45 bg-[#33e68c]/16 px-4 text-xs font-black tracking-wide text-[#ccffe2] hover:bg-[#33e68c]/24 disabled:opacity-45"
          data-testid="operator-mission-start-button"
          disabled={apiBusy || !canStart}
          onClick={onStartOrAdvance}
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
