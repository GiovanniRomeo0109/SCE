import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getStorico } from '../utils/api';

const TIPO_CONFIG = {
  psc:                  { label: 'PSC',      badge: 'badge-psc',      icon: '📗' },
  pos:                  { label: 'POS',      badge: 'badge-pos',      icon: '📘' },
  notifica_preliminare: { label: 'Notifica', badge: 'badge-notifica', icon: '📋' },
};

export default function Dashboard() {
  const [storico, setStorico] = useState([]);

  useEffect(() => {
    getStorico().then(r => { const list = Array.isArray(r) ? r : Array.isArray(r?.data) ? r.data : Array.isArray(r?.documenti) ? r.documenti : []; setStorico(list); }).catch(() => {});
  }, []);

  const count = (tipo) => storico.filter(d => d.tipo_documento === tipo).length;

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Benvenuto in SafetyDocs — gestione documentazione sicurezza cantieri D.Lgs. 81/2008</p>
      </div>

      <div className="card-grid">
        {[
          { tipo: 'notifica_preliminare', label: 'Notifiche Preliminari', color: '#C88B2A' },
          { tipo: 'psc', label: 'Piani di Sicurezza e Coordinamento', color: '#27AE60' },
          { tipo: 'pos', label: 'Piani Operativi di Sicurezza', color: '#1A3A5C' },
        ].map(s => (
          <div key={s.tipo} className="stat-card" style={{ borderLeftColor: s.color }}>
            <div className="stat-num" style={{ color: s.color }}>{count(s.tipo)}</div>
            <div className="stat-label">{s.label}</div>
          </div>
        ))}
        <div className="stat-card" style={{ borderLeftColor: '#5A6B7D' }}>
          <div className="stat-num" style={{ color: '#5A6B7D' }}>{storico.length}</div>
          <div className="stat-label">Documenti Totali</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ fontWeight: 700, fontSize: '1rem', color: '#1A3A5C', marginBottom: 16 }}>
          🚀 Azioni rapide
        </div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <Link to="/nuovo/notifica" className="btn btn-primary">📋 Notifica Preliminare</Link>
          <Link to="/nuovo/psc"      className="btn btn-ghost">📗 Nuovo PSC</Link>
          <Link to="/nuovo/pos"      className="btn btn-ghost">📘 Nuovo POS</Link>
        </div>
      </div>

      <div className="card">
        <div style={{ fontWeight: 700, fontSize: '1rem', color: '#1A3A5C', marginBottom: 16 }}>
          🕐 Documenti recenti
        </div>
        {storico.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📂</div>
            <p>Nessun documento ancora. Crea il primo!</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Cantiere / Impresa</th><th>Tipo</th><th>Data</th><th></th></tr></thead>
              <tbody>
                {storico.slice(0, 8).map(d => {
                  const cfg = TIPO_CONFIG[d.tipo_documento] || { label: d.tipo_documento, badge: 'badge-notifica', icon: '📄' };
                  return (
                    <tr key={d.id}>
                      <td>
                        <strong>{d.nome_cantiere || '—'}</strong>
                        {d.impresa_nome && <><br /><span style={{ fontSize: '0.75rem', color: '#8A9BB0' }}>{d.impresa_nome}</span></>}
                      </td>
                      <td><span className={`badge ${cfg.badge}`}>{cfg.icon} {cfg.label}</span></td>
                      <td style={{ fontSize: '0.82rem', color: '#5A6B7D' }}>
                        {d.created_at ? new Date(d.created_at).toLocaleDateString('it-IT') : '—'}
                      </td>
                      <td>
                        <a href={`/api/documents/download/${d.id}`} className="btn btn-ghost btn-sm" download>
                          ↓ DOCX
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}