import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { deleteAccount, listAccounts } from '../../services/accounts.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'
import Badge from '../../components/ui/Badge.jsx'

export default function Accounts() {
  const [accounts, setAccounts] = useState([])
  const [error, setError] = useState('')

  const load = () => listAccounts().then(setAccounts).catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [])

  const del = async (a) => {
    if (!window.confirm(`¿Eliminar la cuenta "${a.nombre}"?`)) return
    try {
      await deleteAccount(a.id)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <PageHead title="Cuentas" sub="Cuentas de Supabase que alimentan el panel.">
        <Link className="btn btn-primary" to="/cuentas/nueva">Nueva cuenta</Link>
      </PageHead>

      {error && <Flash type="err">{error}</Flash>}

      <div className="card">
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr><th>Nombre</th><th>PAT</th><th>Estado</th><th>Creada</th><th className="td-actions">Acciones</th></tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.id}>
                  <td>{a.nombre}</td>
                  <td className="mono muted">{a.pat_masked}</td>
                  <td>{a.activo ? <Badge tone="ok">Activa</Badge> : <Badge tone="mid">Inactiva</Badge>}</td>
                  <td className="muted">{new Date(a.created_at).toLocaleDateString('es')}</td>
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