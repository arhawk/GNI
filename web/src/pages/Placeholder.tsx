export function Placeholder({ title, note }: { title: string; note?: string }) {
  return (
    <div className="panel">
      <h2>{title}</h2>
      <p className="muted">{note ?? 'Shell placeholder — wired in a later slice.'}</p>
    </div>
  )
}
