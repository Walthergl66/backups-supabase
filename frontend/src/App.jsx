import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import { useAuth } from './auth.jsx'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Projects from './pages/Projects.jsx'
import ProjectForm from './pages/ProjectForm.jsx'
import ProjectHistory from './pages/ProjectHistory.jsx'
import Accounts from './pages/Accounts.jsx'
import AccountForm from './pages/AccountForm.jsx'
import Users from './pages/Users.jsx'
import UserForm from './pages/UserForm.jsx'
import WebUsers from './pages/WebUsers.jsx'
import WebUserForm from './pages/WebUserForm.jsx'
import Backups from './pages/Backups.jsx'
import Audit from './pages/Audit.jsx'
import ImportProjects from './pages/ImportProjects.jsx'

function RequireAuth({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="main"><div className="muted">Cargando…</div></div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/proyectos" element={<Projects />} />
        <Route path="/proyectos/nuevo" element={<ProjectForm />} />
        <Route path="/proyectos/:id/editar" element={<ProjectForm />} />
        <Route path="/proyectos/:id/historial" element={<ProjectHistory />} />
        <Route path="/cuentas" element={<Accounts />} />
        <Route path="/cuentas/nueva" element={<AccountForm />} />
        <Route path="/cuentas/:id/editar" element={<AccountForm />} />
        <Route path="/usuarios" element={<Users />} />
        <Route path="/usuarios/nuevo" element={<UserForm />} />
        <Route path="/usuarios/:id/editar" element={<UserForm />} />
        <Route path="/usuarios-web" element={<WebUsers />} />
        <Route path="/usuarios-web/nuevo" element={<WebUserForm />} />
        <Route path="/usuarios-web/:id/editar" element={<WebUserForm />} />
        <Route path="/backups" element={<Backups />} />
        <Route path="/importar" element={<ImportProjects />} />
        <Route path="/auditoria" element={<Audit />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}