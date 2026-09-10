export default function PageHead({ title, sub, subClass, children }) {
  return (
    <div className="page-head">
      <div>
        <h1 className="h1">{title}</h1>
        {sub && <p className={`sub${subClass ? ` ${subClass}` : ''}`}>{sub}</p>}
      </div>
      {children}
    </div>
  )
}