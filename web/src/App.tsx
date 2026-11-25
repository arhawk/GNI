import type { ReactNode } from 'react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { CommandPalette } from './components/CommandPalette'
import { ErrorBoundary } from './components/ErrorBoundary'
import { TimeFilter } from './components/TimeFilter'
import { TopSearch } from './components/TopSearch'
import { TimeWindowProvider } from './TimeWindowContext'
import { OverviewPage } from './pages/Overview'
import { EventsPage } from './pages/Events'
import { EventDetailPage } from './pages/EventDetail'
import { ReportsPage } from './pages/Reports'
import { TrendsPage } from './pages/Trends'
import { CountriesPage } from './pages/Countries'
import { AlertsPage } from './pages/Alerts'
import { SystemPage } from './pages/System'
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
                <span className="brand-sub">全球对华监测 · 当前接入五国</span>
              </div>

              <NavGroup label="监测">
                <NavLink to="/" end>
                  总览
                </NavLink>
                <NavLink to="/countries">国家与媒体监测</NavLink>
                <NavLink to="/events">新闻中心</NavLink>
              </NavGroup>

              <NavGroup label="研判">
                <NavLink to="/trends">舆情趋势分析</NavLink>
                <NavLink to="/events">事件与叙事分析</NavLink>
                <NavLink to="/alerts">异常与预警</NavLink>
              </NavGroup>

              <NavGroup label="报告">
                <NavLink to="/reports">报告中心</NavLink>
                <NavLink to="/system">系统与数据管理</NavLink>
              </NavGroup>
            </aside>

            <div className="content">
              <header className="topbar">
                <div className="topbar-brand-line">GNI · 全球对华监测</div>
                <TopSearch />
                <div className="topbar-status" title="⌘K 打开命令面板">
                  监测中 · ⌘K
                </div>
              </header>
              <TimeFilter />
              <main className="main">
                <Routes>
                  <Route path="/" element={<OverviewPage />} />
                  <Route path="/events" element={<EventsPage />} />
                  <Route path="/events/:id" element={<EventDetailPage />} />
                  <Route path="/countries" element={<CountriesPage />} />
                  <Route path="/trends" element={<TrendsPage />} />
                  <Route path="/alerts" element={<AlertsPage />} />
                  <Route path="/reports" element={<ReportsPage />} />
                  <Route path="/system" element={<SystemPage />} />
                </Routes>
              </main>
            </div>
          </div>
          <CommandPalette />
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
