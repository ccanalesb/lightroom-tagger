import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<div className="p-8"><h1 className="text-2xl font-bold">Lightroom Tagger</h1></div>} />
      </Routes>
    </Router>
  )
}

export default App