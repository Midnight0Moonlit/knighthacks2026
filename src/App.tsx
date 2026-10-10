import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import StartPage from './pages/StartPage';
import BudgetPage from './pages/BudgetPage';
import './App.css';

function App() {
  return (
      <Router>
        <div className="ipad-viewport">
          <Routes>
            <Route path="/" element={<StartPage/>} />
            <Route path="/budget" element={<BudgetPage/>} />
          </Routes>
        </div>
      </Router>
  )
}

export default App
