import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteUser, listUsers } from '../../services/users.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'

export default function Users() {
  const [users, setUsers] = useState([])
  const [error, setError] = useState('')

  const load = () => listUsers().then(setUsers).catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [])

  const del = async (u) => {
    if (!window.confirm(`¿Eliminar al usuario de Telegram "${u.nombre}"?`)) return
    try {
      await deleteUser(u.id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <PageHead title="Usuarios de Telegram" sub="Personas que pueden operar el bot desde Telegram.">
        <Link className="btn btn-primary" to="/usuarios/nuevo">Nuevo usuario</Link>
      </PageHead>

      {error && <Flash type="err">{error}</Flash>}

      <div className="card">
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr><th>Nombre</th><th>Chat ID</th><th>Rol</th><th>Acceso</th><th className="td-actions">Acciones</th></tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 600 }}>{u.nombre}</td>
                  <td className="mono">{u.telegram_chat_id}</td>
                  <td>
                    <span className={`chip ${u.rol === 'admin' ? 'chip-admin' : 'chip-viewer'}`}>{u.rol}</span>
                  </td>
                  <td className="muted" style={{ fontSize: 12 }}>{u.proyectos_puede || (u.es_admin ? 'Todos' : '—')}</td>
                  <td className="td-actions">
                    <Link className="btn-link" to={`/usuarios/${u.id}/editar`}>Editar</Link>
                    <button className="btn-link btn-link-danger" onClick={() => del(u)}>Eliminar</button>
                  </td>
                </tr>
              ))}
              {!users.length && (
                <tr className="empty"><td colSpan={5}>Sin usuarios de Telegram. Puedes crearlos al <Link className="btn-link" to="/importar">importar proyectos</Link>.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}