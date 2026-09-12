export default function Pager({ page, pages, total, onChange }) {
  if (!total || pages <= 1) return null
  return (
    <div className="pager">
      <button className="btn btn-ghost" disabled={page <= 1} onClick={() => onChange(page - 1)}>‹ Anterior</button>
      <span className="muted">Página {page} de {pages} · {total} registros</span>
      <button className="btn btn-ghost" disabled={page >= pages} onClick={() => onChange(page + 1)}>Siguiente ›</button>
    </div>
  )
}