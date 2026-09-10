import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/layout/Layout.jsx'
import RequireAuth from './components/ui/RequireAuth.jsx'
import Login from './features/login/Login.jsx'
import Dashboard from './features/dashboard/Dashboard.jsx'
import Projects from './features/projects/Projects.jsx'
import ProjectForm from './features/projects/ProjectForm.jsx'
import ProjectHistory from './features/projects/ProjectHistory.jsx'
import Accounts from './features/accounts/Accounts.jsx'
import AccountForm from './features/accounts/AccountForm.jsx'
import Users from './features/users/Users.jsx'
import UserForm from './features/users/UserForm.jsx'
import WebUsers from './features/web-users/WebUsers.jsx'
import WebUserForm from './features/web-users/WebUserForm.jsx'
import Backups from './features/backups/Backups.jsx'
import Audit from './features/audit/Audit.jsx'
import ImportProjects from './features/imports/ImportProjects.jsx'

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