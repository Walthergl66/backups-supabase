import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { createUser, getUser, saveUserPermissions, updateUser } from '../../services/users.js'
import { listActiveProjects } from '../../services/projects.js'
import { ApiError } from '../../services/http.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'

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
    getUser(userId).then((u) => {
      setForm((f) => ({ ...f, rol: u.rol, activo: u.activo !== false }))
      const map = {}
      for (const p of u.permissions || []) map[p.project_id] = p
      setPerms(map)
    })

  useEffect(() => {
    listActiveProjects().then(setProjects).catch((e) => setError(e.message))
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
        await updateUser(id, {
          nombre: form.nombre,
          rol: form.rol,
          activo: form.activo,
        })
      } else {
        const res = await createUser({
          telegram_chat_id: form.telegram_chat_id,
          nombre: form.nombre,
          rol: form.rol,
        })
        userId = res.id
      }
      if (form.rol === 'usuario') {
        await saveUserPermissions(userId, rowsFromPerms())
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
      <PageHead title={editing ? 'Editar usuario de Telegram' : 'Nuevo usuario de Telegram'} sub="Los administradores pueden respaldar y monitorear todos los proyectos." />

      {error && <Flash type="err">{error}</Flash>}

      <div className="card">
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="form-grid">
              <div className="field">
                <label className="label">ID de chat en Telegram</label>
                <input className="input mono" value={form.telegram_chat_id} onChange={set('telegram_chat_id')}
                  required={!editing} disabled={editing} placeholder="123456789" />
                <div className="hint">Es el número que identifica el chat del usuario con el bot.</div>
              </div>
              <div className="field">
                <label className="label">Nombre para mostrar</label>
                <input className="input" value={form.nombre} onChange={set('nombre')} required />
              </div>
              <div className="field">
                <label className="label">Rol de acceso</label>
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