/** Messaggio a comparsa. La durata è gestita da App (un solo timer per tutti i messaggi). */
export default function Notification({ message, type = 'info', onClose }) {
  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  return (
    <div className={`notification notification-${type}`}>
      <span>{icons[type] || 'ℹ️'}</span>
      <span style={{ flex: 1 }}>{message}</span>
      <button onClick={onClose}
        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, opacity: .6 }}>
        ✕
      </button>
    </div>
  );
}