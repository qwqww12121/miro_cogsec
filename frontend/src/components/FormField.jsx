export function FormField({ label, hint, children }) {
  return (
    <div>
      <label className="label-base">{label}</label>
      {children}
      {hint && <div className="text-[11px] text-ink-300 mt-1">{hint}</div>}
    </div>
  )
}

export function TextInput(props) {
  return <input {...props} className={`input-base ${props.className || ''}`} />
}

export function TextArea(props) {
  return <textarea {...props} className={`input-base ${props.className || ''}`} />
}

export function Select({ children, ...props }) {
  return (
    <select {...props} className={`input-base ${props.className || ''}`}>
      {children}
    </select>
  )
}
