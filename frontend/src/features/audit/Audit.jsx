import { useEffect, useState } from 'react'
import { listAudit } from '../../services/audit.js'
import { fmtFecha } from '../../utils/format.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Pager from '../../components/ui/Pager.jsx'

const PAGE_SIZE = 50

export default function Audit() {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')

  useEffect(() => {
    listAudit(page, PAGE_SIZE)
      .then(setData)
      .catch((e) => setError(e.message))
  }, [page])

  if (error) return <Flash type="err">{error}</Flash>
  if (!data) return <div className="muted">Cargando…</div>

  const rows = data.rows || []

  return (
    <>
      <PageHead title="Auditoría" sub={`Historial de la actividad del panel y del bot · ${data.total} registros.`} />

      <div className="card">
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr><th>Fecha</th><th>Desde</th><th>Acción</th><th>Estado</th><th>Detalle</th></tr>
            </thead>
            <tbody>
              {rows.map((a) => (
                <tr key={a.id}>
                  <td className="muted">{fmtFecha(a.fecha)}</td>
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
        <Pager page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
      </div>
    </>
  )
}