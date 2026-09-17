import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { createWebUser, getWebUser, updateWebUser } from '../../services/webUsers.js'
import { useAbort, isAbortError } from '../../hooks/useAbort.js'
import { ApiError } from '../../services/http.js'
import PageHead from '../../components/ui/PageHead.jsx'
import { useToast } from '../../components/ui/Toast.jsx'

export default function WebUserForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()
  const signal = useAbort()

  const [form, setForm] = useState({ username: '', password: '', rol: 'admin', activo: true })
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!id) return
    getWebUser(id, { signal })
      .then((u) => setForm((f) => ({ ...f, username: u.username, rol: u.rol, activo: u.activo !== false })))
      .catch((e) => {
        if (!isAbortError(e)) setError(e.message)
      })
  }, [id])

  useEffect(() => {
    if (error) toast.err(error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error])

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
        await updateWebUser(id, payload)
        toast.ok('Usuario web actualizado.')
      } else {
        await createWebUser(payload)
        toast.ok('Usuario web creado.')
      }
      navigate('/usuarios-web')
    } catch (err) {
      toast.err(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <PageHead title={editing ? 'Editar usuario web' : 'Nuevo usuario web'} sub="Roles: administrar todo o solo consultar." />

      <div className="card" style={{ maxWidth: 480 }}>
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="field">
              <label className="label" htmlFor="wu-username">Nombre de usuario</label>
              <input id="wu-username" className="input" value={form.username} onChange={set('username')} required autoComplete="off" />
            </div>
            <div className="field">
              <label className="label" htmlFor="wu-password">{editing ? 'Nueva contraseña' : 'Contraseña'}</label>
              <input id="wu-password" className="input" type="password" value={form.password}
                onChange={set('password')} required={!editing} placeholder="mínimo 8 caracteres" autoComplete="new-password" />
              <div className="hint">{editing ? 'Vacía para no cambiarla.' : ''}</div>
            </div>
            <div className="field">
              <label className="label" htmlFor="wu-rol">Rol de acceso</label>
              <select id="wu-rol" className="select" value={form.rol} onChange={set('rol')}>
                <option value="admin">admin</option>
                <option value="viewer">viewer</option>
              </select>
            </div>
            <div className="field">
              <label className="check">
                <input type="checkbox" checked={form.activo} onChange={setChk('activo')} />
                Cuenta activa
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