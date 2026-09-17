import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { createProject, getProject, updateProject } from '../../services/projects.js'
import { listAccounts } from '../../services/accounts.js'
import { useAbort, isAbortError } from '../../hooks/useAbort.js'
import { ApiError } from '../../services/http.js'
import PageHead from '../../components/ui/PageHead.jsx'
import { useToast } from '../../components/ui/Toast.jsx'

export default function ProjectForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()
  const signal = useAbort()

  const [accounts, setAccounts] = useState([])
  const [form, setForm] = useState({
    slug: '', nombre: '', account_id: '', connection: '', project_ref: '', activo: true,
  })
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    listAccounts({ signal }).then(setAccounts).catch((e) => {
      if (!isAbortError(e)) setError(e.message)
    })
  }, [])

  useEffect(() => {
    if (error) toast.err(error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error])

  useEffect(() => {
    if (!id) return
    getProject(id, { signal })
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
      .catch((e) => {
        if (!isAbortError(e)) setError(e.message)
      })
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
        toast.ok('Proyecto actualizado.')
      } else {
        await createProject(payload)
        toast.ok('Proyecto creado.')
      }
      navigate('/proyectos')
    } catch (err) {
      toast.err(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <PageHead title={editing ? 'Editar proyecto' : 'Nuevo proyecto'} sub="Conecta un proyecto de Supabase y programa su respaldo automático." />

      <div className="card">
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="form-grid">
              <div className="field">
                <label className="label" htmlFor="proj-slug">Nombre corto (slug)</label>
                <input id="proj-slug" className="input" value={form.slug} onChange={set('slug')} placeholder="mi-proyecto" required disabled={editing} />
                <div className="hint">Minúsculas, números y guiones. No se puede cambiar después.</div>
              </div>
              <div className="field">
                <label className="label" htmlFor="proj-nombre">Nombre visible</label>
                <input id="proj-nombre" className="input" value={form.nombre} onChange={set('nombre')} required />
              </div>
              <div className="field">
                <label className="label" htmlFor="proj-account">Cuenta de Supabase</label>
                <select id="proj-account" className="select" value={form.account_id} onChange={set('account_id')} required>
                  <option value="" disabled>Selecciona una cuenta…</option>
                  {accounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.nombre}</option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="label" htmlFor="proj-ref">Referencia del proyecto (ref)</label>
                <input id="proj-ref" className="input mono" value={form.project_ref} onChange={set('project_ref')} placeholder="xxxxxxxxxxxxxxxxxxxx" required />
                <div className="hint">Código del proyecto. Aparece en la URL de tu dashboard de Supabase.</div>
              </div>
            </div>

            <div className="field">
              <label className="label" htmlFor="proj-connection">Conexión de la base de datos</label>
              <input id="proj-connection" className="input mono" type="text" value={form.connection} onChange={set('connection')}
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