import type { ReactNode } from 'react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { TimeFilter } from './components/TimeFilter'
import { TimeWindowProvider } from './TimeWindowContext'
import { OverviewPage } from './pages/Overview'
import { EventsPage } from './pages/Events'
import { EventDetailPage } from './pages/EventDetail'
import { Placeholder } from './pages/Placeholder'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <TimeWindowProvider>
        <ErrorBoundary>
          <div className="shell">
            <aside className="nav">
              <div className="brand">
                <span className="brand-mark">GNI</span>
                <span className="brand-sub">Event Intelligence</span>
              </div>

              <NavGroup label="Monitoring">
                <NavLink to="/" end>
                  Overview
                </NavLink>
                <NavLink to="/countries">Countries & media</NavLink>
                <NavLink to="/events">News & Events</NavLink>
              </NavGroup>

              <NavGroup label="Intelligence">
                <NavLink to="/trends">Trends</NavLink>
                <NavLink to="/events">Events & narratives</NavLink>
                <NavLink to="/alerts">Alerts</NavLink>
              </NavGroup>

              <NavGroup label="Reports">
                <NavLink to="/reports">Report center</NavLink>
                <NavLink to="/system">Sources & quality</NavLink>
              </NavGroup>
            </aside>

            <div className="content">
              <TimeFilter />
              <main className="main">
                <Routes>
                  <Route path="/" element={<OverviewPage />} />
                  <Route path="/events" element={<EventsPage />} />
                  <Route path="/events/:id" element={<EventDetailPage />} />
                  <Route
                    path="/countries"
                    element={
                      <Placeholder
                        title="Countries & media"
                        note="List + detail tabs; country ↔ media switch. No alignment-colored globe."
                      />
                    }
                  />
                  <Route path="/trends" element={<Placeholder title="Trends" />} />
                  <Route path="/alerts" element={<Placeholder title="Alerts" />} />
                  <Route path="/reports" element={<Placeholder title="Report center" />} />
                  <Route path="/system" element={<Placeholder title="Sources & quality" />} />
                </Routes>
              </main>
            </div>
          </div>
        </ErrorBoundary>
      </TimeWindowProvider>
    </BrowserRouter>
  )
}

function NavGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="nav-group">
      <div className="nav-group-label">{label}</div>
      {children}
    </div>
  )
}
