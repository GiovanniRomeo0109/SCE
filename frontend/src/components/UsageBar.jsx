import { useState, useEffect } from 'react';
import { apiFetch } from '../utils/api';

export default function UsageBar() {
  const [info, setInfo] = useState(null);

  useEffect(() => {
    apiFetch('/api/auth/me')
      .then(r => r.data)
      .then(setInfo)
      .catch(() => {});
  }, []);

  if (!info) return null;

  const pct = Math.round((info.calls_oggi / info.max_calls_giorno) * 100);
  const colore = pct >= 90 ? '#dc3545' : pct >= 70 ? '#F5C842' : '#28a745';

  return (
    <div style={{
      margin: '12px 16px', padding: '10px 12px', borderRadius: 8,
      background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
        <span style={{ color: '#8A9BB0', fontSize: '0.72rem' }}>Operazioni oggi</span>
        <span style={{ color: colore, fontSize: '0.72rem', fontWeight: 600 }}>
          {info.calls_oggi} / {info.max_calls_giorno}
        </span>
      </div>
      <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: 4, height: 5 }}>
        <div style={{
          width: `${Math.min(pct, 100)}%`, height: '100%',
          background: colore, borderRadius: 4, transition: 'width 0.3s',
        }} />
      </div>
      {info.calls_rimanenti === 0 && (
        <p style={{ color: '#dc3545', fontSize: '0.7rem', margin: '6px 0 0' }}>
          ⚠️ Limite raggiunto — si azzera a mezzanotte
        </p>
      )}
    </div>
  );
}
