import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

export default function WebUsers() {
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')

  const load = () => api.get('/api/web-users').then(setUsers).catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [])

  const del = async (u) => {
    if (!window.confirm(`¿Eliminar al usuario web "${u.username}"?`)) return
    try {
      await api.del(`/api/web-users/${u.id}`)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">Usuarios Web</h1>
          <p className="sub">Quienes acceden a este panel. Roles: admin o viewer.</p>
        </div>
        <Link className="btn btn-primary" to="/usuarios-web/nuevo">Nuevo usuario web</Link>
      </div>

      {error && <div className="flash flash-err">{error}</div>}

      <div className="card">
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr><th>Usuario</th><th>Rol</th><th>Estado</th><th>Creado</th><th className="td-actions">Acciones</th></tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    {u.username}
                    <div className="muted" style={{ fontSize: 11 }}>id {u.id}</div>
                  </td>
                  <td>
                    <span className={`chip ${u.rol === 'admin' ? 'chip-admin' : 'chip-viewer'}`}>{u.rol}</span>
                  </td>
                  <td>{u.activo ? <span className="badge badge-ok">Activo</span> : <span className="badge badge-mid">Inactivo</span>}</td>
                  <td className="muted">{new Date(u.created_at).toLocaleDateString('es')}</td>
                  <td className="td-actions">
                    <Link className="btn-link" to={`/usuarios-web/${u.id}/editar`}>Editar</Link>
                    <button className="btn-link btn-link-danger" onClick={() => del(u)}>Eliminar</button>
                  </td>
                </tr>
              ))}
              {!users.length && (
                <tr className="empty"><td colSpan={5}>Sin usuarios web.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}