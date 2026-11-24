import type { ReactNode } from 'react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { ErrorBoundary } from './components/ErrorBoundary'
import { TimeFilter } from './components/TimeFilter'
import { TopSearch } from './components/TopSearch'
import { TimeWindowProvider } from './TimeWindowContext'
import { OverviewPage } from './pages/Overview'
import { EventsPage } from './pages/Events'
import { EventDetailPage } from './pages/EventDetail'
import { ReportsPage } from './pages/Reports'
import { Placeholder } from './pages/Placeholder'
import './App.css'

const PLANNED = '总纲已规划，本页尚未实现业务功能。'

export default function App() {
  return (
    <BrowserRouter>
      <TimeWindowProvider>
        <ErrorBoundary>
          <div className="shell">
            <aside className="nav">
              <div className="brand">
                <span className="brand-mark">GNI</span>
                <span className="brand-sub">全球叙事智能</span>
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
                <div className="topbar-brand-line">GNI · 对华舆情监测</div>
                <TopSearch />
                <div className="topbar-status" title="本地监测面板">
                  监测中
                </div>
              </header>
              <TimeFilter />
              <main className="main">
                <Routes>
                  <Route path="/" element={<OverviewPage />} />
                  <Route path="/events" element={<EventsPage />} />
                  <Route path="/events/:id" element={<EventDetailPage />} />
                  <Route
                    path="/countries"
                    element={
                      <Placeholder title="国家与媒体监测" note={`${PLANNED} 将支持国家↔媒体切换列表。`} />
                    }
                  />
                  <Route
                    path="/trends"
                    element={
                      <Placeholder title="舆情趋势分析" note={`${PLANNED} 将展示关注度与情感走势。`} />
                    }
                  />
                  <Route
                    path="/alerts"
                    element={
                      <Placeholder title="异常与预警" note={`${PLANNED} 舆情异常与源质量分区展示。`} />
                    }
                  />
                  <Route path="/reports" element={<ReportsPage />} />
                  <Route
                    path="/system"
                    element={
                      <Placeholder title="系统与数据管理" note={`${PLANNED} 来源健康与数据质量面板。`} />
                    }
                  />
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
