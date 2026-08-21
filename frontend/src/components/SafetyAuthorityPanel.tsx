/**
 * SafetyAuthorityPanel — Adım 4b
 *
 * Safety Gate durumu ve emniyet kilitleri gösterimi.
 *
 * Güvenlik notu: Fiziksel mantar buton birincil ve bağımsız güvencedir.
 * E-Stop veya güvenlik kilidi aktifken tüm FireIntent/ManualAim aksiyonları
 * backend ve arayüz seviyesinde fail-closed olarak engellenir.
 */
import { type OperatorSafetyState, operatorBlockCopy } from '../operatorContracts';

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
  onEStop: _onEStop,
  eStopBusy: _eStopBusy,
}: {
  safety: OperatorSafetyState;
  onEStop?: () => void;
  eStopBusy?: boolean;
}) {
  const estopActive = safety.estop;
  const blocked = safety.blockReason !== 'ALLOWED';

  return (
    <section className="rounded-xl border border-[#ffbb42]/18 bg-[rgba(10,8,4,.88)] p-4" aria-label="Emniyet kilitleri">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="m-0 text-xl font-black text-[#ffe4ad]">Emniyet Durumu</h2>
        <span className={`px-3 py-1 rounded-lg text-xs font-black ${blocked ? 'bg-[#ff4757]/20 text-[#ff808b] border border-[#ff4757]/40' : 'bg-[#33e68c]/20 text-[#7affbf] border border-[#33e68c]/40'}`}>
          {blocked ? 'KİLİTLİ / GÜVENLİK DEVREDE' : 'SİSTEM HAZIR · NORMAL'}
        </span>
      </div>

      {/* Safety state grid */}
      <div className="mt-3 grid gap-2 text-sm" data-testid="operator-safety-state">
        <EvidenceRow label="Acil Durdur" value={estopActive ? 'AKTİF ⚠️' : 'Pasif ✓'} />
        <EvidenceRow label="Hareket alanı" value={safety.motionZoneOk ? 'Uygun ✓' : 'Kilitli ⚠️'} />
        <EvidenceRow label="Atış alanı" value={safety.fireZoneOk ? 'Uygun ✓' : 'Kilitli ⚠️'} />
        <EvidenceRow label="Hedef kapısı" value={safety.targetGateOk ? 'Uygun ✓' : 'Dost/bilinmeyen/menzil dışı'} />
        <EvidenceRow label="Mod kilidi" value={safety.modeOk ? 'Uygun ✓' : 'Uyumsuz mod'} />
        <EvidenceRow label="Durum / Blok" value={`${safety.blockReason}: ${operatorBlockCopy[safety.blockReason]}`} />
      </div>

      {/* Blocked durum özeti */}
      {blocked && (
        <div className="mt-3 rounded-lg border border-[#ff4757]/25 bg-[#ff4757]/8 p-3 text-xs font-bold text-[#ffbdc4]">
          {operatorBlockCopy[safety.blockReason]}
        </div>
      )}

      {/* Güvenlik notu */}
      <p className="m-0 mt-3 text-[10px] italic text-[#5a7a8a]">
        ⚠ Güvenlik mimarisi: Donanım mantar butonu birincil ve bağımsız emniyet güvencesidir.
      </p>
    </section>
  );
}
