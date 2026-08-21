import { useMemo, useState } from 'react';
import type { OperatorBackendState } from '../hooks/useOperatorBackendState';
import { sendOperatorManualAimCommand } from '../operatorApiClient';
import { ManualAimController } from './ManualAimController';

export default function AIPanel({
  apiBaseUrl,
  backendState,
  onOpenOperator,
}: {
  apiBaseUrl?: string;
  backendState: OperatorBackendState;
  onOpenOperator: () => void;
}) {
  const { snapshot, error } = backendState;
  const [cameraFailed, setCameraFailed] = useState(false);
  const [apiBusy, setApiBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState<string>('');
  const activeApiUrl = apiBaseUrl || 'http://127.0.0.1:8088';

  const cameraStreamUrl = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    const defaultStream = typeof window !== 'undefined' && window.location.hostname
      ? `${window.location.protocol}//${window.location.hostname}:8090/camera/live.mjpg`
      : 'http://127.0.0.1:8090/camera/live.mjpg';
    return params.get('cameraStream')?.trim()
      || (import.meta.env.VITE_GOKKALKAN_CAMERA_STREAM_URL as string | undefined)?.trim()
      || defaultStream;
  }, []);

  const handleManualAim = (panDeltaDeg: number, tiltDeltaDeg: number) => {
    if (!activeApiUrl) {
      setActionMessage('HATA: API bağlantısı yok');
      return;
    }
    setApiBusy(true);
    sendOperatorManualAimCommand(activeApiUrl, {
      kind: 'ManualAimCommand',
      panDeltaDeg,
      tiltDeltaDeg,
      rateLimitDegPerSec: 15,
      deadmanActive: true,
      dryRun: false,
    })
      .then((res) => {
        const isOk = res.result?.accepted || (res as unknown as { queued?: boolean }).queued;
        if (isOk) {
          setActionMessage(`Hareket: Pan ${panDeltaDeg > 0 ? '+' : ''}${panDeltaDeg}°, Tilt ${tiltDeltaDeg > 0 ? '+' : ''}${tiltDeltaDeg}°`);
        } else {
          setActionMessage(`Engellendi: ${res.result?.safetyBlockReason || 'Safety Kontrolü'}`);
        }
      })
      .catch((err: unknown) => {
        setActionMessage(`Hata: ${err instanceof Error ? err.message : 'Komut gönderilemedi'}`);
      })
      .finally(() => setApiBusy(false));
  };

  const lidarReading = snapshot?.lidarReading;
  const currentPan = snapshot?.turretPosition?.panDeg ?? 0;
  const currentTilt = snapshot?.turretPosition?.tiltDeg ?? 0;

  return (
    <div className="flex flex-col min-h-screen bg-[#070a0e] text-[#8ba7be] overflow-auto p-4">
      {/* Compact Top Bar */}
      <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-black text-[#d7efff]">GÖKKALKAN</h1>
          <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/60 px-2.5 py-1 text-xs font-mono">
            <span className={`w-2 h-2 rounded-full ${snapshot && !error ? 'bg-[#33e68c] animate-pulse' : 'bg-[#ff4757]'}`} />
            <span>{snapshot && !error ? 'CANLI' : 'BAĞLANTIYI BEKLİYOR'}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-2 rounded-lg border border-[#ffbb42]/30 bg-black/60 px-3 py-1.5 text-xs font-mono">
            <span className={`w-2 h-2 rounded-full ${lidarReading?.distanceM != null ? 'bg-[#33e68c]' : 'bg-[#ffbb42]'}`} />
            <span>LİDAR: <b>{lidarReading?.distanceM != null ? `${lidarReading.distanceM.toFixed(2)} m` : 'BEKLENİYOR'}</b></span>
          </div>
          <button
            type="button"
            onClick={onOpenOperator}
            className="rounded-lg border border-white/20 bg-white/5 hover:bg-white/10 px-3 py-1.5 text-xs text-[#91a6b7] hover:text-white transition-colors"
          >
            Tam Panel →
          </button>
        </div>
      </header>

      {/* Main Layout: Camera + Controls */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-4">

        {/* Live Camera View */}
        <div className="rounded-xl border border-[#48a8ff]/20 bg-black shadow-[0_8px_32px_rgba(72,168,255,.05)] overflow-hidden flex flex-col relative items-center justify-center">

          {/* Top-Right LiDAR HUD (large, always visible) */}
          <div className="absolute top-4 right-4 z-10 rounded-lg border border-[#ffbb42]/40 bg-black/80 backdrop-blur px-4 py-3 font-mono text-right shadow-lg">
            <span className="block text-[#91a6b7] text-[10px]">1D LİDAR MENZİLİ</span>
            <b className="text-2xl text-[#ffe4ad]">
              {lidarReading?.distanceM != null ? `${lidarReading.distanceM.toFixed(2)} m` : '---'}
            </b>
          </div>

          {/* Action Message Feedback */}
          {actionMessage && (
            <div className="absolute top-4 left-4 z-10 rounded bg-[#25d8ff]/20 border border-[#25d8ff]/40 px-2.5 py-1 text-xs text-[#25d8ff] font-mono">
              {actionMessage}
            </div>
          )}

          {/* Camera Feed */}
          <div className="relative w-full aspect-video bg-black flex items-center justify-center">
            {cameraFailed ? (
              <div className="absolute inset-0 grid place-items-center text-center text-[#ffbdc4] bg-black/90 p-6">
                <div>
                  <b className="text-lg text-white">KAMERA YAYINI BEKLENİYOR</b>
                  <p className="text-sm mt-2 text-[#91a6b7]">
                    Kamera akışına bağlanılamadı ({cameraStreamUrl}).
                    <br />
                    SSH tünelinde <b>8090</b> portunun yönlendirildiğinden emin olun:
                    <br />
                    <code className="inline-block mt-2 bg-black px-2 py-1 rounded text-[#25d8ff]">
                      ssh -N -L 4173:127.0.0.1:4173 -L 8088:127.0.0.1:8088 -L 8090:127.0.0.1:8090 gokkalkan@gokkalkan
                    </code>
                  </p>
                  <button
                    type="button"
                    onClick={() => setCameraFailed(false)}
                    className="mt-4 px-4 py-2 bg-[#25d8ff]/20 hover:bg-[#25d8ff]/30 text-[#25d8ff] rounded-lg border border-[#25d8ff]/40 text-xs font-bold"
                  >
                    Yeniden Dene
                  </button>
                </div>
              </div>
            ) : (
              <img
                src={cameraStreamUrl}
                className="w-full h-full object-contain"
                alt="Canlı Kamera Akışı"
                onError={() => setCameraFailed(true)}
              />
            )}

            {/* Crosshair */}
            <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
              <div className="w-12 h-12 border border-white/30 rounded-full flex items-center justify-center">
                <div className="w-2 h-2 bg-[#25d8ff]/80 rounded-full" />
              </div>
              <div className="absolute w-24 h-[1px] bg-white/20" />
              <div className="absolute h-24 w-[1px] bg-white/20" />
            </div>

            {/* Bottom Right Position HUD */}
            <div className="absolute bottom-4 right-4 z-10 rounded-lg border border-white/20 bg-black/80 backdrop-blur px-3 py-1.5 font-mono text-xs text-white">
              PAN: <b>{currentPan.toFixed(1)}°</b> | TILT: <b>{currentTilt.toFixed(1)}°</b>
            </div>
          </div>
        </div>

        {/* Right Sidebar: WASD Controller */}
        <div className="flex flex-col gap-4">
          <ManualAimController
            apiBusy={apiBusy}
            manualAimReady={Boolean(apiBaseUrl)}
            onManualAim={handleManualAim}
            turretCalibration={snapshot?.turretCalibration}
            currentPanDeg={currentPan}
            currentTiltDeg={currentTilt}
          />

          {/* Connection Status */}
          <div className="rounded-xl border border-white/10 bg-[rgba(10,15,22,.9)] p-3 shadow-lg">
            <h2 className="text-xs font-bold text-[#cbe9ff] mb-2 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#25d8ff]" />
              Bağlantı Durumu
            </h2>
            <div className="space-y-1.5 text-xs font-mono">
              <div className="flex justify-between items-center bg-white/5 px-2 py-1.5 rounded">
                <span className="text-[#91a6b7]">Kamera</span>
                <span className={cameraFailed ? 'text-[#ff4757] font-bold' : 'text-[#33e68c] font-bold'}>
                  {cameraFailed ? 'BAĞLANTI YOK' : 'CANLI'}
                </span>
              </div>
              <div className="flex justify-between items-center bg-white/5 px-2 py-1.5 rounded">
                <span className="text-[#91a6b7]">LiDAR</span>
                <span className={lidarReading?.distanceM != null ? 'text-[#33e68c] font-bold' : 'text-[#ffbb42] font-bold'}>
                  {lidarReading?.distanceM != null ? `${lidarReading.distanceM.toFixed(2)} m` : 'BEKLENİYOR'}
                </span>
              </div>
              <div className="flex justify-between items-center bg-white/5 px-2 py-1.5 rounded">
                <span className="text-[#91a6b7]">Backend</span>
                <span className={snapshot && !error ? 'text-[#33e68c] font-bold' : 'text-[#ff4757] font-bold'}>
                  {snapshot && !error ? 'BAĞLI' : 'BAĞLANTI YOK'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
