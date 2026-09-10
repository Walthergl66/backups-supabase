export default function Flash({ type = 'err', children }) {
  return <div className={`flash flash-${type}`}>{children}</div>
}