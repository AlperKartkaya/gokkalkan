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
      className="mt-3 rounded-xl border border-[#48a8ff]/18 bg-[rgba(7,10,14,.94)] p-3"
      data-testid="operator-track-list"
      aria-label="Backend ve perception hedef izleri"
    >
      <div className="flex items-center justify-between gap-2">
        <b className="text-sm text-[#d7efff]">Track Listesi</b>
        <span className="text-xs text-[#91a6b7]">{tracks.length} iz</span>
      </div>
      {tracks.length === 0 ? (
        <p className="m-0 mt-2 text-xs font-bold text-[#ffbdc4]">
          Backend track yayınlamıyor; UI sentetik hedef üretmedi.
        </p>
      ) : (
        <div className="mt-2 grid max-h-48 gap-2 overflow-auto">
          {tracks.map((track) => {
            const selected = track.trackId === selectedTrackId;
            const authoritative = track.trackId === authoritativeTargetId;
            return (
              <button
                type="button"
                key={track.trackId}
                onClick={() => onSelect(track.trackId)}
                className={`rounded-lg border p-2 text-left text-xs ${
                  selected
                    ? 'border-[#ffbb42]/45 bg-[#ffbb42]/10'
                    : 'border-white/10 bg-white/[.04]'
                }`}
                data-testid={`operator-track-row-${track.trackId}`}
              >
                <span className="flex justify-between gap-2">
                  <b className="truncate text-[#eaf7ff]">{track.trackId}</b>
                  <strong className={authoritative ? 'text-[#33e68c]' : 'text-[#91a6b7]'}>
                    {authoritative ? 'BACKEND ÖNCELİĞİ' : track.friendFoe}
                  </strong>
                </span>
                <span className="mt-1 block text-[#91a6b7]">
                  {track.rangeM.toFixed(1)} m · {track.bearingDeg.toFixed(1)}° · güven {Math.round(track.confidence * 100)}%
                </span>
              </button>
            );
          })}
        </div>
      )}
    </section>
  );
}
