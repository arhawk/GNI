import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchSearch, type SearchHit } from '../api'

export function TopSearch() {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const boxRef = useRef<HTMLDivElement | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  useEffect(() => {
    const term = q.trim()
    if (term.length < 2) {
      setHits([])
      return
    }
    let cancelled = false
    const t = window.setTimeout(() => {
      setLoading(true)
      fetchSearch(term)
        .then((r) => {
          if (!cancelled) {
            setHits(r.results || [])
            setOpen(true)
          }
        })
        .catch(() => {
          if (!cancelled) setHits([])
        })
        .finally(() => {
          if (!cancelled) setLoading(false)
        })
    }, 220)
    return () => {
      cancelled = true
      window.clearTimeout(t)
    }
  }, [q])

  const onPick = (hit: SearchHit) => {
    setOpen(false)
    setQ('')
    if (hit.kind === 'event') {
      navigate(`/events/${hit.id}`)
      return
    }
    if (hit.url) {
      window.open(hit.url, '_blank', 'noopener,noreferrer')
    }
  }

  return (
    <div className="top-search" ref={boxRef}>
      <input
        type="search"
        className="top-search-input"
        placeholder="搜索国家、媒体、事件、文章…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => hits.length > 0 && setOpen(true)}
        aria-label="全局搜索"
      />
      {open && (loading || hits.length > 0 || q.trim().length >= 2) && (
        <ul className="top-search-dropdown" role="listbox">
          {loading && <li className="muted">搜索中…</li>}
          {!loading && hits.length === 0 && <li className="muted">无匹配结果</li>}
          {!loading &&
            hits.map((h) => (
              <li key={`${h.kind}-${h.id}`}>
                <button type="button" className="top-search-hit" onClick={() => onPick(h)}>
                  <span className="top-search-kind">{h.kind === 'event' ? '事件' : '文章'}</span>
                  <span className="top-search-title">{h.title}</span>
                  {h.subtitle && <span className="meta">{h.subtitle}</span>}
                </button>
              </li>
            ))}
        </ul>
      )}
    </div>
  )
}
