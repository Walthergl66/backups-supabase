import { useEffect, useState } from 'react'
import { listAudit } from '../../services/audit.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'
import Badge from '../../components/ui/Badge.jsx'

export default function Audit() {
  const [rows, setRows] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    listAudit()
      .then((d) => setRows(d.rows || []))
      .catch((e) => setError(e.message))
  }, [])

  return (
    <>
      <PageHead title="Auditoría" sub="Registro de acciones del bot y de la interfaz web." />

      {error && <Flash type="err">{error}</Flash>}

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
                      <Badge tone="ok">ok</Badge>
                    ) : (
                      <Badge tone="err">{a.resultado}</Badge>
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