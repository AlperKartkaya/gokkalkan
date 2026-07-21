import type { OperatorTelemetryExport, OperatorReplayBundle, OperatorTelemetryLogRecord } from '../operatorApiClient';
import { EvidenceRow } from './SafetyAuthorityPanel';
import type { OperatorApiSnapshot } from '../operatorApiClient';

function shortRecordPayload(record: OperatorTelemetryLogRecord) {
  const value = record.payload ? JSON.stringify(record.payload) : record.raw ?? 'payload yok';
  return value.length > 120 ? `${value.slice(0, 120)}…` : value;
}

export function HardwareHealthBadge({
  apiBaseUrl,
  evidenceBusy,
  refreshTelemetryEvidence,
  resetTelemetryEvidence,
  evidenceError,
  evidenceNotice,
  unsafeReplayEvidence,
  replayEvidenceWarning,
  telemetryMetadata,
  evidenceEntries,
  replayEventCount,
  replayCommandCount,
  replayHardwareCount,
  telemetryExport,
  replayBundle,
  apiSnapshot
}: {
  apiBaseUrl: string;
  evidenceBusy: boolean;
  refreshTelemetryEvidence: () => void;
  resetTelemetryEvidence: () => void;
  evidenceError: string;
  evidenceNotice: string;
  unsafeReplayEvidence: boolean;
  replayEvidenceWarning?: string;
  telemetryMetadata: any;
  evidenceEntries: OperatorTelemetryLogRecord[];
  replayEventCount: number;
  replayCommandCount: number;
  replayHardwareCount: number;
  telemetryExport?: OperatorTelemetryExport;
  replayBundle?: OperatorReplayBundle;
  apiSnapshot?: OperatorApiSnapshot;
}) {
  return (
    <details className="mt-3 rounded-xl border border-[#48a8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-evidence-drawer">
      <summary className="cursor-pointer list-none text-xl font-black text-[#d7efff]">
        Kayıt / Replay
        <span className="ml-2 rounded-full border border-[#48a8ff]/25 bg-[#48a8ff]/10 px-2 py-1 align-middle text-xs text-[#bfe7ff]">Log</span>
      </summary>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button className="rounded-lg border border-[#48a8ff]/30 bg-[#48a8ff]/10 px-3 py-2 text-sm font-black text-[#cbe9ff] disabled:cursor-not-allowed disabled:opacity-45" disabled={!apiBaseUrl || evidenceBusy} onClick={refreshTelemetryEvidence}>
          {evidenceBusy ? 'Kanıt alınıyor' : 'Kanıtı Yenile'}
        </button>
        <button className="rounded-lg border border-[#ffbb42]/30 bg-[#ffbb42]/10 px-3 py-2 text-sm font-black text-[#ffe4ad] disabled:cursor-not-allowed disabled:opacity-45" disabled={!apiBaseUrl || evidenceBusy} onClick={resetTelemetryEvidence}>
          Telemetriyi Sıfırla
        </button>
      </div>
      {!apiBaseUrl && <p className="m-0 mt-3 rounded-lg border border-[#ffbb42]/25 bg-[#ffbb42]/10 p-3 text-sm font-bold text-[#ffe4ad]">Backend API yok: panel yerel dry-run modunda. Export/replay için `operatorApi` veya VITE_GOKKALKAN_OPERATOR_API_BASE gerekir.</p>}
      {evidenceError && <p className="m-0 mt-3 rounded-lg border border-[#ff4757]/25 bg-[#ff4757]/10 p-3 text-sm font-bold text-[#ffbdc4]">{evidenceError}</p>}
      {evidenceNotice && !evidenceError && <p className="m-0 mt-3 rounded-lg border border-[#33e68c]/25 bg-[#33e68c]/10 p-3 text-sm font-bold text-[#bfffe0]">{evidenceNotice}</p>}
      {unsafeReplayEvidence && <p className="m-0 mt-3 rounded-lg border border-[#ff4757]/30 bg-[#ff4757]/10 p-3 text-sm font-black text-[#ffbdc4]">{replayEvidenceWarning || 'Replay kanıtı güvenli değil: physicalOutput=true kaydı görüldü.'}</p>}
      <div className="mt-3 grid gap-2 text-sm min-[760px]:grid-cols-2">
        <EvidenceRow label="JSONL kayıt yolu" value={telemetryMetadata?.path ?? 'Henüz backend kanıtı alınmadı'} />
        <EvidenceRow label="Kayıt sayısı" value={String(telemetryMetadata?.recordCount ?? evidenceEntries.length)} />
        <EvidenceRow label="Replay özeti" value={`${replayEventCount} olay · ${replayCommandCount} komut · ${replayHardwareCount} dry-run hardware sonucu`} />
        <EvidenceRow label="Fiziksel çıkış" value={(telemetryExport?.physicalOutputEnabled ?? replayBundle?.physicalOutputEnabled ?? apiSnapshot?.physicalOutputEnabled) ? 'AÇIK' : 'KAPALI / YOK'} />
      </div>
      <div className="mt-3 grid max-h-64 gap-2 overflow-auto pr-1" aria-label="Replay kayıtları">
        {evidenceEntries.length === 0 && <p className="m-0 rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm text-[#91a6b7]">Henüz export/replay kaydı alınmadı.</p>}
        {evidenceEntries.slice(0, 8).map((record, index) => (
          <article key={`${record.recordId ?? index}-${record.timestamp ?? 'no-time'}`} className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-xs">
            <b className="text-[#d7efff]">{record.recordType}</b>
            <small className="ml-2 text-[#91a6b7]">{record.timestamp ?? 'timestamp yok'}</small>
            <p className="m-0 mt-1 break-words text-[#c8d8e2]">{shortRecordPayload(record)}</p>
          </article>
        ))}
      </div>
    </details>
  );
}
