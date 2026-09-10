import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { createProject, getProject, updateProject } from '../../services/projects.js'
import { listAccounts } from '../../services/accounts.js'
import { ApiError } from '../../services/http.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'

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
    listAccounts().then(setAccounts).catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!id) return
    getProject(id)
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
        await updateProject(id, payload)
      } else {
        await createProject(payload)
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
      <PageHead title={editing ? 'Editar proyecto' : 'Nuevo proyecto'} sub="Conecta un proyecto de Supabase y programa su respaldo automático." />

      {error && <Flash type="err">{error}</Flash>}

      <div className="card">
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="form-grid">
              <div className="field">
                <label className="label">Nombre corto (slug)</label>
                <input className="input" value={form.slug} onChange={set('slug')} placeholder="mi-proyecto" required disabled={editing} />
                <div className="hint">Minúsculas, números y guiones. No se puede cambiar después.</div>
              </div>
              <div className="field">
                <label className="label">Nombre visible</label>
                <input className="input" value={form.nombre} onChange={set('nombre')} required />
              </div>
              <div className="field">
                <label className="label">Cuenta de Supabase</label>
                <select className="select" value={form.account_id} onChange={set('account_id')} required>
                  <option value="" disabled>Selecciona una cuenta…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.nombre}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="label">Referencia del proyecto (ref)</label>
                <input className="input mono" value={form.project_ref} onChange={set('project_ref')} placeholder="xxxxxxxxxxxxxxxxxxxx" required />
                <div className="hint">Código del proyecto. Aparece en la URL de tu dashboard de Supabase.</div>
              </div>
            </div>

            <div className="field">
              <label className="label">Conexión de la base de datos</label>
              <input className="input mono" type="text" value={form.connection} onChange={set('connection')}
                placeholder="postgresql://postgres:[PASSWORD]@db.xxxx.supabase.co:5432/postgres" required={!editing} />
              <div className="hint">
                {editing ? 'Si la dejas vacía se conserva la actual (guardada cifrada).' : 'Se guarda cifrada al almacenarla.'}
              </div>
            </div>

            <div className="field">
              <label className="check">
                <input type="checkbox" checked={form.activo} onChange={setChk('activo')} />
                Activo: permitir respaldos programados
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