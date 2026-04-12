import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { AnalyticsPage } from './pages/AnalyticsPage'
import { DashboardPage } from './pages/DashboardPage'
import { ImagesPage } from './pages/ImagesPage'
import { ProcessingPage } from './pages/ProcessingPage'
import { MatchOptionsProvider } from './stores/matchOptionsContext'
import { ThemeProvider } from './contexts/ThemeContext'

function App() {
  return (
    <ThemeProvider>
      <MatchOptionsProvider>
        <Router>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
              <Route path="images" element={<ErrorBoundary><ImagesPage /></ErrorBoundary>} />
              <Route path="analytics" element={<ErrorBoundary><AnalyticsPage /></ErrorBoundary>} />
              <Route path="processing" element={<ErrorBoundary><ProcessingPage /></ErrorBoundary>} />
              <Route path="instagram" element={<Navigate to="/images" replace />} />
              <Route path="matching" element={<Navigate to="/processing" replace />} />
              <Route
                path="descriptions"
                element={<Navigate to={{ pathname: '/processing', search: '?tab=descriptions' }} replace />}
              />
              <Route path="jobs" element={<Navigate to={{ pathname: '/processing', search: '?tab=jobs' }} replace />} />
              <Route
                path="providers"
                element={<Navigate to={{ pathname: '/processing', search: '?tab=providers' }} replace />}
              />
            </Route>
          </Routes>
        </Router>
      </MatchOptionsProvider>
    </ThemeProvider>
  )
}

export default App