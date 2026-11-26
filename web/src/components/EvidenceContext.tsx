import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { EvidenceDrawer } from './EvidenceDrawer'

type EvidenceContextValue = {
  openEvidence: (id: string) => void
  closeEvidence: () => void
}

const EvidenceContext = createContext<EvidenceContextValue>({
  openEvidence: () => {},
  closeEvidence: () => {},
})

export function EvidenceProvider({ children }: { children: ReactNode }) {
  const [activeId, setActiveId] = useState<string | null>(null)
  const openEvidence = useCallback((id: string) => {
    if (id && id.trim()) setActiveId(id.trim())
  }, [])
  const closeEvidence = useCallback(() => setActiveId(null), [])

  return (
    <EvidenceContext.Provider value={{ openEvidence, closeEvidence }}>
      {children}
      {activeId && <EvidenceDrawer evidenceId={activeId} onClose={closeEvidence} />}
    </EvidenceContext.Provider>
  )
}

export function useEvidenceDrawer() {
  return useContext(EvidenceContext)
}
