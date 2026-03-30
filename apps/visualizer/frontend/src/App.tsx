import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ErrorBoundary } from './components/ui/ErrorBoundary'
import { DashboardPage } from './pages/DashboardPage'
import { DescriptionsPage } from './pages/DescriptionsPage'
import { InstagramPage } from './pages/InstagramPage'
import { MatchingPage } from './pages/MatchingPage'
import { JobsPage } from './pages/JobsPage'
import { ProvidersPage } from './pages/ProvidersPage'
import { MatchOptionsProvider } from './stores/matchOptionsContext'

function App() {
  return (
    <MatchOptionsProvider>
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<ErrorBoundary><DashboardPage /></ErrorBoundary>} />
          <Route path="instagram" element={<ErrorBoundary><InstagramPage /></ErrorBoundary>} />
          <Route path="matching" element={<ErrorBoundary><MatchingPage /></ErrorBoundary>} />
          <Route path="descriptions" element={<ErrorBoundary><DescriptionsPage /></ErrorBoundary>} />
          <Route path="jobs" element={<ErrorBoundary><JobsPage /></ErrorBoundary>} />
          <Route path="providers" element={<ErrorBoundary><ProvidersPage /></ErrorBoundary>} />
        </Route>
      </Routes>
    </Router>
    </MatchOptionsProvider>
  )
}

export default App