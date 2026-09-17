import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteAccount, listAccounts } from '../../services/accounts.js'
import { useAbort, isAbortError } from '../../hooks/useAbort.js'
import { fmtFechaDate } from '../../utils/format.js'
import PageHead from '../../components/ui/PageHead.jsx'
import { useToast } from '../../components/ui/Toast.jsx'
import { useDialog } from '../../components/ui/ConfirmDialog.jsx'
import Badge from '../../components/ui/Badge.jsx'

export default function Accounts() {
  const toast = useToast()
  const { confirm } = useDialog()
  const signal = useAbort()
  const [accounts, setAccounts] = useState([])
  const [error, setError] = useState('')

  const load = () =>
    listAccounts({ signal })
      .then(setAccounts)
      .catch((e) => {
        if (!isAbortError(e)) setError(e.message)
      })

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    if (error) toast.err(error)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [error])

  const del = async (a) => {
    const ok = await confirm(`¿Eliminar la cuenta "${a.nombre}"?`, {
      title: 'Eliminar cuenta',
      confirmLabel: 'Eliminar',
      danger: true,
    })
    if (!ok) return
    try {
      await deleteAccount(a.id)
      toast.ok(`Cuenta "${a.nombre}" eliminada.`)
      load()
    } catch (e) {
      toast.err(e.message)
    }
  }

  return (
    <>
      <PageHead title="Cuentas" sub="Cuentas de Supabase que alimentan el panel.">
        <Link className="btn btn-primary" to="/cuentas/nueva">Nueva cuenta</Link>
      </PageHead>

      <div className="card">
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr><th>Nombre</th><th>Token</th><th>Estado</th><th>Creada</th><th className="td-actions">Acciones</th></tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id}>
                  <td>{a.nombre}</td>
                  <td className="mono muted">{a.pat_masked}</td>
                  <td>{a.activo ? <Badge tone="ok">Activa</Badge> : <Badge tone="mid">Inactiva</Badge>}</td>
                  <td className="muted">{fmtFechaDate(a.created_at)}</td>
                  <td className="td-actions">
                    <Link className="btn-link" to={`/cuentas/${a.id}/editar`}>Editar</Link>
                    <button className="btn-link btn-link-danger" onClick={() => del(a)}>Eliminar</button>
                  </td>
                </tr>
              ))}
              {!accounts.length && (
                <tr className="empty"><td colSpan={5}>Sin cuentas registradas.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}