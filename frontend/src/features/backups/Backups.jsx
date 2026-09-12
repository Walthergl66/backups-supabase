import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listBackups } from '../../services/backups.js'
import { fmtBytes, fmtFecha } from '../../utils/format.js'
import PageHead from '../../components/ui/PageHead.jsx'
import Flash from '../../components/ui/Flash.jsx'
import Badge from '../../components/ui/Badge.jsx'
import Pager from '../../components/ui/Pager.jsx'

const PAGE_SIZE = 50

export default function Backups() {
  const [data, setData] = useState(null)
  const [page, setPage] = useState(1)
  const [error, setError] = useState('')

  useEffect(() => {
    listBackups(page, PAGE_SIZE).then(setData).catch((e) => setError(e.message))
  }, [page])

  if (error) return <Flash type="err">{error}</Flash>
  if (!data) return <div className="muted">Cargando…</div>

  return (
    <>
      <PageHead title="Backups" sub={`${data.total} registros · se muestran de la página ${data.page}.`} />

      <div className="card">
        <div className="table-scroll">
          <table className="t">
            <thead>
              <tr><th>Fecha</th><th>Proyecto</th><th>Estado</th><th>Tamaño</th><th>Detalle</th></tr>
            </thead>
            <tbody>
              {(data.rows || []).map((r) => (
                <tr key={r.id}>
                  <td className="muted">{fmtFecha(r.fecha)}</td>
                  <td>
                    <Link className="btn-link" to={`/proyectos/${r.project_id}/historial`}>{r.slug}</Link>
                  </td>
                  <td>
                    {r.resultado === 'ok' ? (
                      <Badge tone="ok">OK</Badge>
                    ) : (
                      <Badge tone="err">Error</Badge>
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
        <Pager page={data.page} pages={data.pages} total={data.total} onChange={setPage} />
      </div>
    </>
  )
}