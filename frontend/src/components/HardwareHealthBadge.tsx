/**
 * HardwareHealthBadge — Adım 4b
 *
 * GET /hardware/health endpoint'ini 3 saniyede bir polling yaparak
 * USB CDC bağlantısı, Pico MCU erişilebilirlik ve physicalOutput durumunu gösterir.
 *
 * Güvenlik notu: Yazılım katmanı ikincil izleme aracıdır.
 * Fiziksel mantar E-Stop birincil güvencedir.
 */
import { useEffect, useRef, useState } from 'react';
import { fetchHardwareHealth, type HardwareHealthResponse } from '../operatorApiClient';
import type { OperatorApiSnapshot } from '../operatorApiClient';

const POLL_INTERVAL_MS = 3000;

function StatusDot({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-xs">
      <span
        className={`inline-block h-2 w-2 rounded-full ${ok ? 'bg-[#33e68c] shadow-[0_0_6px_#33e68c]' : 'bg-[#ff4757] shadow-[0_0_6px_#ff4757]'}`}
        aria-hidden="true"
      />
      <span className={ok ? 'text-[#bfffe0]' : 'text-[#ffbdc4]'}>
        {label}: {ok ? 'UYGUN' : 'KİLİTLİ/YOK'}
      </span>
    </span>
  );
}

export function HardwareHealthBadge({
  apiBaseUrl,
  snapshot,
}: {
  apiBaseUrl: string;
  snapshot?: OperatorApiSnapshot;
}) {
  const [health, setHealth] = useState<HardwareHealthResponse | null>(null);
  const [error, setError] = useState<string>('');
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!apiBaseUrl) return;

    const poll = async () => {
      try {
        const data = await fetchHardwareHealth(apiBaseUrl);
        setHealth(data);
        setError('');
      } catch (e) {
        setError('Donanım sağlık verisi alınamadı');
      }
    };

    poll();
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [apiBaseUrl]);

  if (!apiBaseUrl) {
    return (
      <div className="rounded-xl border border-white/[.07] bg-white/[.03] p-3 text-xs text-[#91a6b7]">
        Backend API bağlı değil — donanım durumu alınamıyor.
      </div>
    );
  }

  return (
    <section
      className="rounded-xl border border-[#48a8ff]/18 bg-[rgba(4,8,16,.92)] p-4"
      aria-label="Donanım Sağlık Durumu"
    >
      <h2 className="m-0 mb-3 text-base font-black text-[#d7efff]">
        Donanım
        <span className="ml-2 rounded-full border border-[#48a8ff]/25 bg-[#48a8ff]/10 px-2 py-0.5 text-xs text-[#bfe7ff]">
          {health?.adapter ?? '…'}
        </span>
      </h2>

      {error && (
        <p className="m-0 mb-2 rounded-lg border border-[#ff4757]/25 bg-[#ff4757]/10 p-2 text-xs font-bold text-[#ffbdc4]">
          {error}
        </p>
      )}

      {health ? (
        <div className="grid grid-cols-2 gap-2">
          <StatusDot ok={health.serialConnected ?? health.busConnected} label="USB CDC" />
          <StatusDot ok={health.picoReachable} label="Pico MCU" />
          <StatusDot ok={health.dryRun} label="Dry-Run Modu" />
          <StatusDot ok={!health.physicalOutputEnabled} label="Fiziksel Çıkış Kapalı" />
          <StatusDot ok={!snapshot?.safety.estop} label="E-Stop Pasif" />
          <StatusDot ok={Boolean(snapshot?.sensorHealth?.perceptionConnected)} label="Kamera/Perception" />
          <StatusDot ok={Boolean(snapshot?.sensorHealth?.adapterConnected)} label="LiDAR Adapter" />
          <StatusDot ok={Boolean(snapshot?.telemetry?.exists)} label="Kayıt/Telemetri" />
          <StatusDot ok={Boolean(health.encoderOk)} label="Enkoder" />
          <span className="col-span-2 text-xs text-[#91a6b7]">
            Pico: <b className="text-[#c8d8e2]">{health.serialPort ?? 'cihaz yolu yok'}</b>
            {' · '}FW: <b className="text-[#c8d8e2]">{health.firmwareVersion ?? 'bilinmiyor'}</b>
            {' · '}Protokol: <b className="text-[#c8d8e2]">v{health.protocolVersion ?? 0}</b>
          </span>
          <span className="col-span-2 text-xs text-[#91a6b7]">
            Status yaşı: <b className="text-[#c8d8e2]">{health.lastStatusAgeSec == null ? 'yok' : `${(health.lastStatusAgeSec * 1000).toFixed(0)} ms`}</b>
            {' · '}Reddedilen frame: <b className="text-[#c8d8e2]">{(health.rejectedRxCount ?? 0) + (health.transportRejectedFrameCount ?? 0)}</b>
          </span>
          <span className="col-span-2 text-xs text-[#c8d8e2]">
            Çalışma profili: <b>{snapshot?.runtimeMode ?? (snapshot?.dryRun ? 'SIM' : 'BİLİNMİYOR')}</b>
            {' · '}Arm: <b>{snapshot?.liveArmEnabled ? 'AÇIK' : 'KAPALI'}</b>
          </span>
          <span className="col-span-2 text-xs text-[#c8d8e2]">
            Safety kararı: <b>{snapshot?.safety.blockReason ?? 'BACKEND SNAPSHOT YOK'}</b>
          </span>
          <span className="col-span-2 text-xs text-[#c8d8e2]">
            Otonom: <b>{snapshot?.autonomousController?.state ?? 'IDLE'}</b>
            {' · '}Neden: <b>{snapshot?.autonomousController?.reason ?? 'veri yok'}</b>
          </span>
          {health.commandCount !== undefined && (
            <span className="col-span-2 text-xs text-[#91a6b7]">
              Komut sayısı: <b className="text-[#c8d8e2]">{health.commandCount}</b>
            </span>
          )}
          {health.lastHeartbeatAt && (
            <span className="col-span-2 text-xs text-[#91a6b7]">
              Son heartbeat: <b className="text-[#c8d8e2]">{health.lastHeartbeatAt}</b>
            </span>
          )}
        </div>
      ) : (
        <p className="m-0 text-xs text-[#91a6b7]">Yükleniyor…</p>
      )}

      <p className="m-0 mt-3 text-[10px] italic text-[#5a7a8a]">
        ⚠ Yazılım E-Stop ikincildir; fiziksel mantar buton birincil güvencedir.
      </p>
    </section>
  );
}
