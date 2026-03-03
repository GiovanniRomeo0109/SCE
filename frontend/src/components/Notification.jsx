import { useEffect } from 'react';

export default function Notification({ message, type = 'info', onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, 4500);
    return () => clearTimeout(t);
  }, [onClose]);

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