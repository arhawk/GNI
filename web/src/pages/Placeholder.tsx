export function Placeholder({ title, note }: { title: string; note?: string }) {
  return (
    <div className="panel">
      <h2>{title}</h2>
      <p className="muted">{note ?? '总纲已规划，本页尚未实现。'}</p>
    </div>
  )
}
