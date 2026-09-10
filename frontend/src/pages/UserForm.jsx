import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api.js'

export default function UserForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()

  const [form, setForm] = useState({ telegram_chat_id: '', nombre: '', rol: 'usuario', activo: true })
  const [projects, setProjects] = useState([])
  const [perms, setPerms] = useState({})
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  const loadPermissions = (userId) =>
    api.get(`/api/users/${userId}`).then((u) => {
      setForm((f) => ({ ...f, rol: u.rol, activo: u.activo !== false }))
      const map = {}
      for (const p of u.permissions || []) map[p.project_id] = p
      setPerms(map)
    })

  useEffect(() => {
    api.get('/api/projects/active').then(setProjects).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!id) return
    loadPermissions(id).catch((e) => setError(e.message))
  }, [id])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setChk = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.checked }))

  const togglePerm = (pid, key) => (e) => {
    const current = perms[pid] || { can_backup: false, can_monitor: false }
    setPerms((m) => ({ ...m, [pid]: { ...current, [key]: e.target.checked } }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    try {
      let userId = id
      if (editing) {
        await api.put(`/api/users/${id}`, {
          nombre: form.nombre,
          rol: form.rol,
          activo: form.activo,
        })
      } else {
        const res = await api.post('/api/users', {
          telegram_chat_id: form.telegram_chat_id,
          nombre: form.nombre,
          rol: form.rol,
        })
        userId = res.id
      }
      if (form.rol === 'usuario') {
        await api.post(`/api/users/${userId}/permissions`, { permissions: rowsFromPerms() })
      }
      navigate('/usuarios')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setSending(false)
    }
  }

  const rowsFromPerms = () =>
    Object.entries(perms)
      .map(([project_id, v]) => ({
        project_id: Number(project_id),
        can_backup: Boolean(v.can_backup),
        can_monitor: Boolean(v.can_monitor),
      }))
      .filter((r) => r.can_backup || r.can_monitor)

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">{editing ? 'Editar usuario de Telegram' : 'Nuevo usuario de Telegram'}</h1>
          <p className="sub">Los admins pueden respaldar y monitorear todos los proyectos.</p>
        </div>
      </div>

      {error && <div className="flash flash-err">{error}</div>}

      <div className="card">
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="form-grid">
              <div className="field">
                <label className="label">Chat ID de Telegram</label>
                <input className="input mono" value={form.telegram_chat_id} onChange={set('telegram_chat_id')}
                  required={!editing} disabled={editing} placeholder="123456789" />
                <div className="hint">Es el ID numérico del chat del usuario con el bot.</div>
              </div>
              <div className="field">
                <label className="label">Nombre</label>
                <input className="input" value={form.nombre} onChange={set('nombre')} required />
              </div>
              <div className="field">
                <label className="label">Rol</label>
                <select className="select" value={form.rol} onChange={set('rol')}>
                  <option value="usuario">usuario</option>
                  <option value="admin">admin</option>
                </select>
              </div>
              <div className="field">
                <label className="check" style={{ marginTop: 26 }}>
                  <input type="checkbox" checked={form.activo} onChange={setChk('activo')} />
                  Activo
                </label>
              </div>
            </div>

            {form.rol === 'usuario' && (
              <div className="field">
                <label className="label">Permisos por proyecto</label>
                <div className="checkbox-scroll">
                  <table className="t">
                    <thead><tr><th>Proyecto</th><th style={{ textAlign: 'center' }}>Respaldo</th><th style={{ textAlign: 'center' }}>Monitorear</th></tr></thead>
                    <tbody>
                      {(projects || []).map((p) => (
                        <tr key={p.id}>
                          <td className="mono">{p.slug}</td>
                          <td style={{ textAlign: 'center' }}>
                            <input type="checkbox" checked={Boolean(perms[p.id]?.can_backup)} onChange={togglePerm(p.id, 'can_backup')} />
                          </td>
                          <td style={{ textAlign: 'center' }}>
                            <input type="checkbox" checked={Boolean(perms[p.id]?.can_monitor)} onChange={togglePerm(p.id, 'can_monitor')} />
                          </td>
                        </tr>
                      ))}
                      {!projects.length && (
                        <tr className="empty"><td colSpan={3}>No hay proyectos activos.</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="inline-actions">
              <button className="btn btn-primary" disabled={sending}>{sending ? 'Guardando…' : 'Guardar'}</button>
              <button type="button" className="btn btn-ghost" onClick={() => navigate('/usuarios')}>Cancelar</button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}