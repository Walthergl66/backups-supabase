import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { createAccount, getAccount, updateAccount } from '../../services/accounts.js'
import { useAbort, isAbortError } from '../../hooks/useAbort.js'
import { ApiError } from '../../services/http.js'
import PageHead from '../../components/ui/PageHead.jsx'
import { useToast } from '../../components/ui/Toast.jsx'

export default function AccountForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()
  const signal = useAbort()

  const [form, setForm] = useState({ nombre: '', pat: '' })
  const [error, setError] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    if (!id) return
    getAccount(id, { signal })
      .then((a) => setForm({ nombre: a.nombre, pat: '' }))
      .catch((e) => {
        if (!isAbortError(e)) setError(e.message)
      })
  }, [id])

  useEffect(() => {
    if (error) toast.err(error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSending(true)
    const payload = { nombre: form.nombre, pat: form.pat }
    try {
      if (editing) {
        await updateAccount(id, payload)
        toast.ok('Cuenta actualizada.')
      } else {
        await createAccount(payload)
        toast.ok('Cuenta creada.')
      }
      navigate('/cuentas')
    } catch (err) {
      toast.err(err instanceof ApiError ? err.message : 'Error inesperado')
    } finally {
      setSending(false)
    }
  }

  return (
    <>
      <PageHead title={editing ? 'Editar cuenta' : 'Nueva cuenta'} sub="Agrega una cuenta de Supabase; su token se guarda cifrado." />

      <div className="card" style={{ maxWidth: 560 }}>
        <div className="card-body">
          <form onSubmit={submit}>
            <div className="field">
              <label className="label" htmlFor="acc-nombre">Nombre de la cuenta</label>
              <input id="acc-nombre" className="input" value={form.nombre} onChange={set('nombre')} required />
            </div>
            <div className="field">
              <label className="label" htmlFor="acc-pat">Token de acceso (PAT)</label>
              <input id="acc-pat" className="input mono" type="password" autoComplete="off"
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