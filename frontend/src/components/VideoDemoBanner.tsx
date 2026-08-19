import type { VideoDemoSession } from '../operatorApiClient';

export function VideoDemoBanner({ session }: { session?: VideoDemoSession }) {
  if (!session?.active) return null;
  return (
    <section className="mb-3 rounded-xl border border-[#ffbb42]/45 bg-[#ffbb42]/10 p-3 text-sm" data-testid="video-demo-banner">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <b className="text-[#ffe4ad]">VİDEO OTURUMU · {session.capability} · {session.title}</b>
        <span className="font-mono text-xs text-[#ffcf7a]">{session.runId}</span>
      </div>
      <p className="mt-1 text-[#d8c394]">Sonraki fiziksel eylem: {session.physicalActionRequired}</p>
      <p className="mt-1 text-xs text-[#b8a77b]">Bu oturum fiziksel başarı hükmü vermez; manuel işaretleme AI tespiti değildir.</p>
    </section>
  );
}
