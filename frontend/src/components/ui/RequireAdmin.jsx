import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext.jsx'

export default function RequireAdmin() {
  const { user } = useAuth()
  if (!user || user.rol !== 'admin') return <Navigate to="/" replace />
  return <Outlet />
}