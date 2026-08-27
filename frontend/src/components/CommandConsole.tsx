

export function CommandConsole({
  apiBusy,
  fireReady,
  fireCaption,
  operatorStopActive,
  maintenanceReady,
  maintenanceStatusCopy,
  maintenanceSessionActive,
  maintenanceRemainingSeconds,
  onSendFireIntent,
  onTriggerOperatorStop,
  onOpenMaintenance,
  children,
}: {
  apiBusy: boolean;
  fireReady: boolean;
  fireCaption: string;
  operatorStopActive: boolean;
  maintenanceReady: boolean;
  maintenanceStatusCopy: string;
  maintenanceSessionActive: boolean;
  maintenanceRemainingSeconds: number;
  onSendFireIntent: () => void;
  onTriggerOperatorStop: () => void;
  onOpenMaintenance: () => void;
  children?: React.ReactNode;
}) {
  return (
    <>
      {children}

      <section className="operator-action-strip rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-3" data-testid="operator-action-strip" aria-label="Operatör komutları">
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-xl border border-white/[.08] bg-black/20 p-1.5" data-testid="fire-cluster">
            <button
              className={`min-h-12 w-full rounded-lg px-3 text-sm font-black transition-all ${fireReady ? 'bg-[#ff3146] text-white shadow-[0_12px_24px_rgba(255,71,87,.28)] fire-ready-pulse' : 'bg-white/[.08] text-[#91a6b7]'}`}
              disabled={!fireReady || apiBusy}
              data-testid="operator-fire-button"
              onClick={onSendFireIntent}
              title={fireCaption}
            >
              ATEŞ
            </button>
            <p className="m-0 mt-1 text-center text-[11px] font-bold text-[#91a6b7]" data-testid="operator-fire-caption">
              {fireCaption}
            </p>
          </div>

          <div className="rounded-xl border border-white/[.08] bg-black/20 p-1.5">
            <button
              className={`min-h-12 w-full rounded-lg border px-3 text-sm font-black transition-all ${operatorStopActive ? 'border-[#ff4757]/80 bg-[#ff4757]/30 text-white' : 'border-[#ff4757]/35 bg-[#ff4757]/14 text-[#ffd3d7]'}`}
              data-testid="operator-stop-button"
              disabled={apiBusy || operatorStopActive}
              onClick={onTriggerOperatorStop}
              title={operatorStopActive ? 'Acil Durdur kilidi aktif.' : 'Yazılım Acil Durdur isteği gönder'}
            >
              ACİL DURDUR
            </button>
          </div>

          <div className="rounded-xl border border-white/[.08] bg-black/20 p-1.5">
            <button
              className={`min-h-12 w-full rounded-lg border px-3 text-sm font-black transition-all ${maintenanceSessionActive ? 'border-[#ffbb42]/80 bg-[#ffbb42]/20 text-[#ffe4ad] shadow-[0_0_15px_rgba(255,187,66,.3)]' : 'border-[#48a8ff]/30 bg-[#48a8ff]/10 text-[#d7efff]'}`}
              data-testid="operator-maintenance-button"
              disabled={!maintenanceReady && !maintenanceSessionActive}
              onClick={onOpenMaintenance}
              title={maintenanceStatusCopy}
            >
              {maintenanceSessionActive ? `BİTİR · ${Math.ceil(maintenanceRemainingSeconds)}s` : 'BAKIM'}
            </button>
            <p className="m-0 mt-1 text-center text-[11px] font-bold text-[#91cfff]">{maintenanceStatusCopy}</p>
          </div>
        </div>
      </section>
    </>
  );
}
