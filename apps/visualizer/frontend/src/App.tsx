import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { DashboardPage } from './pages/DashboardPage'
import { InstagramPage } from './pages/InstagramPage'
import { MatchingPage } from './pages/MatchingPage'
import { JobsPage } from './pages/JobsPage'

function App() {
  return (
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
  )
}

export default App