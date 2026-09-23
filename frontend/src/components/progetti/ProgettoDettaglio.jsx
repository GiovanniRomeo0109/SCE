import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getProgetto, rinominaProgetto, caricaDocumentiProgetto, correggiTipoDocumento,
  rielaboraDocumento, eliminaDocumentoProgetto, getDatiDocumento, mappaturaDocumento,
} from '../../utils/api';
import { useNotify } from '../../App';
import MappaturaColonne from '../MappaturaColonne';
import TappePSC from './TappePSC';
import Questionario from './Questionario';

const COLORI_STATO = {
  completato: '#27AE60', in_elaborazione: '#1A3A5C', in_coda: '#8A9BB0',
  da_classificare: '#8A9BB0', in_attesa: '#C88B2A', mappatura_richiesta: '#C88B2A',
  errore: '#C0392B', non_supportato: '#C0392B',
};
const COLORI_AVVISO = {
  demo:   { bg: '#FFF4D6', bordo: '#E0A800', icona: '⏳' },
  limite: { bg: '#FFF4D6', bordo: '#E0A800', icona: '🕒' },
  info:   { bg: '#EEF4FA', bordo: '#B8CCE0', icona: 'ℹ️' },
};

const iconaFile = (est) => est === 'pdf' ? '📕' : est === 'docx' ? '📘'
  : ['xlsx', 'xls', 'ods'].includes(est) ? '📗' : est === 'xml' ? '🧾' : '🖼️';
const mb = (b) => (b / 1024 / 1024).toFixed(1);

export default function ProgettoDettaglio({ progettoId, onIndietro }) {
  const notify = useNotify();
  const [p, setP] = useState(null);
  const [caricamento, setCaricamento] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [nome, setNome] = useState('');
  const [modificaNome, setModificaNome] = useState(false);
  const [datiAperti, setDatiAperti] = useState(null);      // { documento, blocchi, elenco }
  const [mappatura, setMappatura] = useState(null);        // { docId, anteprima }
  const [inCorso, setInCorso] = useState(false);
  const [vista, setVista] = useState('documenti');        // documenti | tappe | questionario
  const inputRef = useRef(null);
  // notify cambia a ogni render di App: lo tengo in un ref per non rilanciare il caricamento
  const notifyRef = useRef(notify);
  notifyRef.current = notify;

  const carica = useCallback(async () => {
    try {
      const r = await getProgetto(progettoId);
      setP(r.data);
      setNome(prev => (prev ? prev : r.data.nome));
    } catch (e) {
      notifyRef.current(e.message, 'error');
    }
  }, [progettoId]);

  useEffect(() => { carica(); }, [carica]);

  // Aggiornamento automatico finché ci sono documenti in lavorazione
  useEffect(() => {
    if (!p?.in_lavorazione) return;
    const t = setInterval(carica, 3000);
    return () => clearInterval(t);
  }, [p?.in_lavorazione, carica]);

  const inviaFile = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    setCaricamento(true);
    try {
      const fd = new FormData();
      files.forEach(f => fd.append('files', f));
      const r = await caricaDocumentiProgetto(progettoId, fd);
      if (r.data.caricati.length) notify(`${r.data.caricati.length} documenti caricati: elaborazione avviata`, 'success');
      r.data.rifiutati.forEach(x => notify(`${x.file}: ${x.motivo}`, 'error'));
      await carica();
    } catch (e) {
      notify(e.message, 'error');
    } finally {
      setCaricamento(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  };

  const salvaNome = async () => {
    if (!nome.trim()) return;
    try {
      await rinominaProgetto(progettoId, nome.trim());
      setModificaNome(false);
      carica();
    } catch (e) { notify(e.message, 'error'); }
  };

  const cambiaTipo = async (doc, tipo) => {
    try {
      const r = await correggiTipoDocumento(progettoId, doc.id, tipo);
      if (r.data.rielaborazione_consigliata) {
        notify('Tipo aggiornato. Il documento era già stato elaborato: usa "Rielabora" per rileggerlo con il nuovo tipo.', 'info');
      }
      carica();
    } catch (e) { notify(e.message, 'error'); }
  };

  const rielabora = async (doc) => {
    if (!window.confirm(`Rielaborare "${doc.nome_file}"? L'operazione usa l'AI e consuma budget.`)) return;
    try { await rielaboraDocumento(progettoId, doc.id); carica(); }
    catch (e) { notify(e.message, 'error'); }
  };

  const elimina = async (doc) => {
    if (!window.confirm(`Eliminare "${doc.nome_file}" e i dati estratti?`)) return;
    try { await eliminaDocumentoProgetto(progettoId, doc.id); carica(); }
    catch (e) { notify(e.message, 'error'); }
  };

  const apriDati = async (doc) => {
    try { const r = await getDatiDocumento(progettoId, doc.id); setDatiAperti(r.data); }
    catch (e) { notify(e.message, 'error'); }
  };

  const apriMappatura = async (doc) => {
    try {
      const r = await getDatiDocumento(progettoId, doc.id);
      setMappatura({ docId: doc.id, anteprima: r.data.elenco?.anteprima });
    } catch (e) { notify(e.message, 'error'); }
  };

  const confermaMappatura = async (m) => {
    setInCorso(true);
    try {
      const r = await mappaturaDocumento(progettoId, mappatura.docId, m);
      notify(`Elenco prezzi letto: ${r.data.n_voci} voci`, 'success');
      setMappatura(null);
      carica();
    } catch (e) { notify(e.message, 'error'); }
    finally { setInCorso(false); }
  };

  if (!p) return <div style={{ padding: 40, color: '#8A9BB0' }}>Caricamento progetto…</div>;

  const chiuso = p.stato === 'chiuso';
  const spazioUsato = p.documenti.filter(d => d.file_disponibile).reduce((s, d) => s + d.dimensione, 0);

  return (
    <div>
      {/* Intestazione */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 18 }}>
        <button className="btn btn-ghost btn-sm" onClick={onIndietro}>← Progetti</button>
        {modificaNome ? (
          <>
            <input className="form-control" style={{ maxWidth: 360 }} value={nome} autoFocus
              onChange={e => setNome(e.target.value)} onKeyDown={e => e.key === 'Enter' && salvaNome()} />
            <button className="btn btn-gold btn-sm" onClick={salvaNome}>Salva</button>
            <button className="btn btn-ghost btn-sm" onClick={() => { setModificaNome(false); setNome(p.nome); }}>Annulla</button>
          </>
        ) : (
          <>
            <h2 style={{ margin: 0, color: '#1A3A5C' }}>📗 {p.nome}</h2>
            {!p.is_esempio && <button className="btn btn-ghost btn-sm" onClick={() => setModificaNome(true)}>✏️ Rinomina</button>}
            {p.is_esempio && <span className="badge badge-psc">Progetto di esempio</span>}
          </>
        )}
      </div>

      {/* Avvisi */}
      {p.avvisi.map((a, i) => {
        const c = COLORI_AVVISO[a.tipo] || COLORI_AVVISO.info;
        return (
          <div key={i} style={{ background: c.bg, border: `1px solid ${c.bordo}`, borderRadius: 8,
            padding: '10px 14px', marginBottom: 10, fontSize: '0.84rem', color: '#2C3E50' }}>
            {c.icona} {a.testo}
          </div>
        );
      })}

      {/* Schede */}
      <div style={{ display: 'flex', gap: 4, borderBottom: '2px solid #EEF1F5', margin: '4px 0 18px' }}>
        {[['documenti', `📄 Documenti (${p.documenti.length})`], ['tappe', '🧭 Tappe PSC'], ['questionario', '📝 Questionario sopralluogo']].map(([k, label]) => (
          <button key={k} onClick={() => setVista(k)} data-testid={`scheda-${k}`}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px 14px', fontSize: '0.88rem',
              fontWeight: vista === k ? 700 : 500, color: vista === k ? '#1A3A5C' : '#8A9BB0',
              borderBottom: `2px solid ${vista === k ? '#C88B2A' : 'transparent'}`, marginBottom: -2 }}>
            {label}
          </button>
        ))}
      </div>

      {vista === 'tappe' && <TappePSC progettoId={progettoId} />}
      {vista === 'questionario' && <Questionario progettoId={progettoId} onApplicate={() => setVista('tappe')} />}

      {vista === 'documenti' && (<>
      {/* Caricamento */}
      {!chiuso && (
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); inviaFile(e.dataTransfer.files); }}
          onClick={() => !caricamento && inputRef.current?.click()}
          style={{
            border: `2px dashed ${dragging ? '#1A3A5C' : '#C88B2A'}`, borderRadius: 12,
            padding: '22px 20px', textAlign: 'center', cursor: caricamento ? 'wait' : 'pointer',
            background: dragging ? '#EEF4FA' : '#FFFDF9', margin: '6px 0 20px',
          }}>
          <div style={{ fontSize: '2rem' }}>{caricamento ? '⏳' : '📂'}</div>
          <div style={{ fontWeight: 700, color: '#1A3A5C' }}>
            {caricamento ? 'Caricamento in corso…' : 'Trascina qui i documenti del progetto o clicca per selezionarli'}
          </div>
          <div style={{ fontSize: '0.74rem', color: '#8A9BB0', marginTop: 4 }}>
            PDF · Word · Excel/ODS · XML · JPG/PNG — max {p.limiti.mb_file} MB per file,
            {' '}{p.limiti.mb_progetto} MB per progetto (usati {mb(spazioUsato)} MB) · DWG: esporta in PDF
          </div>
          <div style={{ fontSize: '0.74rem', color: '#8A9BB0', marginTop: 2 }}>
            L'AI riconosce il tipo di ogni documento: puoi correggerlo nella tabella qui sotto.
          </div>
          <input ref={inputRef} type="file" multiple style={{ display: 'none' }}
            accept=".pdf,.docx,.xlsx,.xls,.ods,.xml,.jpg,.jpeg,.png,.dwg"
            onChange={e => inviaFile(e.target.files)} />
        </div>
      )}

      {/* Mappatura colonne */}
      {mappatura && mappatura.anteprima && (
        <div style={{ marginBottom: 20 }}>
          <MappaturaColonne anteprima={mappatura.anteprima} inCorso={inCorso}
            onConferma={confermaMappatura} onAnnulla={() => setMappatura(null)} />
        </div>
      )}

      {/* Documenti */}
      <div className="card">
        <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 12 }}>
          Documenti ({p.documenti.length}) {p.in_lavorazione && <span style={{ fontWeight: 400, fontSize: '0.8rem', color: '#8A9BB0' }}>· aggiornamento automatico</span>}
        </div>
        {p.documenti.length === 0 ? (
          <div className="empty-state"><div className="empty-icon">📄</div><p>Nessun documento caricato</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead>
                <tr><th>Documento</th><th>Tipo</th><th>Stato</th><th>Azioni</th></tr>
              </thead>
              <tbody>
                {p.documenti.map(d => (
                  <tr key={d.id}>
                    <td style={{ minWidth: 200 }}>
                      <span style={{ marginRight: 6 }}>{iconaFile(d.estensione)}</span>
                      <strong style={{ wordBreak: 'break-all' }}>{d.nome_file}</strong>
                      <div style={{ fontSize: '0.72rem', color: '#8A9BB0' }}>
                        {mb(d.dimensione)} MB{d.pagine ? ` · ${d.pagine} pagine` : ''}
                        {d.estensione === 'pdf' && d.ha_testo === false ? ' · letto come immagine' : ''}
                        {!d.file_disponibile ? ' · file originale eliminato' : ''}
                      </div>
                    </td>
                    <td style={{ minWidth: 190 }}>
                      {d.tipo ? (
                        <select className="form-control" value={d.tipo} disabled={chiuso}
                          onChange={e => cambiaTipo(d, e.target.value)} style={{ fontSize: '0.8rem' }}>
                          {p.tipi.map(t => <option key={t.codice} value={t.codice}>{t.etichetta}</option>)}
                        </select>
                      ) : <span style={{ fontSize: '0.8rem', color: '#8A9BB0' }}>Riconoscimento…</span>}
                      {d.tipo && (
                        <div style={{ fontSize: '0.68rem', color: '#8A9BB0', marginTop: 2 }}>
                          {d.tipo_corretto_da_csp ? '✔ indicato da te' : '🤖 riconosciuto dall\'AI'}
                        </div>
                      )}
                    </td>
                    <td style={{ minWidth: 180 }}>
                      <div style={{ fontSize: '0.8rem', fontWeight: 600, color: COLORI_STATO[d.stato] || '#5A6B7D' }}>
                        {d.stato_etichetta}
                        {d.stato === 'in_attesa' && d.motivo_attesa === 'budget' && ' · budget demo'}
                        {d.stato === 'in_attesa' && d.motivo_attesa === 'limite_giornaliero' && ' · riprende domani'}
                      </div>
                      {d.n_blocchi > 1 || d.stato === 'in_elaborazione' ? (
                        <>
                          <div style={{ height: 6, background: '#EEF1F5', borderRadius: 3, overflow: 'hidden', margin: '4px 0' }}>
                            <div style={{ width: `${d.avanzamento}%`, height: '100%', background: COLORI_STATO[d.stato] || '#1A3A5C', transition: 'width .4s' }} />
                          </div>
                          <div style={{ fontSize: '0.7rem', color: '#8A9BB0' }}>
                            {d.n_blocchi > 1 ? `Blocco ${d.blocchi_completati} di ${d.n_blocchi}` : ''}
                          </div>
                        </>
                      ) : null}
                      {d.errore && <div style={{ fontSize: '0.72rem', color: '#C0392B' }}>{d.errore}</div>}
                    </td>
                    <td style={{ whiteSpace: 'nowrap' }}>
                      {d.stato === 'mappatura_richiesta' && (
                        <button className="btn btn-gold btn-sm" onClick={() => apriMappatura(d)}>🧩 Indica colonne</button>
                      )}
                      {(d.stato === 'completato' || d.blocchi_completati > 0) && (
                        <button className="btn btn-ghost btn-sm" onClick={() => apriDati(d)} style={{ marginRight: 6 }}>👁 Dati</button>
                      )}
                      {d.file_disponibile && ['completato', 'errore', 'non_supportato'].includes(d.stato) && d.tipo !== 'elenco_prezzi' && (
                        <button className="btn btn-ghost btn-sm" onClick={() => rielabora(d)} style={{ marginRight: 6 }}>↻ Rielabora</button>
                      )}
                      {!chiuso && <button className="btn btn-danger btn-sm" onClick={() => elimina(d)}>🗑</button>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="info-box" style={{ marginTop: 16, fontSize: '0.8rem' }}>
        💡 I dati estratti dai documenti formano il fascicolo del progetto: quando l'elaborazione è
        terminata, passa alla scheda <strong>Tappe PSC</strong> per costruire il piano tappa per tappa.
      </div>
      </>)}

      {/* Dati estratti */}
      {datiAperti && (
        <div onClick={() => setDatiAperti(null)} style={{
          position: 'fixed', inset: 0, background: 'rgba(15,30,45,0.55)', zIndex: 1000,
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20,
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: 'white', borderRadius: 12, maxWidth: 820, width: '100%', maxHeight: '85vh',
            overflow: 'auto', padding: 24,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, color: '#1A3A5C' }}>{datiAperti.documento.nome_file}</h3>
              <button className="btn btn-ghost btn-sm" onClick={() => setDatiAperti(null)}>✕ Chiudi</button>
            </div>
            {datiAperti.elenco && (
              <p style={{ fontSize: '0.85rem' }}>
                Elenco prezzi <strong>{datiAperti.elenco.nome}</strong>: {datiAperti.elenco.n_voci} voci lette.
              </p>
            )}
            {datiAperti.blocchi.map(b => (
              <div key={b.blocco} style={{ marginBottom: 16 }}>
                {b.pagine_da && (
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#C88B2A', marginBottom: 4 }}>
                    Pagine {b.pagine_da}–{b.pagine_a}
                  </div>
                )}
                {b.dati?.sintesi && <p style={{ fontSize: '0.86rem', marginTop: 0 }}>{b.dati.sintesi}</p>}
                <details>
                  <summary style={{ cursor: 'pointer', fontSize: '0.8rem', color: '#1A3A5C' }}>Tutti i dati estratti</summary>
                  <pre style={{ fontSize: '0.72rem', background: '#F8F9FB', padding: 12, borderRadius: 6,
                    whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {JSON.stringify(b.dati, null, 2)}
                  </pre>
                </details>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
