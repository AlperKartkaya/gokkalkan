import type { CommandResult } from '../operatorContracts';

function commandLabel(result: CommandResult) {
  if (result.kind === 'FireIntent') return 'FireIntent';
  if (result.kind === 'ManualAimCommand') return 'ManualAimCommand';
  if (result.kind === 'StageRequest') return 'StageRequest';
  return 'ModeRequest';
}

export function EventStream({ commandResults }: { commandResults: CommandResult[] }) {
  return (
    <section className="rounded-xl border border-white/[.08] bg-[rgba(7,10,14,.94)] p-4" aria-label="Olay akışı">
      <h2 className="m-0 text-xl font-black">Olay akışı</h2>
      <div className="mt-3 grid max-h-80 gap-2 overflow-auto pr-1">
        {commandResults.length === 0 && <p className="m-0 rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm text-[#91a6b7]">Henüz komut sonucu yok.</p>}
        {commandResults.map((result) => (
          <article key={result.commandId} className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm">
            <b className={result.accepted ? 'text-[#bfffe0]' : 'text-[#ffbdc4]'}>{commandLabel(result)} · {result.accepted ? 'Kabul' : 'Blok'}</b>
            <p className="m-0 mt-1 text-[#c8d8e2]">{result.message}</p>
            <small className="mt-1 block text-[#91a6b7]">{result.createdAt ? new Date(result.createdAt).toISOString() : ''}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
