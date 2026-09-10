import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Audit() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get('/api/audit?limit=200')
      .then((d) => setRows(d.rows || []))
      .catch((e) => setError(e.message))
  }, [])

  return (
    <>
      <div className="page-head">
        <div>
          <h1 className="h1">Auditoría</h1>
          <p className="sub">Registro de acciones del bot y de la interfaz web.</p>
        </div>
      </div>

      {error && <div className="flash flash-err">{error}</div>}

      <div className="card">
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr><th>Fecha</th><th>Origen</th><th>Acción</th><th>Resultado</th><th>Detalle</th></tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td className="muted">{new Date(a.fecha).toLocaleString('es')}</td>
                  <td style={{ fontSize: 12 }}>{a.origen}</td>
                  <td className="mono">{a.accion}</td>
                  <td>
                    {a.resultado === 'ok' ? (
                      <span className="badge badge-ok">ok</span>
                    ) : (
                      <span className="badge badge-err">{a.resultado}</span>
                    )}
                  </td>
                  <td className="muted" style={{ wordBreak: 'break-all', maxWidth: 420 }}>{a.detalle || '-'}</td>
                </tr>
              ))}
              {!rows.length && (
                <tr className="empty"><td colSpan={5}>Sin actividad registrada.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}