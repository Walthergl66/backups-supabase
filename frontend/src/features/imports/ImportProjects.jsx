import { useState } from 'react'
import { api, ApiError } from '../api.js'

export default function ImportProjects() {
  const [pat, setPat] = useState('')
  const [accountName, setAccountName] = useState('')
  const [available, setAvailable] = useState([])
  const [selected, setSelected] = useState({})
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const [tgNombre, setTgNombre] = useState('')
  const [tgChat, setTgChat] = useState('')
  const [tgRol, setTgRol] = useState('usuario')
  const [canBackup, setCanBackup] = useState(true)
  const [canMonitor, setCanMonitor] = useState(true)

  const [result, setResult] = useState(null)
  const [creating, setCreating] = useState(false)

  const fetchProjects = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    setResult(null)
    setSelected({})
    try {
      const d = await api.post('/api/import/fetch', { pat })
      setAvailable(d.available || [])
      if (!d.available.length && d.existing_count) {
        setError(`Los proyectos ya están importados (${d.existing_count}).`)
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setLoading(false)
    }
  }

  const toggle = (ref) => (e) => {
    setSelected((s) => ({ ...s, [ref]: e.target.checked }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setCreating(true)
    const selectedProjects = Object.entries(selected).filter(([, v]) => v).map(([ref]) => ref)
    try {
      const d = await api.post('/api/import/create', {
        pat,
        account_name: accountName,
        selected_projects: selectedProjects,
        telegram_nombre: tgNombre,
        telegram_chat_id: tgChat,
        telegram_rol: tgRol,
        can_backup: canBackup,
        can_monitor: canMonitor,
      })
      setResult(d)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setCreating(false)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">Importar proyectos</h1>
          <p className="sub">Trae proyectos de Supabase y en el mismo paso registra al usuario de Telegram que los operará.</p>
        </div>
      </div>

      {error && <div className="flash flash-err">{error}</div>}

      {result && (
        <div className="flash flash-ok">
          <div>
            <strong>Importación completada.</strong> Se crearon {result.created} proyectos en la cuenta <em>{result.account_name}</em>
            {result.telegram_user && (
              <>
                {' '}y el usuario de Telegram <strong>@{result.telegram_user.nombre}</strong> (chat {result.telegram_user.telegram_chat_id})
                {result.telegram_user.created ? ' fue registrado' : ' ya existía'}.
                Permisos: {result.telegram_user.projects.join(', ')}.
              </>
            )}
            {result.errors?.length > 0 && (
              <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                {result.errors.map((er, i) => <li key={i}>{er}</li>)}
              </ul>
            )}
          </div>
        </div>
      )}

      <form onSubmit={fetchProjects} className="card" style={{ marginBottom: 18 }}>
        <div className="card-head"><span className="card-title">1 · Token de Supabase</span></div>
        <div className="card-body">
          <div className="form-grid">
            <div className="field">
              <label className="label">Personal Access Token (PAT)</label>
              <input className="input mono" type="password" value={pat} onChange={(e) => setPat(e.target.value)} required
                placeholder="sbp_…" autoComplete="off" />
              <div className="hint">Se usa solo para listar proyectos y obtener su connection string. No se guarda.</div>
            </div>
            <div className="field">
              <label className="label">Nombre de la cuenta (opcional)</label>
              <input className="input" value={accountName} onChange={(e) => setAccountName(e.target.value)}
                placeholder="Importada desde bot" />
            </div>
          </div>
          <button className="btn btn-primary" disabled={loading || !pat}>
            {loading ? 'Consultando…' : 'Buscar proyectos'}
          </button>
        </div>
      </form>

      {available.length > 0 && (
        <form onSubmit={submit} className="card" style={{ marginBottom: 18 }}>
          <div className="card-head"><span className="card-title">2 · Selecciona proyectos</span></div>
          <div className="card-body">
            <div className="checkbox-scroll">
              {(available || []).map((p) => (
                <label key={p.ref} className="check" style={{ display: 'flex', padding: '9px 14px', borderBottom: '1px solid var(--border-soft)', width: '100%' }}>
                  <input type="checkbox" checked={Boolean(selected[p.ref])} onChange={toggle(p.ref)} />
                  <span style={{ flex: 1 }}>{p.name}</span>
                  <span className="mono muted" style={{ fontSize: 11 }}>{p.ref.slice(0, 8)}…</span>
                </label>
              ))}
            </div>
          </div>

          <div className="card-head"><span className="card-title">3 · Usuario de Telegram</span></div>
          <div className="card-body">
            <div className="form-grid">
              <div className="field">
                <label className="label">Nombre</label>
                <input className="input" value={tgNombre} onChange={(e) => setTgNombre(e.target.value)} required placeholder="Nombre o @alias" />
              </div>
              <div className="field">
                <label className="label">Chat ID</label>
                <input className="input mono" value={tgChat} onChange={(e) => setTgChat(e.target.value)} required placeholder="123456789" />
                <div className="hint">ID numérico del chat con el bot.</div>
              </div>
              <div className="field">
                <label className="label">Rol</label>
                <select className="select" value={tgRol} onChange={(e) => setTgRol(e.target.value)}>
                  <option value="usuario">usuario</option>
                  <option value="admin">admin</option>
                </select>
              </div>
              <div className="field" style={{ display: 'flex', alignItems: 'flex-end', gap: 16, paddingBottom: 4 }}>
                <label className="check">
                  <input type="checkbox" checked={canBackup} onChange={(e) => setCanBackup(e.target.checked)} />
                  Respaldar
                </label>
                <label className="check">
                  <input type="checkbox" checked={canMonitor} onChange={(e) => setCanMonitor(e.target.checked)} />
                  Monitorear
                </label>
              </div>
            </div>
            <div className="hint" style={{ margin: '0 0 14px' }}>
              Si el chat_id ya existe se reutiliza el usuario (sin duplicar permisos de rol admin).
            </div>
            <button className="btn btn-violet" disabled={creating || !Object.values(selected).some(Boolean) || !tgNombre || !tgChat}>
              {creating ? 'Importando…' : 'Importar ahora'}
            </button>
          </div>
        </form>
      )}
    </>
  )
}