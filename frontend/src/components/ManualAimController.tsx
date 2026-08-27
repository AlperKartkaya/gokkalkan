import { useEffect, useRef, useState } from 'react';

const AIM_STEP_DEG = 11.25;

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
  const [deadmanActive, setDeadmanActive] = useState(false);
  const [activeKey, setActiveKey] = useState<string | null>(null);
  const deadmanRef = useRef(false);
  const aimDisabled = !manualAimReady || !deadmanActive || apiBusy;

  const updateDeadman = (active: boolean) => {
    deadmanRef.current = active;
    setDeadmanActive(active);
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const editing = target?.matches('input, select, textarea, [contenteditable="true"]') ?? false;
      if (editing) return;

      if (event.code === 'Space') {
        event.preventDefault();
        updateDeadman(manualAimReady && !apiBusy);
        return;
      }

      if (!deadmanRef.current || apiBusy || !manualAimReady) return;

      // Field controller mapping: W/S = TILT CW/CCW, A/D = PAN CCW/CW.
      // Keep arrow keys aligned with the same physical axes.
      const delta = {
        KeyW: [0, AIM_STEP_DEG],      // Tilt CW (Motor 2)
        KeyS: [0, -AIM_STEP_DEG],     // Tilt CCW (Motor 2)
        KeyD: [AIM_STEP_DEG, 0],      // Pan CW (Motor 1)
        KeyA: [-AIM_STEP_DEG, 0],     // Pan CCW (Motor 1)
        ArrowUp: [0, AIM_STEP_DEG],
        ArrowDown: [0, -AIM_STEP_DEG],
        ArrowLeft: [-AIM_STEP_DEG, 0],
        ArrowRight: [AIM_STEP_DEG, 0],
      }[event.code];

      if (delta) {
        event.preventDefault();
        setActiveKey(event.code);
        onManualAim(delta[0], delta[1]);
      }
    };

    const handleKeyUp = (event: KeyboardEvent) => {
      if (event.code === 'Space') {
        event.preventDefault();
        updateDeadman(false);
      }
      setActiveKey(null);
    };
    const releaseDeadmanOnBlur = () => updateDeadman(false);

    window.addEventListener('keydown', handleKeyDown, { passive: false });
    window.addEventListener('keyup', handleKeyUp);
    window.addEventListener('blur', releaseDeadmanOnBlur);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
      window.removeEventListener('blur', releaseDeadmanOnBlur);
    };
  }, [apiBusy, manualAimReady, onManualAim]);

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
        <span className="text-[10px] font-bold text-[#25d8ff]">Saha adımı: {AIM_STEP_DEG}°</span>
      </div>

      <button
        type="button"
        className="mt-2 w-full rounded-lg border border-[#ffbb42]/35 bg-[#ffbb42]/10 px-3 py-2 text-xs font-black text-[#ffe4ad] disabled:opacity-40"
        data-testid="operator-deadman-button"
        disabled={!manualAimReady || apiBusy}
        onPointerDown={() => updateDeadman(true)}
        onPointerUp={() => updateDeadman(false)}
        onPointerCancel={() => updateDeadman(false)}
        onPointerLeave={() => updateDeadman(false)}
      >
        {deadmanActive ? 'DEADMAN AKTİF' : 'BASILI TUT: DEADMAN'}
      </button>

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
          onClick={() => onManualAim(0, AIM_STEP_DEG)}
          data-testid="operator-aim-up"
          title="Tilt CW — Motor 2 (W)"
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
          onClick={() => onManualAim(-AIM_STEP_DEG, 0)}
          data-testid="operator-aim-left"
          title="Pan CCW — Motor 1 (A)"
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
          onClick={() => onManualAim(AIM_STEP_DEG, 0)}
          data-testid="operator-aim-right"
          title="Pan CW — Motor 1 (D)"
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
          onClick={() => onManualAim(0, -AIM_STEP_DEG)}
          data-testid="operator-aim-down"
          title="Tilt CCW — Motor 2 (S)"
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
        <span>⌨ <b>Space + W/S</b>: Tilt · <b>Space + A/D</b>: Pan</span>
      </div>
    </section>
  );
}
