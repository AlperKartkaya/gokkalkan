import type { CSSProperties } from 'react';
import type { Stage } from '../types';

export function StageRoundSelector({
  displayStage,
  displayRound,
  apiBusy,
  onRecordStage,
  stageRoundLimit,
}: {
  displayStage: Stage;
  displayRound: number;
  apiBusy: boolean;
  onRecordStage: (stage: Stage, round: number) => void;
  stageRoundLimit: (stage: Stage) => number;
}) {
  return (
    <div className="flex-1 flex flex-col gap-2 p-3 min-w-0" data-testid="operator-stage-control">
      <div className="flex justify-between items-center">
        <p className="m-0 text-xs font-black uppercase tracking-[.16em] text-[#25d8ff]">Görev Aşama / Tur</p>
      </div>
      <div className="flex gap-2 min-w-0">
        <div className="flex gap-1 border-r border-[#48a8ff]/20 pr-2 mr-1">
          {([1, 2, 3] as const).map((item) => (
            <button
              key={`stage-${item}`}
              className={`rounded-lg border px-3 py-1.5 text-xs whitespace-nowrap font-black ${displayStage === item ? 'border-[#33e68c]/40 bg-[#33e68c]/14 text-[#ccffe2]' : 'border-white/10 bg-white/[.06] text-[#c8d8e2]'}`}
              disabled={apiBusy}
              onClick={() => onRecordStage(item, 1)}
            >
              Aşama {item}
            </button>
          ))}
        </div>
        <div
          className="operator-round-grid overflow-x-auto pb-1 min-w-0"
          style={{ '--round-count': stageRoundLimit(displayStage) } as CSSProperties}
        >
          {Array.from({ length: stageRoundLimit(displayStage) }, (_, index) => index + 1).map((item) => (
            <button
              key={`round-${item}`}
              className={`rounded-full border px-2.5 py-1 text-[11px] whitespace-nowrap font-black ${displayRound === item ? 'border-[#ffbb42]/40 bg-[#ffbb42]/14 text-[#ffe4ad]' : 'border-white/10 bg-white/[.06] text-[#c8d8e2]'}`}
              disabled={apiBusy}
              onClick={() => onRecordStage(displayStage, item)}
            >
              Tur {item}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
