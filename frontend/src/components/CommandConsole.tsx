import type { Stage } from '../types';
import { useEffect, useRef, useState } from 'react';

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
  onManualAim,
  manualAimReady,
  turretCalibration,
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
  onManualAim: (panDeltaDeg: number, tiltDeltaDeg: number) => void;
  manualAimReady: boolean;
  turretCalibration?: { active: boolean; calibrationId: string; status: string };
  stageRoundLimit: (stage: Stage) => number;
  children?: React.ReactNode;
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
      if (!delta) return;
      event.preventDefault();
      onManualAim(delta[0], delta[1]);
    };
    const releaseDeadman = (event: KeyboardEvent) => {
      if (event.code === 'Space') updateDeadman(false);
    };
    const releaseDeadmanOnBlur = () => updateDeadman(false);
    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', releaseDeadman);
    window.addEventListener('blur', releaseDeadmanOnBlur);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', releaseDeadman);
      window.removeEventListener('blur', releaseDeadmanOnBlur);
    };
  }, [aimStepDeg, apiBusy, manualAimReady, onManualAim]);

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

      <section
        className="mt-3 rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-3"
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
          <button type="button" disabled={aimDisabled} onClick={() => onManualAim(0, aimStepDeg)} data-testid="operator-aim-up">YUKARI</button>
          <span />
          <button type="button" disabled={aimDisabled} onClick={() => onManualAim(-aimStepDeg, 0)} data-testid="operator-aim-left">SOL</button>
          <button type="button" disabled={aimDisabled} onClick={() => onManualAim(0, -aimStepDeg)} data-testid="operator-aim-down">AŞAĞI</button>
          <button type="button" disabled={aimDisabled} onClick={() => onManualAim(aimStepDeg, 0)} data-testid="operator-aim-right">SAĞ</button>
        </div>
        <p className="m-0 mt-2 text-[10px] text-[#91a6b7]">
          Klavye: Space basılıyken ok/WASD. UI yalnız delta/rate/deadman niyeti gönderir; limit ve Safety kararı backend'e aittir.
        </p>
      </section>

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
              GÖREVİ DURAKLAT
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
