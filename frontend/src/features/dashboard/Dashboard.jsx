import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

const tiles = [
  ['proyectos', 'Proyectos activos', 'projects', '#22d3ee'],
  ['cuentas', 'Cuentas', 'accounts', '#a78bfa'],
  ['usuarios_telegram', 'Usuarios Telegram', 'tg', '#34d399'],
  ['backups_ok', 'Backups OK', 'ok', '#34d399'],
  ['backups_error', 'Backups con error', 'err', '#fb7185'],
]

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/api/dashboard').then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="flash flash-err">{error}</div>
  if (!data) return <div className="muted">Cargando…</div>

  const d = data.dashboard
  const bySlug = (slug) => d.projects.find((p) => p.slug === slug)

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">Dashboard</h1>
          <p className="sub">Resumen del sistema de respaldo de Supabase.</p>
        </div>
      </div>

      <div className="grid grid-stat">
        {tiles.map(([key, label, icon, color]) => (
          <div className="card stat" key={key}>
            <div className="stat-ico" style={{ background: `${color}22`, color }}>
              {icon === 'projects' && <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 7l9-4 9 4-9 4-9-4z"/><path d="M3 7v10l9 4 9-4V7"/></svg>}
              {icon === 'accounts' && <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.5"/></svg>}
              {icon === 'tg' && <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 4L3 11l6 2 2 6 3-4 5 3L21 4z"/></svg>}
              {icon === 'ok' && <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M8 12l3 3 5-6"/></svg>}
              {icon === 'err' && <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9"/><path d="M12 8v5"/><path d="M12 16h.01"/></svg>}
            </div>
            <div>
              <div className="stat-lbl">{label}</div>
              <div className="stat-val">{d[key] ?? 0}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid-2 grid">
        <div className="card">
          <div className="card-head">
            <span className="card-title">Proyectos activos</span>
            <Link className="btn-link" to="/proyectos">Ver todos</Link>
          </div>
          <div className="table-scroll card-body" style={{ padding: 0 }}>
            <table className="t">
              <thead>
                <tr><th>Proyecto</th><th>Último backup</th><th>Tamaño</th><th>Estado</th></tr>
              </thead>
              <tbody>
                {(d.projects || []).map((p) => {
                  const ultimo = p.ultimo_backup
                  return (
                    <tr key={p.id}>
                      <td>
                        <Link className="btn-link" to={`/proyectos/${p.id}/historial`}>{p.slug}</Link>
                        <div className="muted" style={{ fontSize: 11 }}>{p.nombre}</div>
                      </td>
                      <td className="muted">{ultimo ? new Date(ultimo).toLocaleString('es') : 'Sin backups'}</td>
                      <td className="mono">-</td>
                      <td>
                        {!ultimo ? (
                          <span className="badge badge-mid">Pendiente</span>
                        ) : (
                          <span className="badge badge-ok">OK</span>
                        )}
                      </td>
                    </tr>
                  )
                })}
                {!d.projects?.length && (
                  <tr className="empty"><td colSpan={4}>No hay proyectos activos. Puedes <Link className="btn-link" to="/importar">importarlos</Link> o crearlos manualmente.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <span className="card-title">Actividad reciente</span>
            <Link className="btn-link" to="/auditoria">Ver log</Link>
          </div>
          <div className="table-scroll card-body" style={{ padding: 0 }}>
            <table className="t">
              <thead><tr><th>Fecha</th><th>Acción</th></tr></thead>
              <tbody>
                {(data.recent_audit || []).map((a) => (
                  <tr key={a.id}>
                    <td className="muted">{new Date(a.fecha).toLocaleString('es')}</td>
                    <td>
                      <span className={`badge ${a.resultado === 'ok' ? 'badge-ok' : 'badge-err'}`}>{a.resultado}</span>
                      <div style={{ fontSize: 12 }} className="mono">{a.accion}</div>
                    </td>
                  </tr>
                ))}
                {!data.recent_audit?.length && (
                  <tr className="empty"><td colSpan={2}>Sin actividad registrada.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </>
  )
}