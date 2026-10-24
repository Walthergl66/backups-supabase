import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  createProject, getProject, testProjectConnection, updateProject,
} from '../../services/projects.js'
import { listAccounts } from '../../services/accounts.js'
import { useAbort, isAbortError } from '../../hooks/useAbort.js'
import { ApiError } from '../../services/http.js'
import PageHead from '../../components/ui/PageHead.jsx'
import { useToast } from '../../components/ui/Toast.jsx'

const PROVIDERS = [
  { value: 'postgres', label: 'PostgreSQL directo' },
  { value: 'supabase', label: 'Supabase' },
]

const emptyForm = {
  slug: '',
  nombre: '',
  provider: 'postgres',
  account_id: '',
  connection: '',
  project_ref: '',
  schedule: '',
  activo: true,
  no_owner: true,
  no_privileges: true,
}

export default function ProjectForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()
  const signal = useAbort()

  const [accounts, setAccounts] = useState([])
  const [form, setForm] = useState(emptyForm)
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)
  const [testing, setTesting] = useState(false)

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
        const provider = p.provider || 'postgres'
        const options = p.backup_options || {}
        setForm({
          slug: p.slug || '',
          nombre: p.nombre || '',
          provider,
          account_id: p.account_id || '',
          connection: '',
          project_ref: p.project_ref || '',
          schedule: p.schedule || '',
          activo: p.activo !== false,
          no_owner: options.no_owner ?? provider === 'postgres',
          no_privileges: options.no_privileges ?? provider === 'postgres',
        })
      })
      .catch((e) => {
        if (!isAbortError(e)) setError(e.message)
      })
  }, [id])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))
  const setChk = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.checked }))
  const setProvider = (e) => setForm((f) => ({
    ...f,
    provider: e.target.value,
    account_id: '',
    project_ref: e.target.value === 'postgres' ? '' : f.project_ref,
  }))

  const isSupabase = form.provider === 'supabase'
  const providerAccounts = accounts.filter(
    (a) => (a.provider || 'supabase') === form.provider,
  )

  const test = async () => {
    const connection = form.connection.trim()
    if (!connection) {
      toast.err('Escribe la cadena de conexión para poder probarla.')
      return
    }
    setTesting(true)
    try {
      const r = await testProjectConnection(connection, form.provider)
      if (!r.ok) {
        toast.err(r.detalle || 'No se pudo conectar.')
        return
      }
      const extra = r.server_version ? ` · PostgreSQL ${r.server_version}` : ''
      const latency = r.latency_ms != null ? ` · ${r.latency_ms} ms` : ''
      toast.ok(`${r.detalle || 'Conexión correcta'}${extra}${latency}`)
    } catch (err) {
      toast.err(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setTesting(false)
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    const payload = {
      slug: form.slug,
      nombre: form.nombre,
      provider: form.provider,
      account_id: Number(form.account_id || 0),
      connection: form.connection,
      project_ref: isSupabase ? form.project_ref : '',
      schedule: form.schedule,
      activo: form.activo,
    }
    if (!isSupabase) {
      payload.backup_options = {
        no_owner: form.no_owner,
        no_privileges: form.no_privileges,
      }
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
      <PageHead
        title={editing ? 'Editar proyecto' : 'Nuevo proyecto'}
        sub="Conecta una base PostgreSQL y programa su respaldo automático."
      />

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
                <label className="label">Proveedor</label>
                <select className="select" value={form.provider} onChange={setProvider} required>
                  {PROVIDERS.map((p) => (
                    <option key={p.value} value={p.value}>{p.label}</option>
                  ))}
                </select>
                <div className="hint">Las cuentas agrupan proyectos. Para PostgreSQL genérica sirve cualquier cuenta (su PAT no se usa).</div>
              </div>
              <div className="field">
                <label className="label">{isSupabase ? 'Cuenta de Supabase' : 'Grupo de conexiones'}</label>
                <select className="select" value={form.account_id} onChange={set('account_id')}
                  required={isSupabase}>
                  <option value="">
                    {isSupabase ? 'Selecciona una cuenta…' : 'Grupo por defecto (Conexiones directas)'}
                  </option>
                  {providerAccounts.map((a) => (
                    <option key={a.id} value={a.id}>{a.nombre}</option>
                  ))}
                </select>
                {isSupabase && !providerAccounts.length && (
                  <div className="hint">
                    No hay cuentas de Supabase. <Link className="btn-link" to="/cuentas/nueva">Crea una</Link> para importar proyectos.
                  </div>
                )}
              </div>
              {isSupabase && (
                <div className="field">
                  <label className="label">Referencia del proyecto (ref)</label>
                  <input className="input mono" value={form.project_ref} onChange={set('project_ref')} placeholder="xxxxxxxxxxxxxxxxxxxx" required />
                  <div className="hint">Código del proyecto. Aparece en la URL de tu dashboard de Supabase.</div>
                </div>
              )}
              <div className="field">
                <label className="label">Respaldo automático (cron)</label>
                <input className="input mono" value={form.schedule} onChange={set('schedule')} placeholder="30 3 * * *" />
                <div className="hint">Cinco campos: minuto hora día mes día-semana. Vacío = solo manual.</div>
              </div>
            </div>

            <div className="field">
              <label className="label">Conexión de la base de datos</label>
              <div className="field-inline">
                <input className="input mono" type="text" value={form.connection} onChange={set('connection')}
                  placeholder="postgresql://usuario:contraseña@host:5432/basedatos"
                  required={!editing} />
                <button type="button" className="btn btn-ghost" onClick={test} disabled={testing}>
                  {testing ? 'Probando…' : 'Probar'}
                </button>
              </div>
              <div className="hint">
                {editing
                  ? 'Si la dejas vacía se conserva la actual (guardada cifrada).'
                  : 'Se valida y se guarda cifrada al almacenarla.'}
              </div>
            </div>

            {!isSupabase && (
              <div className="field">
                <label className="label">Compatibilidad del volcado</label>
                <label className="check">
                  <input type="checkbox" checked={form.no_owner} onChange={setChk('no_owner')} />
                  Omitir propietario (--no-owner)
                </label>
                <label className="check" style={{ marginTop: 10 }}>
                  <input type="checkbox" checked={form.no_privileges} onChange={setChk('no_privileges')} />
                  Omitir privilegios (--no-privileges)
                </label>
                <div className="hint">
                  Recomendado si restaurarás en un servidor con usuarios distintos.
                </div>
              </div>
            )}

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
