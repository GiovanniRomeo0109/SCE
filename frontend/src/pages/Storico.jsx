import { useState, useEffect } from 'react';
import { getStorico, deleteDocumento, downloadUrl } from '../utils/api';
import { useNotify } from '../App';

const TIPO_CONFIG = {
  psc:                  { label: 'PSC',          badge: 'badge-psc',      icon: '📗' },
  pos:                  { label: 'POS',          badge: 'badge-pos',      icon: '📘' },
  notifica_preliminare: { label: 'Notifica',     badge: 'badge-notifica', icon: '📋' },
  verifica_psc:         { label: 'Verifica PSC', badge: 'badge-psc',      icon: '🔍' },
  verifica_pos:         { label: 'Verifica POS', badge: 'badge-pos',      icon: '🔍' },
  verifica_congruita:   { label: 'Congruità',    badge: 'badge-notifica', icon: '🔗' },
  verbale_incongruenze: { label: 'Verbale',      badge: 'badge-notifica', icon: '📝' },
};

export default function Storico() {
  const [docs, setDocs] = useState([]);
  const [filtro, setFiltro] = useState('');
  const notify = useNotify();

  const carica = () => {
    getStorico()
      .then(r => {
        const list = Array.isArray(r) ? r
          : Array.isArray(r?.data) ? r.data
          : Array.isArray(r?.documenti) ? r.documenti
          : [];
        setDocs(list);
      })
      .catch(() => {});
  };

  useEffect(carica, []);

  const handleDelete = async (id) => {
    if (!window.confirm('Eliminare questo documento?')) return;
    try {
      await deleteDocumento(id);
      notify('Documento eliminato', 'success');
      carica();
    } catch {
      notify("Errore durante l'eliminazione", 'error');
    }
  };

  const filtered = docs.filter(d =>
    (d.nome_cantiere || '').toLowerCase().includes(filtro.toLowerCase()) ||
    (d.impresa_nome || '').toLowerCase().includes(filtro.toLowerCase()) ||
    (d.tipo || '').toLowerCase().includes(filtro.toLowerCase())
  );

  return (
    <div>
      <div className="page-header">
        <h1>Storico Documenti</h1>
        <p>Tutti i documenti generati</p>
      </div>
      <div className="toolbar">
        <input
          className="form-control"
          style={{ width: 280 }}
          placeholder="🔍 Cerca per cantiere, impresa, tipo..."
          value={filtro}
          onChange={e => setFiltro(e.target.value)}
        />
        <span style={{ fontSize: '0.82rem', color: '#8A9BB0' }}>{filtered.length} documenti</span>
      </div>
      <div className="card">
        {filtered.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">📂</div>
            <p>Nessun documento trovato</p>
          </div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr>
                  <th>Cantiere / Impresa</th>
                  <th>Tipo</th>
                  <th>Data</th>
                  <th>Azioni</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(d => {
                  const cfg = TIPO_CONFIG[d.tipo] || {
                    label: d.tipo,
                    badge: 'badge-notifica',
                    icon: '📄',
                  };
                  return (
                    <tr key={d.id}>
                      <td>
                        <strong>{d.nome_cantiere || '—'}</strong>
                        {d.impresa_nome && (
                          <>
                            <br />
                            <span style={{ fontSize: '0.75rem', color: '#8A9BB0' }}>
                              {d.impresa_nome}
                            </span>
                          </>
                        )}
                      </td>
                      <td>
                        <span className={`badge ${cfg.badge}`}>
                          {cfg.icon} {cfg.label}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.82rem', color: '#5A6B7D' }}>
                        {d.created_at
                          ? new Date(d.created_at).toLocaleDateString('it-IT')
                          : '—'}
                      </td>
                      <td style={{ display: 'flex', gap: 8 }}>
                        {d.scaricabile && (
                          <a
                            href={downloadUrl(d.id)}
                            className="btn btn-gold"
                            download
                          >
                            ↓ DOCX
                          </a>
                        )}
                        {!d.scaricabile && (
                          <span style={{ fontSize: '0.75rem', color: '#8A9BB0', alignSelf: 'center' }}>
                            📊 Report in app
                          </span>
                        )}
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={() => handleDelete(d.id)}
                        >
                          🗑
                        </button>
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
