import type { OperatorTrackState } from '../operatorContracts';

export function TrackList({
  tracks,
  selectedTrackId,
  authoritativeTargetId,
  onSelect,
}: {
  tracks: OperatorTrackState[];
  selectedTrackId: string;
  authoritativeTargetId: string;
  onSelect: (trackId: string) => void;
}) {
  return (
    <section
      className="rounded-xl border border-[#48a8ff]/18 bg-[rgba(7,10,14,.94)] p-3 flex flex-col flex-1 min-h-[180px]"
      data-testid="operator-track-list"
      aria-label="Backend ve perception hedef izleri"
    >
      <div className="flex items-center justify-between gap-2">
        <b className="text-sm text-[#d7efff]">Tespit Edilen Hedefler (Tracks)</b>
        <span className="text-xs text-[#91a6b7]">{tracks.length} iz</span>
      </div>
      {tracks.length === 0 ? (
        <p className="m-0 mt-2 text-xs font-bold text-[#ffbdc4]">
          Backend track yayınlamıyor; UI sentetik hedef üretmedi.
        </p>
      ) : (
        <div className="mt-2 grid gap-3 overflow-auto flex-1 min-h-0 max-h-64 p-1">
          {tracks.map((track) => {
            const selected = track.trackId === selectedTrackId;
            const authoritative = track.trackId === authoritativeTargetId;
            const isFoe = track.friendFoe?.toLowerCase() === 'düşman';
            const isFriend = track.friendFoe?.toLowerCase() === 'dost';

            let bgClass = 'bg-white/[.04] hover:bg-white/[.08]';
            if (isFoe) bgClass = 'bg-[#ff4757]/10 hover:bg-[#ff4757]/15';
            else if (isFriend) bgClass = 'bg-[#25d8ff]/10 hover:bg-[#25d8ff]/15';

            let borderClass = 'border-white/10';
            let shadowClass = '';
            
            if (authoritative) {
              borderClass = 'border-[#33e68c] ring-1 ring-[#33e68c]';
              shadowClass = 'shadow-[0_0_20px_rgba(51,230,140,0.4)] z-10 relative';
            } else if (selected) {
              borderClass = 'border-[#ffbb42]/60';
            }

            return (
              <button
                type="button"
                key={track.trackId}
                onClick={() => onSelect(track.trackId)}
                className={`rounded-lg border p-2.5 text-left transition-all ${bgClass} ${borderClass} ${shadowClass}`}
                data-testid={`operator-track-row-${track.trackId}`}
              >
                <div className="flex justify-between items-start gap-3">
                  <div className="flex flex-col gap-2 flex-1 overflow-hidden">
                    <div className="flex flex-col gap-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <b className="text-[#eaf7ff] text-xs font-mono break-all leading-tight">{track.trackId}</b>
                        {authoritative && (
                          <strong className="rounded border border-[#33e68c]/35 bg-[#33e68c]/10 px-1.5 py-0.5 text-[8px] font-black tracking-wide text-[#69f0ae]">
                            BACKEND ÖNCELİĞİ
                          </strong>
                        )}
                      </div>
                      
                      <div className="w-full flex items-center gap-1.5 mt-0.5">
                        <span className="text-[#5a7a8a] text-[8px] uppercase tracking-widest font-bold">Tür</span>
                        <div className="flex-1 bg-white/10 h-1.5 rounded-full overflow-hidden flex">
                          <div 
                            className={`h-full transition-all duration-500 ${(track.typeConfidence ?? track.confidence) > 0.8 ? 'bg-[#33e68c] shadow-[0_0_8px_#33e68c]' : 'bg-[#ffbb42] shadow-[0_0_8px_#ffbb42]'}`}
                            style={{ width: `${Math.round((track.typeConfidence ?? track.confidence) * 100)}%` }}
                          />
                        </div>
                        <span className="text-[#c8d8e2] text-[9px] font-mono" data-testid={`operator-track-type-confidence-${track.trackId}`}>{Math.round((track.typeConfidence ?? track.confidence) * 100)}%</span>
                      </div>
                      {track.friendFoeConfidence != null && (
                        <div className="w-full flex items-center gap-1.5">
                          <span className="text-[#5a7a8a] text-[8px] uppercase tracking-widest font-bold">Renk</span>
                          <div className="flex-1 bg-white/10 h-1.5 rounded-full overflow-hidden">
                            <div className="h-full bg-[#25d8ff] transition-all duration-500" style={{ width: `${Math.round(track.friendFoeConfidence * 100)}%` }} />
                          </div>
                          <span className="text-[#c8d8e2] text-[9px] font-mono" data-testid={`operator-track-color-confidence-${track.trackId}`}>{Math.round(track.friendFoeConfidence * 100)}%</span>
                        </div>
                      )}
                    </div>
                    
                    {track.courseState && (
                      <span
                        className={`block text-[10px] leading-tight ${track.courseState.insidePoligon ? 'text-[#48a8ff]' : 'text-[#ffbdc4]/70'}`}
                        data-testid={`operator-course-state-${track.trackId}`}
                      >
                        {track.courseState.insidePoligon && track.courseState.routeNumber
                          ? `R${track.courseState.routeNumber} / Geçiş ${track.courseState.passIndex}`
                          : 'Poligon dışı'}
                      </span>
                    )}
                  </div>

                  <div className="flex flex-col items-end shrink-0 rounded bg-black/20 p-1.5 border border-white/5">
                    <div className="flex gap-3 text-[10px] font-mono text-[#c8d8e2]">
                      <div className="flex flex-col items-end">
                        <span className="text-[#5a7a8a] text-[8.5px] uppercase tracking-wider">Menzil</span>
                        <span>{track.rangeM.toFixed(1)}m</span>
                      </div>
                      <div className="flex flex-col items-end">
                        <span className="text-[#5a7a8a] text-[8.5px] uppercase tracking-wider">Açı</span>
                        <span>{track.bearingDeg.toFixed(1)}°</span>
                      </div>
                    </div>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
