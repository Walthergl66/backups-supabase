import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api.js'

export default function ProjectForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()

  const [accounts, setAccounts] = useState([])
  const [form, setForm] = useState({
    slug: '', nombre: '', account_id: '', connection: '', project_ref: '', activo: true,
  })
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    api.get('/api/accounts').then(setAccounts).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!id) return
    api
      .get(`/api/projects/${id}`)
      .then((p) => {
        setForm({
          slug: p.slug || '',
          nombre: p.nombre || '',
          account_id: p.account_id || '',
          connection: '',
          project_ref: p.project_ref || '',
          activo: p.activo !== false,
        })
      })
      .catch((e) => setError(e.message))
  }, [id])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setChk = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.checked }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    const payload = {
      slug: form.slug,
      nombre: form.nombre,
      account_id: Number(form.account_id || 0),
      connection: form.connection,
      project_ref: form.project_ref,
      activo: form.activo,
    }
    try {
      if (editing) {
        await api.put(`/api/projects/${id}`, payload)
      } else {
        await api.post('/api/projects', payload)
      }
      navigate('/proyectos')
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
          <h1 className="h1">{editing ? 'Editar proyecto' : 'Nuevo proyecto'}</h1>
          <p className="sub">Configura un proyecto de Supabase para su respaldo automático.</p>
        </div>
      </div>

      {error && <div className="flash flash-err">{error}</div>}

      <div className="card">
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="form-grid">
              <div className="field">
                <label className="label">Slug</label>
                <input className="input" value={form.slug} onChange={set('slug')} placeholder="mi-proyecto" required disabled={editing} />
                <div className="hint">minúsculas, números, guiones. No editable tras crear.</div>
              </div>
              <div className="field">
                <label className="label">Nombre</label>
                <input className="input" value={form.nombre} onChange={set('nombre')} required />
              </div>
              <div className="field">
                <label className="label">Cuenta</label>
                <select className="select" value={form.account_id} onChange={set('account_id')} required>
                  <option value="" disabled>Selecciona una cuenta…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.nombre}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="label">Project ref</label>
                <input className="input mono" value={form.project_ref} onChange={set('project_ref')} placeholder="xxxxxxxxxxxxxxxxxxxx" required />
                <div className="hint">Identificador del proyecto (parte del host).</div>
              </div>
            </div>

            <div className="field">
              <label className="label">Cadena de conexión (PostgreSQL)</label>
              <input className="input mono" type="text" value={form.connection} onChange={set('connection')}
                placeholder="postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres" required={!editing} />
              <div className="hint">
                {editing ? 'Si la dejas vacía se conserva la actual (cifrada en la base).' : 'Se cifra antes de guardar.'}
              </div>
            </div>

            <div className="field">
              <label className="check">
                <input type="checkbox" checked={form.activo} onChange={setChk('activo')} />
                Activo (permitir respaldos)
              </label>
            </div>

            <div className="inline-actions">
              <button className="btn btn-primary" disabled={sending}>{sending ? 'Guardando…' : 'Guardar'}</button>
              <button type="button" className="btn btn-ghost" onClick={() => navigate('/proyectos')}>Cancelar</button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}