import type { Mode, Stage } from '../types';
import type { OperatorPanelConfig } from '../operatorContracts';

export function MissionHeader({
  apiBusy,
  config,
  stage,
  mode,
  round,
  onRawLidarOpen,
  onRawCameraOpen,
  onReset,
  missionRemainingSeconds,
}: {
  apiBusy: boolean;
  config: OperatorPanelConfig;
  stage: Stage;
  mode: Mode;
  round: number;
  onRawLidarOpen: () => void;
  onRawCameraOpen: () => void;
  onReset: () => void;
  missionRemainingSeconds?: number;
}) {
  const isTimeCritical = missionRemainingSeconds !== undefined && missionRemainingSeconds <= 30;

  return (
    <header className="operator-header mb-3 flex items-center justify-between gap-3 rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-3 shadow-[0_18px_50px_rgba(0,0,0,.28)]">
      <div className="min-w-0">
        <p className="m-0 text-xs font-black uppercase tracking-[.18em] text-[#ffbb42]">Operasyon</p>
        <h1 className="m-0 mt-1 text-3xl font-black tracking-[.04em] text-white min-[760px]:text-4xl">GÖKKALKAN OPERATÖR PANELİ</h1>
      </div>
      <div className="flex gap-2">
        <div className="flex flex-col text-right">
          <span className="text-xs text-[#25d8ff] font-bold">MOD: {mode.toUpperCase()}</span>
          <span className="text-xs text-[#25d8ff] font-bold">AŞAMA: {stage} TUR: {round}</span>
        </div>
        
        {missionRemainingSeconds !== undefined && (
          <div className={`flex flex-col text-right justify-center rounded-lg px-2 border ${isTimeCritical ? 'border-[#ff4757]/60 bg-[#ff4757]/20 animate-pulse' : 'border-[#48a8ff]/30 bg-[#48a8ff]/10'}`}>
            <span className={`text-[10px] font-black uppercase tracking-widest ${isTimeCritical ? 'text-[#ffbdc4]' : 'text-[#bfe7ff]'}`}>Süre</span>
            <span className={`text-sm font-black ${isTimeCritical ? 'text-[#ff4757]' : 'text-white'}`}>{missionRemainingSeconds}s</span>
          </div>
        )}

        <div className="flex flex-col text-right">
          <span className="text-xs font-bold text-[#ffbb42]">{config.dryRun ? 'DRY-RUN' : 'CANLI'}</span>
          <span className="text-xs font-bold text-[#bfffe0]">BAĞLANTI: {config.connectionState}</span>
        </div>
      </div>
      <div className="operator-header-actions">
        <button
          type="button"
          className="operator-raw-lidar-button"
          data-testid="operator-raw-lidar-button"
          disabled={apiBusy}
          onClick={onRawLidarOpen}
        >
          HAM LİDAR
        </button>
        <button
          type="button"
          className="operator-raw-camera-button"
          data-testid="operator-raw-camera-button"
          disabled={apiBusy}
          onClick={onRawCameraOpen}
        >
          HAM KAMERA
        </button>
        <button
          type="button"
          className="grid h-12 w-12 shrink-0 place-items-center rounded-full border border-[#25d8ff]/25 bg-white/[.06] text-[#d7efff] shadow-[0_0_18px_rgba(37,216,255,.10)] transition hover:bg-[#25d8ff]/12 disabled:opacity-50"
          data-testid="operator-reset-button"
          aria-label="Operatör panelini sıfırla"
          title="Paneli sıfırla"
          disabled={apiBusy}
          onClick={onReset}
        >
          <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden="true">
            <path d="M20 6v5h-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
            <path d="M19 11a7 7 0 1 0-2.05 4.95" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
    </header>
  );
}
