/**
 * SafetyAuthorityPanel — Adım 4b
 *
 * Safety Gate durumu + ACIL DURDUR (E-Stop) butonu.
 *
 * Güvenlik notu: UI E-Stop ikincil güvencedir.
 * Fiziksel mantar buton birincil ve bağımsız güvencedir.
 * E-Stop aktifken tüm FireIntent/ManualAim butonları disabled olmalıdır;
 * bu kontrol CommandConsole bileşeninde safety.blockReason === 'BLOCKED_ESTOP'
 * üzerinden zaten uygulanmaktadır.
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
  onEStop,
  eStopBusy,
}: {
  safety: OperatorSafetyState;
  onEStop: () => void;
  eStopBusy?: boolean;
}) {
  const estopActive = safety.estop;
  const blocked = safety.blockReason !== 'ALLOWED';

  return (
    <section className="rounded-xl border border-[#ffbb42]/18 bg-[rgba(10,8,4,.88)] p-4" aria-label="Emniyet kilitleri">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="m-0 text-xl font-black text-[#ffe4ad]">Emniyet</h2>

        {/* ACIL DURDUR — şartname WP-04; UI ikincil güvence */}
        <button
          id="estop-btn"
          aria-label="Acil Durdur — Yazılım E-Stop"
          disabled={eStopBusy}
          onClick={onEStop}
          className={[
            'rounded-xl px-5 py-2.5 text-sm font-black uppercase tracking-widest transition-all',
            'border-2 focus:outline-none focus-visible:ring-4 focus-visible:ring-[#ff4757]/60',
            estopActive
              ? 'cursor-not-allowed border-[#ff4757] bg-[#ff4757]/25 text-[#ff4757] shadow-[0_0_18px_#ff475788] animate-pulse'
              : 'border-[#ff4757] bg-[#ff4757] text-white shadow-[0_0_10px_#ff475766] hover:bg-[#ff2233] hover:shadow-[0_0_22px_#ff4757aa] active:scale-95',
          ].join(' ')}
        >
          {estopActive ? 'DURDURULDU' : 'ACİL DURDUR'}
        </button>
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
        ⚠ Yazılım E-Stop ikincildir; fiziksel mantar buton birincil ve bağımsız güvencedir.
      </p>
    </section>
  );
}
