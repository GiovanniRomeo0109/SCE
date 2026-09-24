import { useState, useEffect, useCallback, useRef } from 'react';
import { getSchemi, creaSchema, salvaSchema, duplicaSchema, eliminaSchema } from '../../utils/api';
import { useNotify } from '../../App';
import EditorSchema from './EditorSchema';

/**
 * Scheda "Schema di cantiere": elenco degli schemi del progetto (uno per fase, se serve)
 * e apertura dell'editor. Solo gli schemi con "da includere nel PSC" andranno nel documento finale.
 */
export default function SchemiCantiere({ progettoId, solaLettura }) {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [d, setD] = useState(null);
  const [aperto, setAperto] = useState(null);
  const [nome, setNome] = useState('');
  const [rinomina, setRinomina] = useState({ id: null, nome: '' });

  const carica = useCallback(async () => {
    try { const r = await getSchemi(progettoId); setD(r.data); }
    catch (e) { notifyRef.current(e.message, 'error'); }
  }, [progettoId]);
  useEffect(() => { if (!aperto) carica(); }, [carica, aperto]);

  const crea = async () => {
    try {
      const r = await creaSchema(progettoId, nome.trim() || `Schema ${(d?.schemi.length || 0) + 1}`);
      setNome(''); setAperto(r.data.id);
    } catch (e) { notify(e.message, 'error'); }
  };
  const includi = async (sc, v) => {
    // Aggiornamento immediato della casella; se il salvataggio fallisce si ricarica lo stato reale
    setD(x => ({ ...x, schemi: x.schemi.map(y => (y.id === sc.id ? { ...y, includi_psc: v } : y)) }));
    try { await salvaSchema(progettoId, sc.id, { includi_psc: v }); } catch (e) { notify(e.message, 'error'); carica(); }
  };
  const duplica = async (sc) => {
    try { await duplicaSchema(progettoId, sc.id); notify('Schema duplicato', 'success'); carica(); } catch (e) { notify(e.message, 'error'); }
  };
  const elimina = async (sc) => {
    if (!window.confirm(`Eliminare lo schema "${sc.nome}" con il suo sfondo?`)) return;
    try { await eliminaSchema(progettoId, sc.id); carica(); } catch (e) { notify(e.message, 'error'); }
  };
  const salvaNome = async () => {
    try { await salvaSchema(progettoId, rinomina.id, { nome: rinomina.nome }); setRinomina({ id: null, nome: '' }); carica(); }
    catch (e) { notify(e.message, 'error'); }
  };

  if (!d) return <div style={{ padding: 30, color: '#8A9BB0' }}>Caricamento schemi…</div>;
  if (aperto) {
    return <EditorSchema progettoId={progettoId} schemaId={aperto} catalogo={d.catalogo}
      documentiSfondo={d.documenti_sfondo} onChiudi={() => setAperto(null)} solaLettura={solaLettura} />;
  }

  return (
    <div data-testid="schemi">
      <div className="warn-box" style={{ fontSize: '0.8rem', marginBottom: 14 }}>
        ⚠️ Gli schemi sono indicativi: vanno rifiniti in CAD. Puoi esportarli in PNG (per il PSC) e in DXF (per AutoCAD).
      </div>
      <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <input className="form-control" style={{ flex: 1, minWidth: 240 }} value={nome} onChange={e => setNome(e.target.value)}
          placeholder="Nome del nuovo schema (es. Fase 1 — allestimento del cantiere)" onKeyDown={e => e.key === 'Enter' && crea()} />
        <button className="btn btn-gold" onClick={crea}>➕ Nuovo schema</button>
      </div>
      <div className="card">
        {d.schemi.length === 0 ? (
          <div className="empty-state"><div className="empty-icon">🗺️</div>
            <p>Nessuno schema. Creane uno e usa come sfondo una tavola del progetto: puoi fare uno schema per ogni fase.</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Schema</th><th>Sfondo</th><th>Scala</th><th>Elementi</th><th>Nel PSC</th><th></th></tr></thead>
              <tbody>
                {d.schemi.map(sc => (
                  <tr key={sc.id} data-testid={`schema-${sc.id}`}>
                    <td>
                      {rinomina.id === sc.id ? (
                        <span style={{ display: 'flex', gap: 6 }}>
                          <input className="form-control" autoFocus value={rinomina.nome} onChange={e => setRinomina({ id: sc.id, nome: e.target.value })}
                            onKeyDown={e => e.key === 'Enter' && salvaNome()} />
                          <button className="btn btn-gold btn-sm" onClick={salvaNome}>Salva</button>
                        </span>
                      ) : <strong style={{ cursor: 'pointer', color: '#1A3A5C' }} onClick={() => setAperto(sc.id)}>{sc.nome}</strong>}
                    </td>
                    <td style={{ fontSize: '0.78rem', color: '#5A6B7D' }}>{sc.ha_sfondo ? (sc.sfondo_origine || 'Immagine') : 'Nessuno'}</td>
                    <td style={{ fontSize: '0.78rem', color: sc.scala ? '#27AE60' : '#8A6D00' }}>{sc.scala ? 'Tarata' : 'Non tarata'}</td>
                    <td style={{ fontSize: '0.82rem' }}>{sc.n_elementi}</td>
                    <td>
                      <label style={{ fontSize: '0.78rem', display: 'flex', gap: 6, alignItems: 'center', cursor: 'pointer' }}>
                        <input type="checkbox" checked={sc.includi_psc} data-testid={`includi-${sc.id}`} onChange={e => includi(sc, e.target.checked)} />
                        da includere nel PSC
                      </label>
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      <button className="btn btn-gold btn-sm" onClick={() => setAperto(sc.id)} style={{ marginRight: 6 }}>Apri →</button>
                      <button className="btn btn-ghost btn-sm" onClick={() => setRinomina({ id: sc.id, nome: sc.nome })} style={{ marginRight: 6 }}>✏️</button>
                      <button className="btn btn-ghost btn-sm" onClick={() => duplica(sc)} style={{ marginRight: 6 }}>Duplica</button>
                      <button className="btn btn-danger btn-sm" onClick={() => elimina(sc)}>🗑</button>
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
