import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Layout } from './components/Layout'
import { JobsPage } from './pages/JobsPage'

function Dashboard() {
  return <div>Dashboard - Coming Soon</div>
}

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="instagram" element={<div>Instagram - Coming Soon</div>} />
          <Route path="matching" element={<div>Matching - Coming Soon</div>} />
          <Route path="jobs" element={<JobsPage />} />
        </Route>
      </Routes>
    </Router>
  )
}

export default App