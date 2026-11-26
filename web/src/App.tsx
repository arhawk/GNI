import type { ReactNode } from 'react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { CommandPalette } from './components/CommandPalette'
import { ErrorBoundary } from './components/ErrorBoundary'
import { EvidenceProvider } from './components/EvidenceContext'
import { TimeFilter } from './components/TimeFilter'
import { TopSearch } from './components/TopSearch'
import { TimeWindowProvider } from './TimeWindowContext'
import { OverviewPage } from './pages/Overview'
import { EventsPage } from './pages/Events'
import { EventDetailPage } from './pages/EventDetail'
import { ReportsPage } from './pages/Reports'
import { TopicsPage } from './pages/Topics'
import { TrendsPage } from './pages/Trends'
import { CountriesPage } from './pages/Countries'
import { NarrativesPage } from './pages/Narratives'
import { SentimentStancePage } from './pages/SentimentStance'
import { OutlookPage } from './pages/Outlook'
import { ExplorerPage } from './pages/Explorer'
import { ArticleDetailPage } from './pages/ArticleDetail'
import { AlertsPage } from './pages/Alerts'
import { SystemPage } from './pages/System'
import './App.css'

export default function App() {
  return (
    <BrowserRouter>
      <TimeWindowProvider>
        <EvidenceProvider>
          <ErrorBoundary>
            <div className="shell">
              <aside className="nav">
                <div className="brand">
                  <span className="brand-mark">GNI</span>
                  <span className="brand-sub">Global Narrative Intelligence</span>
                </div>

                <NavGroup label="情报总览与报告">
                  <NavLink to="/" end>
                    Global Dashboard
                  </NavLink>
                  <NavLink to="/reports">每日情报简报</NavLink>
                  <NavLink to="/outlook">展望与观察清单</NavLink>
                </NavGroup>

                <NavGroup label="多维研判分析">
                  <NavLink to="/events">事件分析</NavLink>
                  <NavLink to="/topics">议题分析 (4×15)</NavLink>
                  <NavLink to="/countries">国家比较</NavLink>
                  <NavLink to="/narratives">叙事分析</NavLink>
                  <NavLink to="/stance">情感与对华立场</NavLink>
                </NavGroup>

                <NavGroup label="证据追溯与运维">
                  <NavLink to="/explorer">文章与证据浏览器</NavLink>
                  <NavLink to="/trends">历史趋势</NavLink>
                  <NavLink to="/alerts">异常与预警</NavLink>
                  <NavLink to="/system">系统与数据管理</NavLink>
                </NavGroup>
              </aside>

              <div className="content">
                <header className="topbar">
                  <div className="topbar-brand-line">GNI · Global Intelligence Presentation</div>
                  <TopSearch />
                  <div className="topbar-status" title="⌘K 打开命令面板">
                    监测中 · ⌘K
                  </div>
                </header>
                <TimeFilter />
                <main className="main">
                  <Routes>
                    <Route path="/" element={<OverviewPage />} />
                    <Route path="/reports" element={<ReportsPage />} />
                    <Route path="/events" element={<EventsPage />} />
                    <Route path="/events/:id" element={<EventDetailPage />} />
                    <Route path="/topics" element={<TopicsPage />} />
                    <Route path="/countries" element={<CountriesPage />} />
                    <Route path="/narratives" element={<NarrativesPage />} />
                    <Route path="/stance" element={<SentimentStancePage />} />
                    <Route path="/outlook" element={<OutlookPage />} />
                    <Route path="/explorer" element={<ExplorerPage />} />
                    <Route path="/articles/:id" element={<ArticleDetailPage />} />
                    <Route path="/trends" element={<TrendsPage />} />
                    <Route path="/alerts" element={<AlertsPage />} />
                    <Route path="/system" element={<SystemPage />} />
                  </Routes>
                </main>
              </div>
            </div>
            <CommandPalette />
          </ErrorBoundary>
        </EvidenceProvider>
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
