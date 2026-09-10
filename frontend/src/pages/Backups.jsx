import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, fmtBytes } from '../api.js'

export default function Backups() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/api/backups').then(setData).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="flash flash-err">{error}</div>
  if (!data) return <div className="muted">Cargando…</div>

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">Backups</h1>
          <p className="sub">{data.total} registros · se muestran los últimos {data.rows.length}.</p>
        </div>
      </div>

      <div className="card">
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr><th>Fecha</th><th>Proyecto</th><th>Resultado</th><th>Tamaño</th><th>Detalle</th></tr>
            </thead>
            <tbody>
              {(data.rows || []).map((r) => (
                <tr key={r.id}>
                  <td className="muted">{new Date(r.fecha).toLocaleString('es')}</td>
                  <td>
                    <Link className="btn-link" to={`/proyectos/${r.project_id}/historial`}>{r.slug}</Link>
                  </td>
                  <td>
                    {r.resultado === 'ok' ? (
                      <span className="badge badge-ok">OK</span>
                    ) : (
                      <span className="badge badge-err">Error</span>
                    )}
                  </td>
                  <td className="mono">{fmtBytes(r.tamaño_archivo)}</td>
                  <td className="mono muted" style={{ wordBreak: 'break-all' }}>{r.detalle || '-'}</td>
                </tr>
              ))}
              {!data.rows?.length && (
                <tr className="empty"><td colSpan={5}>Aún no hay backups registrados.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}