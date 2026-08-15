import type { ReactNode } from 'react';

export default function Navigation({
  activeSurface,
  onOpenOperator,
  onOpenAI,
  children,
}: {
  activeSurface: 'operator' | 'ai';
  onOpenOperator: () => void;
  onOpenAI: () => void;
  children?: ReactNode;
}) {
  const tabClass = (active: boolean, activeClass: string) =>
    `px-3 py-1.5 rounded-lg text-sm font-bold transition-colors ${
      active ? activeClass : 'text-[#8ba7be] hover:bg-white/5'
    }`;

  return (
    <nav className="fixed top-0 left-0 w-full z-50 flex items-center justify-between p-3 bg-[rgba(7,10,14,.9)] border-b border-[#48a8ff]/20 backdrop-blur-md">
      <div className="flex items-center gap-4">
        <div className="font-black text-[#d7efff] mr-2 flex items-center">
          Gökkalkan <span className="ml-2 text-xs rounded border border-[#ffbb42]/25 bg-[#ffbb42]/10 px-1 text-[#ffe4ad]">UI</span>
        </div>
        <button
          type="button"
          onClick={onOpenOperator}
          aria-current={activeSurface === 'operator' ? 'page' : undefined}
          className={tabClass(activeSurface === 'operator', 'bg-[#48a8ff]/20 text-[#cbe9ff] border border-[#48a8ff]/30')}
        >
          Operatör Paneli
        </button>
        <button
          type="button"
          onClick={onOpenAI}
          aria-current={activeSurface === 'ai' ? 'page' : undefined}
          className={tabClass(activeSurface === 'ai', 'bg-[#33e68c]/20 text-[#bfffe0] border border-[#33e68c]/30')}
        >
          Yapay Zeka / Algı
        </button>
      </div>
      {children && <div className="flex items-center gap-3">{children}</div>}
    </nav>
  );
}
