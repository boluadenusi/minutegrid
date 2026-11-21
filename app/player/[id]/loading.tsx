// Shown instantly while a player page renders: the 90 minutes light up in order, on a loop.
export default function Loading() {
  return (
    <main className="player-loading" role="status" aria-live="polite">
      <div className="player-loading-grid" aria-hidden>
        {Array.from({ length: 90 }, (_, i) => (
          <span key={i} style={{ animationDelay: `${i * 18}ms` }} />
        ))}
      </div>
      <p className="player-loading-text">Warming up the grid…</p>
    </main>
  );
}
