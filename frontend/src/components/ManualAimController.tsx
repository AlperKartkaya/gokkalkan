import { useEffect, useState } from 'react';

export function ManualAimController({
  apiBusy,
  manualAimReady,
  onManualAim,
  turretCalibration,
  currentPanDeg,
  currentTiltDeg,
}: {
  apiBusy: boolean;
  manualAimReady: boolean;
  onManualAim: (panDeltaDeg: number, tiltDeltaDeg: number) => void;
  turretCalibration?: { active: boolean; calibrationId: string; status: string };
  currentPanDeg?: number;
  currentTiltDeg?: number;
}) {
  const [aimStepDeg, setAimStepDeg] = useState(22.5);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const aimDisabled = !manualAimReady || apiBusy;

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const editing = target?.matches('input, select, textarea, [contenteditable="true"]') ?? false;
      if (editing) return;

      if (apiBusy) return;

      // WASD: W/S = Motor 1 (Pan CW/CCW), A/D = Motor 2 (Tilt CCW/CW)
      // Arrow keys: keep traditional directional mapping
      const delta = {
        KeyW: [aimStepDeg, 0],      // Pan CW (Motor 1)
        KeyS: [-aimStepDeg, 0],     // Pan CCW (Motor 1)
        KeyD: [0, aimStepDeg],      // Tilt CW (Motor 2)
        KeyA: [0, -aimStepDeg],     // Tilt CCW (Motor 2)
        ArrowUp: [0, aimStepDeg],
        ArrowDown: [0, -aimStepDeg],
        ArrowLeft: [-aimStepDeg, 0],
        ArrowRight: [aimStepDeg, 0],
      }[event.code];

      if (delta) {
        event.preventDefault();
        setActiveKey(event.code);
        onManualAim(delta[0], delta[1]);
      }
    };

    const handleKeyUp = () => {
      setActiveKey(null);
    };

    window.addEventListener('keydown', handleKeyDown, { passive: false });
    window.addEventListener('keyup', handleKeyUp);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, [aimStepDeg, apiBusy, onManualAim]);

  return (
    <section
      className="rounded-xl border border-[#25d8ff]/30 bg-black/80 backdrop-blur-md p-3.5 flex flex-col min-w-[280px] shadow-2xl transition-all duration-200"
      data-testid="operator-manual-aim"
      aria-label="Manuel yönelim ve WASD kontrolü"
    >
      <div className="flex items-center justify-between gap-2 border-b border-white/10 pb-2">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-[#33e68c] animate-pulse" />
          <b className="text-sm font-black text-[#d7efff]">Taret Yönlendirme (WASD)</b>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-[#91a6b7]">Adım:</span>
          <select
            className="rounded bg-[#111822] border border-white/20 px-1.5 py-0.5 text-xs text-[#25d8ff] font-bold focus:outline-none focus:border-[#25d8ff]"
            value={aimStepDeg}
            onChange={(event) => setAimStepDeg(Number(event.currentTarget.value))}
          >
            <option value={5}>5.0° (Hassas)</option>
            <option value={11.25}>11.25° (Normal)</option>
            <option value={22.5}>22.5° (Hızlı)</option>
            <option value={45}>45.0° (Geniş)</option>
            <option value={90}>90.0° (Maks)</option>
          </select>
        </div>
      </div>

      {/* Angle Status Readout */}
      {(currentPanDeg !== undefined || currentTiltDeg !== undefined) && (
        <div className="mt-2 flex items-center justify-between text-xs font-mono bg-white/5 px-2.5 py-1.5 rounded-lg border border-white/5">
          <span className="text-[#91a6b7]">PAN: <b className="text-white">{currentPanDeg?.toFixed(1)}°</b></span>
          <span className="text-[#91a6b7]">TILT: <b className="text-white">{currentTiltDeg?.toFixed(1)}°</b></span>
        </div>
      )}

      {/* D-PAD / WASD Grid */}
      <div className="mt-3 grid grid-cols-3 gap-2 place-items-center">
        <span />
        <button
          type="button"
          disabled={aimDisabled}
          className={`w-14 h-12 rounded-lg font-mono font-black text-sm flex flex-col items-center justify-center transition-all active:scale-95 ${
            activeKey === 'KeyW' || activeKey === 'ArrowUp'
              ? 'bg-[#25d8ff] text-black border-[#25d8ff] shadow-[0_0_15px_rgba(37,216,255,0.6)]'
              : 'bg-white/10 hover:bg-white/20 text-white border border-white/20 hover:border-[#25d8ff]/50'
          }`}
          onClick={() => onManualAim(aimStepDeg, 0)}
          data-testid="operator-aim-up"
          title="Pan CW — Motor 1 (W)"
        >
          <span className="text-xs">▲</span>
          <span className="text-[10px] opacity-70">W</span>
        </button>
        <span />

        <button
          type="button"
          disabled={aimDisabled}
          className={`w-14 h-12 rounded-lg font-mono font-black text-sm flex flex-col items-center justify-center transition-all active:scale-95 ${
            activeKey === 'KeyA' || activeKey === 'ArrowLeft'
              ? 'bg-[#25d8ff] text-black border-[#25d8ff] shadow-[0_0_15px_rgba(37,216,255,0.6)]'
              : 'bg-white/10 hover:bg-white/20 text-white border border-white/20 hover:border-[#25d8ff]/50'
          }`}
          onClick={() => onManualAim(0, -aimStepDeg)}
          data-testid="operator-aim-left"
          title="Tilt CCW — Motor 2 (A)"
        >
          <span className="text-xs">◀</span>
          <span className="text-[10px] opacity-70">A</span>
        </button>

        <div
          className="w-14 h-12 rounded-lg font-mono font-black text-xs flex flex-col items-center justify-center border border-white/10 bg-white/5 text-[#91a6b7] select-none"
          title="Merkez Nişangâh"
        >
          <span className="text-sm text-[#25d8ff]">🎯</span>
          <span className="text-[8px] opacity-70">NİŞAN</span>
        </div>

        <button
          type="button"
          disabled={aimDisabled}
          className={`w-14 h-12 rounded-lg font-mono font-black text-sm flex flex-col items-center justify-center transition-all active:scale-95 ${
            activeKey === 'KeyD' || activeKey === 'ArrowRight'
              ? 'bg-[#25d8ff] text-black border-[#25d8ff] shadow-[0_0_15px_rgba(37,216,255,0.6)]'
              : 'bg-white/10 hover:bg-white/20 text-white border border-white/20 hover:border-[#25d8ff]/50'
          }`}
          onClick={() => onManualAim(0, aimStepDeg)}
          data-testid="operator-aim-right"
          title="Tilt CW — Motor 2 (D)"
        >
          <span className="text-xs">▶</span>
          <span className="text-[10px] opacity-70">D</span>
        </button>

        <span />
        <button
          type="button"
          disabled={aimDisabled}
          className={`w-14 h-12 rounded-lg font-mono font-black text-sm flex flex-col items-center justify-center transition-all active:scale-95 ${
            activeKey === 'KeyS' || activeKey === 'ArrowDown'
              ? 'bg-[#25d8ff] text-black border-[#25d8ff] shadow-[0_0_15px_rgba(37,216,255,0.6)]'
              : 'bg-white/10 hover:bg-white/20 text-white border border-white/20 hover:border-[#25d8ff]/50'
          }`}
          onClick={() => onManualAim(-aimStepDeg, 0)}
          data-testid="operator-aim-down"
          title="Pan CCW — Motor 1 (S)"
        >
          <span className="text-xs">▼</span>
          <span className="text-[10px] opacity-70">S</span>
        </button>
        <span />
      </div>

      {turretCalibration?.active && (
        <div className="mt-2 text-[10px] text-[#33e68c] font-mono text-center">
          Kalibrasyon: {turretCalibration.calibrationId}
        </div>
      )}

      <div className="mt-3 flex items-center justify-between text-[10px] text-[#91a6b7] border-t border-white/10 pt-2">
        <span>⌨ <b>W/S</b>: Pan (Motor 1) · <b>A/D</b>: Tilt (Motor 2) · Ok tuşları da kullanılabilir.</span>
      </div>
    </section>
  );
}
