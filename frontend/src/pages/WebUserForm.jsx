import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api.js'

export default function WebUserForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()

  const [form, setForm] = useState({ username: '', password: '', rol: 'admin', activo: true })
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!id) return
    api
      .get(`/api/web-users/${id}`)
      .then((u) => setForm((f) => ({ ...f, username: u.username, rol: u.rol, activo: u.activo !== false })))
      .catch((e) => setError(e.message))
  }, [id])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setChk = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.checked }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    const payload = { username: form.username, rol: form.rol, activo: form.activo }
    if (form.password) payload.password = form.password
    try {
      if (editing) {
        await api.put(`/api/web-users/${id}`, payload)
      } else {
        await api.post('/api/web-users', payload)
      }
      navigate('/usuarios-web')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">{editing ? 'Editar usuario web' : 'Nuevo usuario web'}</h1>
          <p className="sub">Los viewers solo pueden consultar; los admins pueden administrar.</p>
        </div>
      </div>

      {error && <div className="flash flash-err">{error}</div>}

      <div className="card" style={{ maxWidth: 480 }}>
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="field">
              <label className="label">Usuario</label>
              <input className="input" value={form.username} onChange={set('username')} required autoComplete="off" />
            </div>
            <div className="field">
              <label className="label">{editing ? 'Nueva contraseña' : 'Contraseña'}</label>
              <input className="input" type="password" value={form.password}
                onChange={set('password')} required={!editing} placeholder="mínimo 8 caracteres" autoComplete="new-password" />
              <div className="hint">{editing ? 'Vacía para no cambiarla.' : ''}</div>
            </div>
            <div className="field">
              <label className="label">Rol</label>
              <select className="select" value={form.rol} onChange={set('rol')}>
                <option value="admin">admin</option>
                <option value="viewer">viewer</option>
              </select>
            </div>
            <div className="field">
              <label className="check">
                <input type="checkbox" checked={form.activo} onChange={setChk('activo')} />
                Activo
              </label>
            </div>
            <div className="inline-actions">
              <button className="btn btn-primary" disabled={sending}>{sending ? 'Guardando…' : 'Guardar'}</button>
              <button type="button" className="btn btn-ghost" onClick={() => navigate('/usuarios-web')}>Cancelar</button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}