import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { InstagramPage } from './pages/InstagramPage'
import { MatchingPage } from './pages/MatchingPage'
import { JobsPage } from './pages/JobsPage'
import { MatchOptionsProvider } from './stores/matchOptionsContext'

function App() {
  return (
    <MatchOptionsProvider>
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="instagram" element={<InstagramPage />} />
          <Route path="matching" element={<MatchingPage />} />
          <Route path="jobs" element={<JobsPage />} />
        </Route>
      </Routes>
    </Router>
    </MatchOptionsProvider>
  )
}

export default App