import type { Stage } from '../types';

export function CommandConsole({
  displayStage,
  displayRound,
  apiBusy,
  fireReady,
  fireCaption,
  operatorStopActive,
  maintenanceReady,
  maintenanceStatusCopy,
  onRecordStage,
  onSendFireIntent,
  onTriggerOperatorStop,
  onOpenMaintenance,
  stageRoundLimit,
  children,
}: {
  displayStage: Stage;
  displayRound: number;
  apiBusy: boolean;
  fireReady: boolean;
  fireCaption: string;
  operatorStopActive: boolean;
  maintenanceReady: boolean;
  maintenanceStatusCopy: string;
  onRecordStage: (stage: Stage, round: number) => void;
  onSendFireIntent: () => void;
  onTriggerOperatorStop: () => void;
  onOpenMaintenance: () => void;
  stageRoundLimit: (stage: Stage) => number;
  children?: React.ReactNode;
}) {
  return (
    <>
      <section className="rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-stage-control" aria-label="Aşama ve tur kontrolü">
        <p className="m-0 text-xs font-black uppercase tracking-[.16em] text-[#25d8ff]">Görev</p>
        <h2 className="m-0 mt-1 text-2xl font-black">Aşama / Tur</h2>
        <div className="mt-4 grid grid-cols-3 gap-2">
          {([1, 2, 3] as const).map((item) => (
            <button
              key={item}
              className={`rounded-lg border px-3 py-2 text-sm font-black ${displayStage === item ? 'border-[#33e68c]/40 bg-[#33e68c]/14 text-[#ccffe2]' : 'border-white/10 bg-white/[.06] text-[#c8d8e2]'}`}
              disabled={apiBusy}
              onClick={() => onRecordStage(item, 1)}
            >
              Aşama {item}
            </button>
          ))}
        </div>
        <div
          className="operator-round-grid mt-3"
          style={{ '--round-count': stageRoundLimit(displayStage) } as React.CSSProperties}
        >
          {Array.from({ length: stageRoundLimit(displayStage) }, (_, index) => index + 1).map((item) => (
            <button
              key={item}
              className={`rounded-full border px-1.5 py-1 text-[11px] font-black ${displayRound === item ? 'border-[#ffbb42]/40 bg-[#ffbb42]/14 text-[#ffe4ad]' : 'border-white/10 bg-white/[.06] text-[#c8d8e2]'}`}
              disabled={apiBusy}
              onClick={() => onRecordStage(displayStage, item)}
            >
              Tur {item}
            </button>
          ))}
        </div>
      </section>

      {children}

      <section className="operator-action-strip rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-3 mt-3" data-testid="operator-action-strip" aria-label="Operatör komutları">
        <div className="operator-action-buttons">
          <div className="rounded-xl border border-white/[.08] bg-black/20 p-2.5" data-testid="fire-cluster">
            <button
              className={`min-h-16 w-full rounded-xl px-3 text-base font-black ${fireReady ? 'bg-[#ff3146] text-white shadow-[0_18px_42px_rgba(255,71,87,.28)] fire-ready-pulse' : 'bg-white/[.08] text-[#91a6b7]'}`}
              disabled={!fireReady || apiBusy}
              data-testid="operator-fire-button"
              onClick={onSendFireIntent}
            >
              ATEŞ
            </button>
            <p className="m-0 mt-1 truncate text-center text-[11px] font-bold text-[#ffe4ad]">{fireCaption}</p>
          </div>

          <div className="rounded-xl border border-white/[.08] bg-black/20 p-2.5">
            <button
              className="min-h-16 w-full rounded-xl border border-[#ff4757]/35 bg-[#ff4757]/14 px-3 text-base font-black text-[#ffd3d7]"
              data-testid="operator-stop-button"
              disabled={operatorStopActive || apiBusy}
              onClick={onTriggerOperatorStop}
            >
              ACİL DURDUR
            </button>
            <p className="m-0 mt-1 text-center text-[11px] font-bold text-[#ffbdc4]">{operatorStopActive ? 'AKTİF' : 'Hazır'}</p>
          </div>

          <div className="rounded-xl border border-white/[.08] bg-black/20 p-2.5">
            <button
              className="min-h-16 w-full rounded-xl border border-[#48a8ff]/30 bg-[#48a8ff]/10 px-3 text-base font-black text-[#d7efff]"
              data-testid="operator-maintenance-button"
              disabled={!maintenanceReady}
              onClick={onOpenMaintenance}
            >
              BAKIM
            </button>
            <p className="m-0 mt-1 text-center text-[11px] font-bold text-[#91cfff]">{maintenanceStatusCopy}</p>
          </div>
        </div>
      </section>
    </>
  );
}
