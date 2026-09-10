import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'

export default function Accounts() {
  const [accounts, setAccounts] = useState([])
  const [error, setError] = useState('')

  const load = () => api.get('/api/accounts').then(setAccounts).catch((e) => setError(e.message))

  useEffect(() => {
    load()
  }, [])

  const del = async (a) => {
    if (!window.confirm(`¿Eliminar la cuenta "${a.nombre}"?`)) return
    try {
      await api.del(`/api/accounts/${a.id}`)
      load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">Cuentas</h1>
          <p className="sub">Cuentas de Supabase con su Personal Access Token cifrado.</p>
        </div>
        <Link className="btn btn-primary" to="/cuentas/nueva">Nueva cuenta</Link>
      </div>

      {error && <div className="flash flash-err">{error}</div>}

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
                  <td>{a.activo ? <span className="badge badge-ok">Activa</span> : <span className="badge badge-mid">Inactiva</span>}</td>
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