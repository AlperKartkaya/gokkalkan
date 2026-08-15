import { useEffect, useRef, useState } from 'react';

export function ManualAimController({
  apiBusy,
  manualAimReady,
  onManualAim,
  turretCalibration,
}: {
  apiBusy: boolean;
  manualAimReady: boolean;
  onManualAim: (panDeltaDeg: number, tiltDeltaDeg: number) => void;
  turretCalibration?: { active: boolean; calibrationId: string; status: string };
}) {
  const [deadmanActive, setDeadmanActive] = useState(false);
  const [aimStepDeg, setAimStepDeg] = useState(1);
  const deadmanRef = useRef(false);
  const aimDisabled = !manualAimReady || !deadmanActive || apiBusy;

  const updateDeadman = (active: boolean) => {
    deadmanRef.current = active;
    setDeadmanActive(active);
  };

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.code === 'Space') {
        event.preventDefault();
        updateDeadman(manualAimReady && !apiBusy);
        return;
      }
      if (!deadmanRef.current || apiBusy) return;
      const delta = {
        ArrowUp: [0, aimStepDeg],
        KeyW: [0, aimStepDeg],
        ArrowDown: [0, -aimStepDeg],
        KeyS: [0, -aimStepDeg],
        ArrowLeft: [-aimStepDeg, 0],
        KeyA: [-aimStepDeg, 0],
        ArrowRight: [aimStepDeg, 0],
        KeyD: [aimStepDeg, 0],
      }[event.code];

      if (delta) {
        event.preventDefault();
        onManualAim(delta[0], delta[1]);
      }
    };

    const releaseDeadman = (event: KeyboardEvent) => {
      if (event.code === 'Space') {
        event.preventDefault();
        updateDeadman(false);
      }
    };
    const releaseDeadmanOnBlur = () => updateDeadman(false);

    window.addEventListener('keydown', handleKeyDown, { passive: false });
    window.addEventListener('keyup', releaseDeadman);
    window.addEventListener('blur', releaseDeadmanOnBlur);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', releaseDeadman);
      window.removeEventListener('blur', releaseDeadmanOnBlur);
    };
  }, [aimStepDeg, apiBusy, manualAimReady, onManualAim]);

  return (
    <section
      className="mt-3 rounded-xl border border-[#25d8ff]/30 bg-black/40 hover:bg-[rgba(7,10,14,.95)] transition-all duration-300 p-3 flex flex-col min-w-[250px]"
      data-testid="operator-manual-aim"
      aria-label="Manuel yönelim ve deadman"
    >
      <div className="flex items-center justify-between gap-2">
        <b className="text-sm text-[#d7efff]">Manuel Yönelim</b>
        <span className="text-xs font-black text-[#91a6b7]">
          {deadmanActive ? 'DEADMAN AKTİF' : 'DEADMAN PASİF'}
        </span>
      </div>
      <div className="mt-2 flex items-center justify-between gap-2 text-[10px]">
        <span className={turretCalibration?.active ? 'text-[#33e68c]' : 'text-[#ffbb42]'} data-testid="operator-turret-calibration">
          Taret kalibrasyonu: {turretCalibration?.active ? turretCalibration.calibrationId : 'AKTİF DEĞİL'}
        </span>
        <label>Adım&nbsp;
          <select className="rounded bg-black px-1 py-0.5 text-white" value={aimStepDeg} onChange={(event) => setAimStepDeg(Number(event.currentTarget.value))}>
            <option value={0.25}>0,25°</option>
            <option value={0.5}>0,5°</option>
            <option value={1}>1°</option>
            <option value={2}>2°</option>
          </select>
        </label>
      </div>
      <button
        type="button"
        className="mt-2 w-full rounded-lg border border-[#ffbb42]/35 bg-[#ffbb42]/10 px-3 py-2 text-sm font-black text-[#ffe4ad] disabled:opacity-40"
        data-testid="operator-deadman-button"
        disabled={!manualAimReady || apiBusy}
        onPointerDown={() => updateDeadman(true)}
        onPointerUp={() => updateDeadman(false)}
        onPointerCancel={() => updateDeadman(false)}
        onPointerLeave={() => updateDeadman(false)}
      >
        BASILI TUT: DEADMAN
      </button>
      <div className="mt-2 grid grid-cols-3 gap-2">
        <span />
        <button type="button" disabled={aimDisabled} className="bg-white/5 rounded border border-white/10" onClick={() => onManualAim(0, aimStepDeg)} data-testid="operator-aim-up">W</button>
        <span />
        <button type="button" disabled={aimDisabled} className="bg-white/5 rounded border border-white/10" onClick={() => onManualAim(-aimStepDeg, 0)} data-testid="operator-aim-left">A</button>
        <button type="button" disabled={aimDisabled} className="bg-white/5 rounded border border-white/10" onClick={() => onManualAim(0, -aimStepDeg)} data-testid="operator-aim-down">S</button>
        <button type="button" disabled={aimDisabled} className="bg-white/5 rounded border border-white/10" onClick={() => onManualAim(aimStepDeg, 0)} data-testid="operator-aim-right">D</button>
      </div>
      <p className="m-0 mt-2 text-[10px] text-[#91a6b7]">
        Space tuşuna basılı tutarak WASD veya yön tuşları ile yönlendirin.
      </p>
    </section>
  );
}
