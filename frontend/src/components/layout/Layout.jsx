import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext.jsx'

const icons = {
  dash: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></svg>,
  projects: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/><path d="M12 11v10"/></svg>,
  accounts: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.5"/><path d="M12 9.5v-3M12 14.5v3"/></svg>,
  backups: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v9l3 3"/><path d="M5 15a7 7 0 1 1 2.1 5"/></svg>,
  import: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 3v12"/><path d="M7 10l5 5 5-5"/><path d="M4 19h16"/></svg>,
  tg: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 4L3 11l6 2 2 6 3-4 5 3L21 4z"/><path d="M9 13l9-7"/></svg>,
  web: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="8" r="3.5"/><path d="M5 21c.5-3.5 3-5.5 7-5.5s6.5 2 7 5.5"/></svg>,
  audit: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>,
  sec: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>,
}

const groups = [
  {
    group: null,
    items: [
      { to: '/', label: 'Dashboard', icon: icons.dash, end: true },
      { to: '/proyectos', label: 'Proyectos', icon: icons.projects },
      { to: '/cuentas', label: 'Cuentas', icon: icons.accounts },
      { to: '/backups', label: 'Backups', icon: icons.backups },
      { to: '/importar', label: 'Importar desde Supabase', icon: icons.import },
    ],
  },
  {
    group: 'Acceso',
    items: [
      { to: '/usuarios', label: 'Usuarios de Telegram', icon: icons.tg },
      { to: '/usuarios-web', label: 'Usuarios del panel', icon: icons.web },
    ],
  },
  {
    group: 'Registro',
    items: [
      { to: '/auditoria', label: 'Bitácora', icon: icons.audit },
      { to: '/seguridad', label: 'Seguridad', icon: icons.sec },
    ],
  },
]

const sectionLabels = [
  ['/proyectos', 'Proyectos'],
  ['/cuentas', 'Cuentas'],
  ['/backups', 'Backups'],
  ['/importar', 'Importar desde Supabase'],
  ['/usuarios-web', 'Usuarios del panel'],
  ['/usuarios', 'Usuarios de Telegram'],
  ['/auditoria', 'Bitácora'],
  ['/seguridad', 'Seguridad'],
]

// Rutas reservadas al rol admin (viewer solo monitorea).
const ADMIN_ROUTES = ['/cuentas', '/importar', '/usuarios', '/usuarios-web']

export default function Layout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const { pathname } = useLocation()
  const section = pathname === '/' ? 'Dashboard' : sectionLabels.find(([p]) => pathname.startsWith(p))?.[1] || ''

  const close = () => setOpen(false)
  const isAdmin = user?.rol === 'admin'
  const visibleGroups = groups
    .map((g) => ({
      ...g,
      items: g.items.filter((it) => isAdmin || !ADMIN_ROUTES.some((r) => it.to.startsWith(r))),
    }))
    .filter((g) => g.items.length > 0)

  return (
    <div className="shell">
      <aside className={`sidebar ${open ? 'open' : ''}`}>
        <div className="brand">
          <div className="brand-logo">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"><path d="M12 3v9l3 3"/><path d="M5 15a7 7 0 1 1 2.1 5"/></svg>
          </div>
          <div>
            <div className="brand-name">Supabase Backups</div>
            <div className="brand-sub">Respaldo y monitoreo</div>
          </div>
        </div>

        <nav className="nav">
          {visibleGroups.map((g, gi) => (
            <div key={gi}>
              {g.group && <div className="nav-group">{g.group}</div>}
              {g.items.map((it) => (
                <NavLink
                  key={it.to}
                  to={it.to}
                  end={it.end}
                  className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
                  onClick={close}
                >
                  {it.icon}
                  <span>{it.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="sidebar-foot">
          <span className="status-dot" />
          Operativo
          <span className="sidebar-ver">Supabase Backups · v1.0</span>
        </div>
      </aside>

      <div
        className="dimmer"
        style={{ display: open ? 'block' : 'none' }}
        aria-hidden
      />
      <div className="main-wrap">
        <header className="topbar">
          <button className="burger" onClick={() => setOpen(!open)} aria-label="Menú">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
          </button>
          {section && (
            <div className="topbar-title">
              <span className="topbar-dot" />
              {section}
            </div>
          )}
          <div className="user">
            {user && <span className="user-name muted" style={{ fontSize: 13 }}>{user.username}</span>}
            {user && <span className={`chip ${user.rol === 'admin' ? 'chip-admin' : 'chip-viewer'}`}>{user.rol === 'admin' ? 'Administrador' : 'Solo lectura'}</span>}
            <button className="btn btn-ghost btn-sm" onClick={logout}>
              Salir
            </button>
          </div>
        </header>
        <main className="main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}