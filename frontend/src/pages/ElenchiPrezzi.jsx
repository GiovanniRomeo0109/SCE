import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getElenchi, caricaElenco, rinominaElenco, eliminaElenco, mappaturaElenco, cercaVociElenco,
} from '../utils/api';
import { useNotify } from '../App';
import MappaturaColonne from '../components/MappaturaColonne';

/**
 * Elenchi prezzi dell'account (+ elenchi di sistema caricati dall'amministratore).
 * Sono il secondo e terzo livello della ricerca prezzi: progetto → account → sistema.
 * La lettura avviene senza AI e non consuma budget.
 */
export default function ElenchiPrezzi() {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [dati, setDati] = useState(null);
  const [nome, setNome] = useState('');
  const [sistema, setSistema] = useState(false);
  const [caricamento, setCaricamento] = useState(false);
  const [mappatura, setMappatura] = useState(null);     // elenco in attesa di mappatura
  const [inCorso, setInCorso] = useState(false);
  const [rinomina, setRinomina] = useState({ id: null, nome: '' });
  const [consulta, setConsulta] = useState(null);       // { elenco, q, voci }
  const inputRef = useRef(null);

  const carica = useCallback(() => {
    getElenchi()
      .then(r => setDati(r.data))
      .catch(e => { setDati({ elenchi: [] }); notifyRef.current(e.message, 'error'); });
  }, []);

  useEffect(() => { carica(); }, [carica]);

  const invia = async (file) => {
    if (!file) return;
    setCaricamento(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('nome', nome.trim() || file.name);
      fd.append('sistema', sistema ? 'true' : 'false');
      const r = await caricaElenco(fd);
      if (r.data.stato === 'pronto') notify(`Elenco letto: ${r.data.n_voci} voci`, 'success');
      else if (r.data.stato === 'mappatura_richiesta') { notify('Indica le colonne dell\'elenco', 'info'); setMappatura(r.data); }
      else notify(r.data.errore || 'Impossibile leggere l\'elenco', 'error');
      setNome(''); setSistema(false);
      carica();
    } catch (e) { notify(e.message, 'error'); }
    finally { setCaricamento(false); if (inputRef.current) inputRef.current.value = ''; }
  };

  const confermaMappatura = async (m) => {
    setInCorso(true);
    try {
      const r = await mappaturaElenco(mappatura.id, m);
      notify(`Elenco letto: ${r.data.n_voci} voci`, 'success');
      setMappatura(null);
      carica();
    } catch (e) { notify(e.message, 'error'); }
    finally { setInCorso(false); }
  };

  const salvaNome = async () => {
    try { await rinominaElenco(rinomina.id, rinomina.nome); setRinomina({ id: null, nome: '' }); carica(); }
    catch (e) { notify(e.message, 'error'); }
  };

  const elimina = async (el) => {
    const extra = el.livello === 'sistema' ? ' È un elenco di sistema: sparirà per tutti gli utenti.' : '';
    if (!window.confirm(`Eliminare l'elenco "${el.nome}"?${extra}`)) return;
    try { await eliminaElenco(el.id); notify('Elenco eliminato', 'success'); carica(); }
    catch (e) { notify(e.message, 'error'); }
  };

  const cerca = async (elenco, q) => {
    try {
      const r = await cercaVociElenco(elenco.id, q);
      setConsulta({ elenco, q, voci: r.data });
    } catch (e) { notify(e.message, 'error'); }
  };

  const puoModificare = (el) => el.livello === 'account' || dati?.puo_caricare_sistema;

  return (
    <div>
      <div className="page-header">
        <h1>💶 Elenchi prezzi</h1>
        <p>Usati per stimare i costi della sicurezza: prima l'elenco del progetto, poi i tuoi elenchi, poi quelli di sistema</p>
      </div>

      <div className="card" style={{ marginBottom: 20, maxWidth: 820 }}>
        <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 10 }}>📥 Carica un elenco prezzi</div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <input className="form-control" style={{ flex: 1, minWidth: 240 }}
            placeholder="Nome (es. Prezzario Veneto 2026 — Sicurezza)"
            value={nome} onChange={e => setNome(e.target.value)} />
          {dati?.puo_caricare_sistema && (
            <label style={{ fontSize: '0.82rem', display: 'flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={sistema} onChange={e => setSistema(e.target.checked)} />
              Elenco di sistema (visibile a tutti)
            </label>
          )}
          <button className="btn btn-gold" disabled={caricamento} onClick={() => inputRef.current?.click()}>
            {caricamento ? 'Lettura in corso…' : 'Scegli file…'}
          </button>
          <input ref={inputRef} type="file" accept=".xml,.ods,.xls,.xlsx,.pdf" style={{ display: 'none' }}
            onChange={e => invia(e.target.files?.[0])} />
        </div>
        <p style={{ fontSize: '0.76rem', color: '#8A9BB0', margin: '8px 0 0' }}>
          Formati: XML (prezzari regionali), ODS, XLS, XLSX, PDF con testo. I PDF scansionati non sono supportati.
          Il file viene cancellato dopo la lettura: restano le voci.
        </p>
      </div>

      {mappatura && (
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: '0.85rem', marginBottom: 6 }}>Elenco: <strong>{mappatura.nome}</strong></div>
          <MappaturaColonne anteprima={mappatura.anteprima} inCorso={inCorso}
            onConferma={confermaMappatura} onAnnulla={() => setMappatura(null)} />
        </div>
      )}

      <div className="card">
        {!dati ? <div style={{ color: '#8A9BB0' }}>Caricamento…</div> : dati.elenchi.length === 0 ? (
          <div className="empty-state"><div className="empty-icon">💶</div><p>Nessun elenco prezzi caricato</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Elenco</th><th>Livello</th><th>Voci</th><th>Stato</th><th></th></tr></thead>
              <tbody>
                {dati.elenchi.map(el => (
                  <tr key={el.id}>
                    <td>
                      {rinomina.id === el.id ? (
                        <div style={{ display: 'flex', gap: 6 }}>
                          <input className="form-control" value={rinomina.nome} autoFocus
                            onChange={e => setRinomina({ id: el.id, nome: e.target.value })}
                            onKeyDown={e => e.key === 'Enter' && salvaNome()} />
                          <button className="btn btn-gold btn-sm" onClick={salvaNome}>Salva</button>
                        </div>
                      ) : (
                        <>
                          <strong>{el.nome}</strong>
                          <div style={{ fontSize: '0.72rem', color: '#8A9BB0' }}>{el.nome_file}</div>
                        </>
                      )}
                    </td>
                    <td>
                      <span className={`badge ${el.livello === 'sistema' ? 'badge-psc' : 'badge-pos'}`}>
                        {el.livello === 'sistema' ? '🌐 Sistema' : '👤 Account'}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.85rem' }}>{el.n_voci}</td>
                    <td style={{ fontSize: '0.8rem' }}>
                      {el.stato === 'pronto' && <span style={{ color: '#27AE60' }}>Pronto</span>}
                      {el.stato === 'mappatura_richiesta' && (
                        <button className="btn btn-gold btn-sm" onClick={() => setMappatura(el)}>🧩 Indica colonne</button>
                      )}
                      {el.stato === 'errore' && <span style={{ color: '#C0392B' }}>{el.errore}</span>}
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {el.stato === 'pronto' && (
                        <button className="btn btn-ghost btn-sm" style={{ marginRight: 6 }} onClick={() => cerca(el, '')}>🔍 Consulta</button>
                      )}
                      {puoModificare(el) && (
                        <>
                          <button className="btn btn-ghost btn-sm" style={{ marginRight: 6 }}
                            onClick={() => setRinomina({ id: el.id, nome: el.nome })}>✏️</button>
                          <button className="btn btn-danger btn-sm" onClick={() => elimina(el)}>🗑</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {consulta && (
        <div className="card" style={{ marginTop: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <strong style={{ color: '#1A3A5C' }}>🔍 {consulta.elenco.nome}</strong>
            <button className="btn btn-ghost btn-sm" onClick={() => setConsulta(null)}>✕ Chiudi</button>
          </div>
          <input className="form-control" placeholder="Cerca per codice o parole della descrizione…"
            defaultValue={consulta.q} onKeyDown={e => e.key === 'Enter' && cerca(consulta.elenco, e.target.value)} />
          <div className="table-wrapper" style={{ marginTop: 10, maxHeight: 400, overflow: 'auto' }}>
            <table style={{ fontSize: '0.78rem' }}>
              <thead><tr><th>Codice</th><th>Descrizione</th><th>UM</th><th>Prezzo €</th></tr></thead>
              <tbody>
                {consulta.voci.map((v, i) => (
                  <tr key={i}>
                    <td style={{ whiteSpace: 'nowrap' }}>{v.codice}</td>
                    <td>{v.descrizione}</td>
                    <td>{v.um}</td>
                    <td style={{ textAlign: 'right' }}>{v.prezzo?.toLocaleString('it-IT', { minimumFractionDigits: 2 })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ fontSize: '0.72rem', color: '#8A9BB0', marginTop: 6 }}>Mostrate al massimo 50 voci per ricerca.</div>
        </div>
      )}
    </div>
  );
}
