import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchSearch, type SearchHit } from '../api'

const NAV = [
  { label: '总览', path: '/' },
  { label: '国家与媒体监测', path: '/countries' },
  { label: '新闻中心', path: '/events' },
  { label: '舆情趋势分析', path: '/trends' },
  { label: '异常与预警', path: '/alerts' },
  { label: '报告中心', path: '/reports' },
  { label: '系统与数据管理', path: '/system' },
]

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const navigate = useNavigate()

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    if (!open) return
    const term = q.trim()
    if (term.length < 2) {
      setHits([])
      return
    }
    let cancelled = false
    const t = window.setTimeout(() => {
      fetchSearch(term)
        .then((r) => {
          if (!cancelled) setHits(r.results || [])
        })
        .catch(() => {
          if (!cancelled) setHits([])
        })
    }, 180)
    return () => {
      cancelled = true
      window.clearTimeout(t)
    }
  }, [q, open])

  const navHits = useMemo(() => {
    const term = q.trim().toLowerCase()
    if (!term) return NAV
    return NAV.filter((n) => n.label.toLowerCase().includes(term) || n.path.includes(term))
  }, [q])

  const go = (path: string) => {
    setOpen(false)
    setQ('')
    navigate(path)
  }

  const pickHit = (h: SearchHit) => {
    setOpen(false)
    setQ('')
    if (h.href) {
      navigate(h.href)
      return
    }
    if (h.kind === 'event') {
      navigate(`/events/${h.id}`)
      return
    }
    if (h.url) window.open(h.url, '_blank', 'noopener,noreferrer')
  }

  if (!open) return null

  return (
    <div className="cmdk-backdrop" onClick={() => setOpen(false)} role="presentation">
      <div
        className="cmdk-panel"
        role="dialog"
        aria-label="命令面板"
        onClick={(e) => e.stopPropagation()}
      >
        <input
          autoFocus
          className="cmdk-input"
          placeholder="跳转页面或搜索事件/文章…（Esc 关闭）"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <div className="cmdk-section-label">页面</div>
        <ul className="cmdk-list">
          {navHits.map((n) => (
            <li key={n.path}>
              <button type="button" onClick={() => go(n.path)}>
                {n.label}
                <span className="meta">{n.path}</span>
              </button>
            </li>
          ))}
        </ul>
        {q.trim().length >= 2 && (
          <>
            <div className="cmdk-section-label">搜索结果</div>
            <ul className="cmdk-list">
              {hits.length === 0 && <li className="muted">无匹配</li>}
              {hits.map((h) => (
                <li key={`${h.kind}-${h.id}`}>
                  <button type="button" onClick={() => pickHit(h)}>
                    <span className="top-search-kind">{kindLabel(h.kind)}</span>
                    {h.title}
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  )
}

function kindLabel(k: SearchHit['kind']) {
  if (k === 'event') return '事件'
  if (k === 'article') return '文章'
  if (k === 'country') return '国家'
  return '来源'
}
