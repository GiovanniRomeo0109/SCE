export default function Field({ label, field, type = 'text', placeholder, hint, form, set }) {
  return (
    <div className="form-group">
      <label className="form-label">{label}</label>
      {type === 'textarea' ? (
        <textarea
          className="form-control"
          rows={3}
          value={form[field] || ''}
          placeholder={placeholder}
          onChange={e => set(field, e.target.value)}
        />
      ) : (
        <input
          type={type}
          className="form-control"
          value={form[field] || ''}
          placeholder={placeholder}
          onChange={e => set(field, e.target.value)}
        />
      )}
      {hint && (
        <div style={{ fontSize: '0.72rem', color: '#8A9BB0', marginTop: 3 }}>{hint}</div>
      )}
    </div>
  );
}