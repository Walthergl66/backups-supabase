import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteWebUser, listWebUsers } from '../../services/webUsers.js'
import { fmtFechaDate } from '../../utils/format.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'
import Badge from '../../components/ui/Badge.jsx'

export default function WebUsers() {
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')

  const load = () => listWebUsers().then(setUsers).catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [])

  const del = async (u) => {
    if (!window.confirm(`¿Eliminar al usuario web "${u.username}"?`)) return
    try {
      await deleteWebUser(u.id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <PageHead title="Usuarios Web" sub="Personas con acceso al panel: administran todo o solo consultan.">
        <Link className="btn btn-primary" to="/usuarios-web/nuevo">Nuevo usuario web</Link>
      </PageHead>

      {error && <Flash type="err">{error}</Flash>}

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
                    <span className={`chip ${u.rol === 'admin' ? 'chip-admin' : 'chip-viewer'}`}>{u.rol === 'admin' ? 'Administrador' : 'Solo lectura'}</span>
                  </td>
                  <td>
                    {u.activo ? <Badge tone="ok">Activo</Badge> : <Badge tone="mid">Inactivo</Badge>}
                    {' '}
                    {u.totp_enabled ? <Badge tone="ok">2FA</Badge> : null}
                  </td>
                  <td className="muted">{fmtFechaDate(u.created_at)}</td>
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