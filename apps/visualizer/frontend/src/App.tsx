import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { IdentityPage } from './pages/IdentityPage'
import { DashboardPage } from './pages/DashboardPage'
import { ImagesPage } from './pages/ImagesPage'
import { ProcessingPage } from './pages/ProcessingPage'
import { StackSuggestionsPage } from './pages/StackSuggestionsPage'
import { AnalyzeOptionsProvider } from './stores/analyzeOptionsContext'
import { ThemeProvider } from './contexts/ThemeContext'

function App() {
  return (
    <ThemeProvider>
      <AnalyzeOptionsProvider>
        <Router>
          <Routes>
            <Route path="/" element={<Layout />}>
              <Route index element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
              <Route path="images" element={<ErrorBoundary><ImagesPage /></ErrorBoundary>} />
              <Route path="search" element={<Navigate to="/images" replace />} />
              <Route path="analytics" element={<Navigate to="/images" replace />} />
              <Route path="identity" element={<ErrorBoundary><IdentityPage /></ErrorBoundary>} />
              <Route path="processing" element={<ErrorBoundary><ProcessingPage /></ErrorBoundary>} />
              <Route path="stacks/confirm" element={<ErrorBoundary><StackSuggestionsPage /></ErrorBoundary>} />
              <Route path="instagram" element={<Navigate to="/images" replace />} />
              <Route path="matching" element={<Navigate to="/processing" replace />} />
              <Route
                path="descriptions"
                element={<Navigate to={{ pathname: '/processing', search: '?tab=analyze' }} replace />}
              />
              <Route path="jobs" element={<Navigate to={{ pathname: '/processing', search: '?tab=jobs' }} replace />} />
              <Route
                path="providers"
                element={<Navigate to={{ pathname: '/processing', search: '?tab=providers' }} replace />}
              />
            </Route>
          </Routes>
        </Router>
      </AnalyzeOptionsProvider>
    </ThemeProvider>
  )
}

export default App