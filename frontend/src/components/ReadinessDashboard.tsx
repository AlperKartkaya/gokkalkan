import type { OperatorReadinessItem } from '../operatorApiClient';
import type { OperatorPanelConfig } from '../operatorContracts';
import { EvidenceRow } from './SafetyAuthorityPanel';

const readinessCopy: Record<string, string> = {
  ready: 'Hazır',
  partial: 'Kısmi',
  tbd: 'TBD',
  blocked: 'Kilitli',
};

function readinessTone(status: string) {
  if (status === 'ready') return 'border-[#33e68c]/30 bg-[#33e68c]/10 text-[#bfffe0]';
  if (status === 'partial') return 'border-[#ffbb42]/30 bg-[#ffbb42]/10 text-[#ffe4ad]';
  if (status === 'blocked') return 'border-[#ff4757]/30 bg-[#ff4757]/10 text-[#ffbdc4]';
  return 'border-[#48a8ff]/30 bg-[#48a8ff]/10 text-[#cbe9ff]';
}

export function AdapterRow({ label, item, fallback }: { label: string; item: OperatorReadinessItem | undefined; fallback: string }) {
  const status = item?.status ?? 'tbd';
  return (
    <article className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <b className="text-white">{label}</b>
        <span className={`rounded-full border px-2 py-1 text-[11px] font-black uppercase tracking-[.08em] ${readinessTone(status)}`}>
          {readinessCopy[status]}
        </span>
      </div>
      {!item && <p className="text-[#91a6b7] text-xs mt-2">{fallback}</p>}
    </article>
  );
}

export function ReadinessDashboard({
  maintenanceOpen,
  setMaintenanceOpen,
  readinessById,
  config
}: {
  maintenanceOpen: boolean;
  setMaintenanceOpen: (open: boolean) => void;
  readinessById: Record<string, OperatorReadinessItem | undefined>;
  config: OperatorPanelConfig;
}) {
  return (
    <details className="rounded-xl border border-[#ffbb42]/18 bg-[rgba(10,8,4,.88)] p-4" data-testid="operator-maintenance-drawer" open={maintenanceOpen} onToggle={(event) => setMaintenanceOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer list-none text-xl font-black text-[#ffe4ad]">Bakım / Diagnostik</summary>
      <div className="mt-3 grid gap-2">
        <AdapterRow
          label="Perception Adapter"
          item={readinessById.perception_adapter}
          fallback="Kamera/model çıktısı TrackState sözleşmesine bağlanacak; canlı sınıflandırma adapterı TBD."
        />
        <AdapterRow
          label="TFA50-L 1D LiDAR"
          item={readinessById.radar_lidar_adapter}
          fallback="TFA50-L seri akışı ve 5/10/15 m fiziksel kalibrasyon kanıtı bekleniyor."
        />
        <AdapterRow
          label="MCU / Hardware Protocol"
          item={readinessById.hardware_adapter}
          fallback="Arduino Uno STEP/DIR/STOP yolu hazır; encoder, E-Stop telemetrisi ve FIRE hattı fiziksel HIL'de doğrulanacak."
        />
        <AdapterRow
          label="Canlı Arming / Interlock"
          item={readinessById.live_arming}
          fallback="İki aşamalı arming, hakem/operatör kilidi ve fiziksel interlock tamamlanmadan kapalı."
        />
      </div>
      <div className="mt-3 grid gap-2 text-sm">
        <EvidenceRow label="API base" value={config.apiBaseUrl} />
        <EvidenceRow label="Komut endpointleri" value="POST /stage · POST /mode · POST /fire-intent" />
        <EvidenceRow label="Kanıt endpointleri" value="GET /sensor-frames · GET /readiness · GET /telemetry/export · GET /replay" />
      </div>
      <div className="mt-3 grid gap-2 text-sm" data-testid="operator-lidar-diagnostics">
        <EvidenceRow label="Kamera akışı" value="Canlı MJPEG · nişangâh · hedef bindirmesi" />
        <EvidenceRow label="TFA50-L 1D menzil" value="Seri ölçüm · boresight hizası · kalibrasyon" />
        <EvidenceRow label="Taret kalibrasyonu" value="Komut/ölçüm çifti · bias · ACTIVE durumu" />
      </div>
    </details>
  );
}
