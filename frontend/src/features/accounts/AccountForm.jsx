import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api, ApiError } from '../api.js'

export default function AccountForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()

  const [form, setForm] = useState({ nombre: '', pat: '' })
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!id) return
    api
      .get(`/api/accounts/${id}`)
      .then((a) => setForm({ nombre: a.nombre, pat: '' }))
      .catch((e) => setError(e.message))
  }, [id])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    const payload = { nombre: form.nombre, pat: form.pat }
    try {
      if (editing) {
        await api.put(`/api/accounts/${id}`, payload)
      } else {
        await api.post('/api/accounts', payload)
      }
      navigate('/cuentas')
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
          <h1 className="h1">{editing ? 'Editar cuenta' : 'Nueva cuenta'}</h1>
          <p className="sub">El token se cifra antes de guardarse.</p>
        </div>
      </div>

      {error && <div className="flash flash-err">{error}</div>}

      <div className="card" style={{ maxWidth: 560 }}>
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="field">
              <label className="label">Nombre</label>
              <input className="input" value={form.nombre} onChange={set('nombre')} required />
            </div>
            <div className="field">
              <label className="label">Personal Access Token (PAT)</label>
              <input className="input mono" type="password" autoComplete="off"
                value={form.pat} onChange={set('pat')} required={!editing}
                placeholder={editing ? 'Dejar vacío para conservar el actual' : 'sbp_…'} />
              <div className="hint">Token de Supabase para listar proyectos.</div>
            </div>
            <div className="inline-actions">
              <button className="btn btn-primary" disabled={sending}>{sending ? 'Guardando…' : 'Guardar'}</button>
              <button type="button" className="btn btn-ghost" onClick={() => navigate('/cuentas')}>Cancelar</button>
            </div>
          </form>
        </div>
      </div>
    </>
  )
}