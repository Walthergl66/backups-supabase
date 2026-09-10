import { Navigate } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext.jsx'

export default function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="main"><div className="muted">Cargando…</div></div>
  if (!user) return <Navigate to="/login" replace />
  return children
}