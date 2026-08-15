import { useMemo, useState } from 'react';
import type { OperatorTrackState, OperatorSensorFrame } from '../operatorContracts';
import type { OperatorBackendState } from '../hooks/useOperatorBackendState';

import Navigation from './Navigation';

export default function AIPanel({
  backendState,
  onOpenOperator,
}: {
  backendState: OperatorBackendState;
  onOpenOperator: () => void;
}) {
  const { snapshot, error } = backendState;
  const [cameraFailed, setCameraFailed] = useState(false);
  
  const cameraStreamUrl = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('cameraStream')?.trim()
      || (import.meta.env.VITE_GOKKALKAN_CAMERA_STREAM_URL as string | undefined)?.trim()
      || 'http://127.0.0.1:8090/camera/live.mjpg';
  }, []);

  const getTargetColor = (friendFoe?: string, type?: string) => {
    const f = friendFoe?.toLowerCase();
    if (f === 'düşman' || type === 'balistik füze') return '#ff4757';
    if (f === 'dost') return '#25d8ff';
    return '#ffbb42';
  };

  const tracks = snapshot?.tracks ?? [];
  const frames = snapshot?.sensorFrames ?? [];

  return (
    <div className="flex flex-col h-screen bg-[#070a0e] text-[#8ba7be] overflow-auto pt-20 p-6">
      <Navigation activeSurface="ai" onOpenOperator={onOpenOperator} onOpenAI={() => undefined} />
      <header className="mb-6 border-b border-[#48a8ff]/20 pb-4">
        <h1 className="text-2xl font-black text-[#d7efff]">Yapay Zeka & Algı (Perception) Paneli</h1>
        <p className="mt-2 text-sm text-[#8ba7be]">Sentetik kamera, ROI geometrisi ve hedef takip telemetrisi özeti.</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        
        {/* Live Camera & Bounding Boxes */}
        <div className="rounded-xl border border-[#48a8ff]/20 bg-[rgba(10,15,22,.9)] shadow-[0_8px_32px_rgba(72,168,255,.05)] lg:col-span-2 overflow-hidden flex flex-col relative items-center justify-center bg-black">
          <div className="absolute top-4 left-4 z-10 rounded-lg border border-[#25d8ff]/30 bg-black/75 px-3 py-2 font-mono text-xs">
             <span className="block text-[#91a6b7]">CANLI OPTİK / AI TESPİT</span>
             <b className={snapshot && !error ? 'text-[#33e68c]' : 'text-[#ff4757]'}>
               {snapshot && !error ? 'TELEMETRİ BAĞLI' : 'TELEMETRİ BEKLENİYOR'}
             </b>
          </div>
          
          <div className="relative w-full max-w-[1200px] aspect-video">
            {cameraFailed ? (
              <div className="absolute inset-0 grid place-items-center text-center text-[#ffbdc4] bg-black/80">
                <div><b>KAMERA AKIŞI BEKLENİYOR</b><p className="text-sm mt-2 text-[#91a6b7]">Sentetik AI katmanı veri bekliyor. ({cameraStreamUrl})</p></div>
              </div>
            ) : (
              <img src={cameraStreamUrl} className="absolute inset-0 w-full h-full object-contain" alt="AI Canlı Kamera Akışı" onError={() => setCameraFailed(true)} />
            )}

            {/* Bounding Boxes Overlay */}
            <div className="absolute inset-0 pointer-events-none overflow-hidden">
              {tracks.map((t) => {
                if (!t.bboxPx || !t.frameSizePx) return null;
                const [cx, cy, width, height] = t.bboxPx;
                const [frameWidth, frameHeight] = t.frameSizePx;
                if (frameWidth <= 0 || frameHeight <= 0) return null;
                const color = getTargetColor(t.friendFoe, t.targetType);

                return (
                <div 
                  key={t.trackId}
                  className="absolute border-2 bg-[rgba(0,0,0,0.1)] flex flex-col justify-end"
                  style={{
                    left: `${(cx / frameWidth) * 100}%`,
                    top: `${(cy / frameHeight) * 100}%`,
                    width: `${(width / frameWidth) * 100}%`,
                    height: `${(height / frameHeight) * 100}%`,
                    transform: 'translate(-50%, -50%)',
                    borderColor: color,
                    boxShadow: `0 0 10px ${color}80, inset 0 0 10px ${color}40`
                  }}
                >
                  <div className="absolute -top-6 left-0 right-0 text-center font-mono text-[10px] font-black whitespace-nowrap bg-black/60 px-1 rounded border border-transparent" style={{ color, borderColor: `${color}40` }}>
                    {t.targetType.toUpperCase()} · {t.fireCandidate === false ? 'ATIŞ DIŞI' : `${t.rangeM.toFixed(1)}m`}
                  </div>
                </div>
              );
            })}
            </div>
            {tracks.length > 0 && tracks.every((track) => !track.bboxPx) && (
              <div className="absolute bottom-3 right-3 rounded border border-[#ffbb42]/30 bg-black/75 px-3 py-2 text-xs text-[#ffe4ad]">
                Track telemetrisi bağlı; piksel bbox verisi bekleniyor.
              </div>
            )}
          </div>
        </div>

        {/* Track State Table */}
        <div className="rounded-xl border border-[#48a8ff]/20 bg-[rgba(10,15,22,.9)] p-5 shadow-[0_8px_32px_rgba(72,168,255,.05)]">
          <h2 className="text-lg font-bold text-[#cbe9ff] mb-4">Aktif Hedef İzleri (Tracks)</h2>
          {tracks.length === 0 ? (
            <p className="text-sm text-[#8ba7be]/70 italic">Algılanan hedef izi bulunmuyor.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[#48a8ff]/20 text-[#8ba7be]">
                    <th className="pb-2 font-semibold">Track ID</th>
                    <th className="pb-2 font-semibold">Hedef Türü</th>
                    <th className="pb-2 font-semibold">Güven %</th>
                    <th className="pb-2 font-semibold">Menzil (m)</th>
                    <th className="pb-2 font-semibold">Yönelim (°)</th>
                  </tr>
                </thead>
                <tbody>
                  {tracks.map((t: OperatorTrackState) => (
                    <tr key={t.trackId} className="border-b border-[#48a8ff]/10 hover:bg-[#48a8ff]/5">
                      <td className="py-2 font-mono text-xs text-[#33e68c]">{t.trackId.slice(0, 8)}</td>
                      <td className="py-2">
                        <span className="inline-flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full" style={{ backgroundColor: getTargetColor(t.friendFoe, t.targetType), boxShadow: `0 0 6px ${getTargetColor(t.friendFoe, t.targetType)}` }}></span>
                          <span className="uppercase text-xs font-black" style={{ color: getTargetColor(t.friendFoe, t.targetType) }}>{t.targetType}</span>
                        </span>
                      </td>
                      <td className="py-2">{(t.confidence * 100).toFixed(1)}%</td>
                      <td className="py-2">{t.rangeM.toFixed(1)}</td>
                      <td className="py-2">{t.bearingDeg.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Sensor Frames Table */}
        <div className="rounded-xl border border-[#48a8ff]/20 bg-[rgba(10,15,22,.9)] p-5 shadow-[0_8px_32px_rgba(72,168,255,.05)]">
          <h2 className="text-lg font-bold text-[#cbe9ff] mb-4">Sensör Frameleri (Fusion / Lidar)</h2>
          {frames.length === 0 ? (
            <p className="text-sm text-[#8ba7be]/70 italic">Kayıtlı sensör frame bulunmuyor.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-[#48a8ff]/20 text-[#8ba7be]">
                    <th className="pb-2 font-semibold">Frame ID</th>
                    <th className="pb-2 font-semibold">Sensör</th>
                    <th className="pb-2 font-semibold">Menzil (m)</th>
                    <th className="pb-2 font-semibold">RCS / SNR</th>
                    <th className="pb-2 font-semibold">Hedef</th>
                  </tr>
                </thead>
                <tbody>
                  {frames.slice(0, 10).map((f: OperatorSensorFrame) => (
                    <tr key={f.frameId} className="border-b border-[#48a8ff]/10 hover:bg-[#48a8ff]/5">
                      <td className="py-2 font-mono text-xs text-[#ffbb42]">{f.frameId.slice(0, 8)}</td>
                      <td className="py-2 uppercase text-xs font-bold text-[#bfe7ff]">{f.sensor}</td>
                      <td className="py-2">{f.rangeM.toFixed(1)}</td>
                      <td className="py-2 text-xs">
                        {f.rcsDbsm != null ? `${f.rcsDbsm.toFixed(1)} dB` : '-'} / {f.snrDb != null ? `${f.snrDb.toFixed(1)} dB` : '-'}
                      </td>
                      <td className="py-2 text-xs">
                        <span className="inline-flex items-center gap-1.5">
                          {f.targetType && <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: getTargetColor('unknown', f.targetType) }}></span>}
                          <span className="uppercase font-bold" style={{ color: f.targetType ? getTargetColor('unknown', f.targetType) : '#8ba7be' }}>{f.targetType || 'Bilinmiyor'}</span>
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {frames.length > 10 && <p className="text-xs mt-3 text-[#8ba7be] italic">+ {frames.length - 10} frame daha...</p>}
            </div>
          )}
        </div>

        {/* CAD & Synthetic Data Dashboard Placeholder */}
        <div className="rounded-xl border border-[#ffbb42]/30 bg-[#ffbb42]/5 p-5 shadow-[0_8px_32px_rgba(255,187,66,.05)] lg:col-span-2">
          <h2 className="text-lg font-bold text-[#ffe4ad] mb-4">Sentetik Veri ve ROI Pipeline</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-3 bg-[rgba(0,0,0,0.2)] rounded-lg border border-[#ffbb42]/20">
              <div className="text-xs text-[#ffbb42]/70 uppercase font-black">Course Geometry</div>
              <div className="text-[#ffe4ad] mt-1 font-mono text-sm">{snapshot?.courseGeometry?.datasetId ?? 'N/A'}</div>
            </div>
            <div className="p-3 bg-[rgba(0,0,0,0.2)] rounded-lg border border-[#ffbb42]/20">
              <div className="text-xs text-[#ffbb42]/70 uppercase font-black">Route Count</div>
              <div className="text-[#ffe4ad] mt-1 font-mono text-sm">{snapshot?.courseGeometry?.routeCount ?? '-'}</div>
            </div>
            <div className="p-3 bg-[rgba(0,0,0,0.2)] rounded-lg border border-[#ffbb42]/20">
              <div className="text-xs text-[#ffbb42]/70 uppercase font-black">Target Prior Speed</div>
              <div className="text-[#ffe4ad] mt-1 font-mono text-sm">{snapshot?.courseGeometry?.targetSpeedPriorMps ?? '-'} m/s</div>
            </div>
            <div className="p-3 bg-[rgba(0,0,0,0.2)] rounded-lg border border-[#ffbb42]/20">
              <div className="text-xs text-[#ffbb42]/70 uppercase font-black">Perception Health</div>
              <div className="text-[#ffe4ad] mt-1 font-mono text-sm">
                {snapshot?.missionCore?.perceptionHealthy ? (
                  <span className="text-[#33e68c]">Healthy</span>
                ) : (
                  <span className="text-[#ff4757]">Degraded</span>
                )}
              </div>
            </div>
          </div>
          <p className="mt-4 text-xs text-[#ffbb42]/60">
            * Bu veriler yeni eklenen sentetik (CAD) veri hatları, ROI geometrisi ve yüksek çözünürlüklü frame kırpma hedeflerinden elde edilmektedir.
          </p>
        </div>
      </div>
    </div>
  );
}
