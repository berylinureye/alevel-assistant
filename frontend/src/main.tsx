import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router'
import './index.css'
import App from './App.tsx'
import LandingPage from './pages/landing/LandingPage.tsx'
import { AgentStepReplayPage } from './pages/AgentStepReplayPage.tsx'
import { QuestionCardReplayPage } from './pages/QuestionCardReplayPage.tsx'
import { LargePdfReplayPage } from './pages/LargePdfReplayPage.tsx'
import { PracticeRecommendationsReplayPage } from './pages/PracticeRecommendationsReplayPage.tsx'
import { UIDirectionDemosPage } from './pages/UIDirectionDemosPage.tsx'
import { OpenDesignDemosPage } from './pages/OpenDesignDemosPage.tsx'
import { ErrorBoundary } from './components/ErrorBoundary.tsx'
import { trackEvent } from './api/client'

// 进入站点记录一次 page view，包含基本环境信息
trackEvent('ui_page_view', {
  path: location.pathname,
  ua: navigator.userAgent.slice(0, 200),
  viewport: `${window.innerWidth}x${window.innerHeight}`,
  lang: navigator.language,
})

// 全局 JS 错误捕获
window.addEventListener('error', (e) => {
  trackEvent('ui_error', {
    kind: 'error',
    message: String(e.message || '').slice(0, 300),
    source: String(e.filename || '').slice(0, 200),
    lineno: e.lineno,
  })
})
window.addEventListener('unhandledrejection', (e) => {
  trackEvent('ui_error', {
    kind: 'unhandledrejection',
    message: String((e.reason && (e.reason.message || e.reason)) || '').slice(0, 300),
  })
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          {import.meta.env.DEV ? (
            <Route path="/__agent-step-replay" element={<AgentStepReplayPage />} />
          ) : null}
          {import.meta.env.DEV ? (
            <Route path="/__question-card-replay" element={<QuestionCardReplayPage />} />
          ) : null}
          {import.meta.env.DEV ? (
            <Route path="/__large-pdf-replay" element={<LargePdfReplayPage />} />
          ) : null}
          {import.meta.env.DEV ? (
            <Route path="/__practice-recommendations-replay" element={<PracticeRecommendationsReplayPage />} />
          ) : null}
          <Route path="/__ui-direction-demos" element={<UIDirectionDemosPage />} />
          <Route path="/__open-design-demos" element={<OpenDesignDemosPage />} />
          <Route path="/landing" element={<LandingPage />} />
          <Route path="*" element={<App />} />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  </StrictMode>,
)
