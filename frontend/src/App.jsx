import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Composants from './pages/Composants'
import Matieres from './pages/Matieres'
import PiecesExternes from './pages/PiecesExternes'
import Services from './pages/Services'

function PrivateRoute({ children }) {
  const token = localStorage.getItem('token')
  return token ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/composants" element={<PrivateRoute><Composants /></PrivateRoute>} />
        <Route path="/matieres" element={<PrivateRoute><Matieres /></PrivateRoute>} />
        <Route path="/pieces-ext" element={<PrivateRoute><PiecesExternes /></PrivateRoute>} />
        <Route path="/services" element={<PrivateRoute><Services /></PrivateRoute>} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
