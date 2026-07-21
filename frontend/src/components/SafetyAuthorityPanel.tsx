import { type OperatorSafetyState } from '../operatorContracts';

export function EvidenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/[.07] bg-white/[.04] p-3">
      <span className="block text-xs font-black uppercase tracking-[.12em] text-[#91a6b7]">{label}</span>
      <b className="mt-1 block break-words text-[#eaf7ff]">{value}</b>
    </div>
  );
}

export function SafetyAuthorityPanel({
  safety,
}: {
  safety: OperatorSafetyState;
}) {
  return (
    <section className="rounded-xl border border-[#ffbb42]/18 bg-[rgba(10,8,4,.88)] p-4" aria-label="Emniyet kilitleri">
      <h2 className="m-0 text-xl font-black text-[#ffe4ad]">Emniyet</h2>
      <div className="mt-3 grid gap-2 text-sm" data-testid="operator-safety-state">
        <EvidenceRow label="Acil Durdur" value={safety.estop ? 'AKTİF' : 'Pasif'} />
        <EvidenceRow label="Atış alanı" value={safety.fireZoneOk ? 'Uygun' : 'Kilitli'} />
        <EvidenceRow label="Hedef kapısı" value={safety.targetGateOk ? 'Uygun' : 'Dost/bilinmeyen/menzil dışı'} />
        <EvidenceRow label="Durum / Blok" value={safety.blockReason} />
      </div>
    </section>
  );
}
