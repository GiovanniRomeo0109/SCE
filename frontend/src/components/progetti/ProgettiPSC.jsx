import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getProgetti, creaProgetto, eliminaProgetto } from '../../utils/api';
import { useNotify } from '../../App';
import ProgettoDettaglio from './ProgettoDettaglio';

/**
 * Progetti PSC dell'utente, dentro la pagina "Nuovo Progetto con AI".
 * L'id del progetto aperto è nell'indirizzo (?progetto=ID): ricaricando la pagina
 * si torna allo stesso progetto.
 */
export default function ProgettiPSC({ onIndietro }) {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [params, setParams] = useSearchParams();
  const aperto = params.get('progetto');
  const [progetti, setProgetti] = useState(null);
  const [nome, setNome] = useState('');
  const [creazione, setCreazione] = useState(false);

  const carica = useCallback(() => {
    getProgetti()
      .then(r => setProgetti(Array.isArray(r.data) ? r.data : []))
      .catch(e => { setProgetti([]); notifyRef.current(e.message, 'error'); });
  }, []);

  useEffect(() => { if (!aperto) carica(); }, [aperto, carica]);

  const apri = (id) => setParams({ tipo: 'psc', progetto: String(id) });
  const chiudi = () => setParams({ tipo: 'psc' });

  const crea = async () => {
    if (!nome.trim()) { notify('Indica un nome per il progetto', 'error'); return; }
    setCreazione(true);
    try {
      const r = await creaProgetto(nome.trim());
      setNome('');
      apri(r.data.id);
    } catch (e) { notify(e.message, 'error'); }
    finally { setCreazione(false); }
  };

  const elimina = async (p) => {
    if (!window.confirm(`Eliminare il progetto "${p.nome}" con tutti i documenti e i dati estratti?`)) return;
    try { await eliminaProgetto(p.id); notify('Progetto eliminato', 'success'); carica(); }
    catch (e) { notify(e.message, 'error'); }
  };

  if (aperto) return <ProgettoDettaglio progettoId={Number(aperto)} onIndietro={chiudi} />;

  return (
    <div style={{ maxWidth: 900 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <button className="btn btn-ghost btn-sm" onClick={onIndietro}>← Tipo documento</button>
        <h2 style={{ margin: 0, color: '#1A3A5C' }}>📗 I tuoi progetti PSC</h2>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 10 }}>➕ Nuovo progetto</div>
        <div style={{ display: 'flex', gap: 10 }}>
          <input className="form-control" placeholder="Es. Ristrutturazione palazzina via Roma 12, Rovigo"
            value={nome} onChange={e => setNome(e.target.value)} onKeyDown={e => e.key === 'Enter' && crea()} />
          <button className="btn btn-gold" onClick={crea} disabled={creazione}>
            {creazione ? 'Creazione…' : 'Crea progetto →'}
          </button>
        </div>
        <p style={{ fontSize: '0.78rem', color: '#8A9BB0', margin: '8px 0 0' }}>
          Dopo la creazione potrai caricare tutti i documenti del cantiere: vengono elaborati in
          background e puoi chiudere la pagina e tornare più tardi.
        </p>
      </div>

      <div className="card">
        {progetti === null ? (
          <div style={{ color: '#8A9BB0' }}>Caricamento…</div>
        ) : progetti.length === 0 ? (
          <div className="empty-state"><div className="empty-icon">📂</div><p>Nessun progetto ancora. Creane uno!</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Progetto</th><th>Documenti</th><th>Ultima attività</th><th></th></tr></thead>
              <tbody>
                {progetti.map(p => (
                  <tr key={p.id}>
                    <td>
                      <strong style={{ cursor: 'pointer', color: '#1A3A5C' }} onClick={() => apri(p.id)}>{p.nome}</strong>
                      {p.is_esempio && <span className="badge badge-psc" style={{ marginLeft: 8 }}>Esempio</span>}
                      {p.stato === 'chiuso' && <span className="badge badge-notifica" style={{ marginLeft: 8 }}>Chiuso</span>}
                      {p.preavviso_eliminazione && (
                        <div style={{ fontSize: '0.72rem', color: '#C0392B', marginTop: 2 }}>
                          ⚠️ I file originali verranno eliminati tra {p.giorni_alla_eliminazione} giorni
                          per inattività: apri il progetto per mantenerli.
                        </div>
                      )}
                      {p.file_eliminati && (
                        <div style={{ fontSize: '0.72rem', color: '#8A9BB0', marginTop: 2 }}>
                          File originali eliminati · dati estratti disponibili
                        </div>
                      )}
                    </td>
                    <td style={{ fontSize: '0.82rem' }}>{p.n_completati} / {p.n_documenti} elaborati</td>
                    <td style={{ fontSize: '0.82rem', color: '#5A6B7D' }}>
                      {p.ultima_attivita ? new Date(p.ultima_attivita.replace(' ', 'T') + 'Z').toLocaleDateString('it-IT') : '—'}
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button className="btn btn-gold btn-sm" onClick={() => apri(p.id)} style={{ marginRight: 6 }}>Apri →</button>
                      {!p.is_esempio && <button className="btn btn-danger btn-sm" onClick={() => elimina(p)}>🗑</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
