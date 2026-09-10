import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { createAccount, getAccount, updateAccount } from '../../services/accounts.js'
import { ApiError } from '../../services/http.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'

export default function AccountForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()

  const [form, setForm] = useState({ nombre: '', pat: '' })
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!id) return
    getAccount(id)
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
        await updateAccount(id, payload)
      } else {
        await createAccount(payload)
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
      <PageHead title={editing ? 'Editar cuenta' : 'Nueva cuenta'} sub="Agrega una cuenta de Supabase; su token se guarda cifrado." />

      {error && <Flash type="err">{error}</Flash>}

      <div className="card" style={{ maxWidth: 560 }}>
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="field">
              <label className="label">Nombre de la cuenta</label>
              <input className="input" value={form.nombre} onChange={set('nombre')} required />
            </div>
            <div className="field">
              <label className="label">Token de acceso (PAT)</label>
              <input className="input mono" type="password" autoComplete="off"
                value={form.pat} onChange={set('pat')} required={!editing}
                placeholder={editing ? 'Dejar vacío para conservar el actual' : 'sbp_…'} />
              <div className="hint">Token personal de Supabase (empieza con sbp_…) para listar tus proyectos. Se guarda cifrado.</div>
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