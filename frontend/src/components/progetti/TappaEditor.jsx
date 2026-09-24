import { useState, useEffect, useRef } from 'react';
import { salvaTappa, generaTappa, tappaVerificata, salvaDatiCSP, stimaTappe } from '../../utils/api';
import { useNotify } from '../../App';
import UominiGiorno from './UominiGiorno';
import StimaCosti from './StimaCosti';
import PresidiEmergenza from './PresidiEmergenza';

const DAV = 'DA VERIFICARE';
const haDAV = (t) => (t || '').toUpperCase().includes(DAV);
const clona = (x) => JSON.parse(JSON.stringify(x));
const euro = (n) => `€ ${Number(n || 0).toFixed(2).replace('.', ',')}`;

/** Textarea che cresce con il contenuto. */
function Area({ value, onChange, minRows = 2, stile = {}, disabled }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) { ref.current.style.height = 'auto'; ref.current.style.height = ref.current.scrollHeight + 'px'; }
  }, [value]);
  return (
    <textarea ref={ref} value={value} rows={minRows} disabled={disabled}
      onChange={e => onChange(e.target.value)}
      style={{ width: '100%', resize: 'vertical', boxSizing: 'border-box', font: 'inherit',
        border: '1px solid #DCE3ED', borderRadius: 6, padding: '6px 8px', overflow: 'hidden', ...stile }} />
  );
}

export default function TappaEditor({ progettoId, tappa, tappe, dataInizio, occupato, onAggiorna, onModificata, onApriSchema, manuale }) {
  const notify = useNotify();
  const [sezioni, setSezioni] = useState([]);
  const [modificata, setModificata] = useState(false);
  const [nota, setNota] = useState('');
  const [mostraNota, setMostraNota] = useState(false);
  const [data, setData] = useState(dataInizio || '');
  const [attesa, setAttesa] = useState(false);

  // Ricarica la copia locale quando si cambia tappa, oppure quando arriva un nuovo contenuto
  // dal server e il CSP non ha modifiche in corso (non si perde mai il lavoro non salvato)
  const contenutoServer = JSON.stringify(tappa.contenuto?.sezioni || []);
  const numeroPrecedente = useRef(null);
  const modificataRef = useRef(false);
  modificataRef.current = modificata;
  useEffect(() => {
    const cambioTappa = numeroPrecedente.current !== tappa.numero;
    numeroPrecedente.current = tappa.numero;
    if (cambioTappa || !modificataRef.current) {
      setSezioni(JSON.parse(contenutoServer));
      setModificata(false);
    }
    if (cambioTappa) { setNota(''); setMostraNota(false); }
  }, [tappa.numero, contenutoServer]);
  useEffect(() => { setData(dataInizio || ''); }, [dataInizio]);
  // Il componente padre chiede conferma prima di cambiare tappa con modifiche non salvate
  useEffect(() => { if (onModificata) onModificata(modificata); }, [modificata, onModificata]);

  const attiva = ['in_coda', 'in_generazione'].includes(tappa.stato);
  const bloccata = attiva || occupato;

  const cambiaTesto = (i, v) => { setSezioni(s => { const n = clona(s); n[i].testo = v; return n; }); setModificata(true); };
  const cambiaCella = (i, r, c, v) => { setSezioni(s => { const n = clona(s); n[i].righe[r][c] = v; return n; }); setModificata(true); };
  const aggiungiRiga = (i) => { setSezioni(s => { const n = clona(s); n[i].righe.push(n[i].colonne.map(() => '')); return n; }); setModificata(true); };
  const eliminaRiga = (i, r) => { setSezioni(s => { const n = clona(s); n[i].righe.splice(r, 1); return n; }); setModificata(true); };

  // Tappe successive che la cascata rigenererebbe / salterebbe
  const successive = tappe.filter(t => t.numero > tappa.numero && t.contenuto);
  const daRigenerare = successive.filter(t => !t.modificata_a_mano).map(t => t.numero);
  const daRicontrollare = successive.filter(t => t.modificata_a_mano).map(t => t.numero);

  const conferma = async (numeri, azione) => {
    if (!numeri.length) return window.confirm(`${azione}?`);
    let stima = '';
    try { const r = await stimaTappe(progettoId, numeri); stima = ` Costo stimato: ${euro(r.data.stima_eur)}.`; } catch { /* stima non essenziale */ }
    return window.confirm(`${azione}?\n\nVerranno rigenerate automaticamente le tappe ${numeri.join(', ')}.${stima}` +
      (daRicontrollare.length ? `\nLe tappe ${daRicontrollare.join(', ')}, modificate a mano, non verranno toccate ma saranno segnate "da ricontrollare".` : ''));
  };

  const salva = async () => {
    if (!(await conferma(daRigenerare, 'Salvare le modifiche'))) return;
    setAttesa(true);
    try {
      const r = await salvaTappa(progettoId, tappa.numero, sezioni);
      setModificata(false);
      notify(r.data.rigenerate.length
        ? `Modifiche salvate: rigenerazione delle tappe ${r.data.rigenerate.join(', ')} avviata`
        : 'Modifiche salvate', 'success');
      onAggiorna();
    } catch (e) { notify(e.message, 'error'); }
    finally { setAttesa(false); }
  };

  const annulla = () => { setSezioni(clona(tappa.contenuto?.sezioni || [])); setModificata(false); };

  const genera = async () => {
    const numeri = [tappa.numero, ...(tappa.contenuto ? daRigenerare : [])];
    let msg = tappa.contenuto ? `Rigenerare la tappa ${tappa.numero}` : `Generare la tappa ${tappa.numero}`;
    if (tappa.modificata_a_mano) msg += ' (le tue modifiche manuali verranno sostituite)';
    let stima = '';
    try { const r = await stimaTappe(progettoId, numeri); stima = `\n\nCosto stimato: ${euro(r.data.stima_eur)}.`; } catch { /* stima non essenziale */ }
    const casc = tappa.contenuto && daRigenerare.length ? `\nIn seguito verranno rigenerate le tappe ${daRigenerare.join(', ')}.` : '';
    if (!window.confirm(`${msg}?${casc}${stima}`)) return;
    setAttesa(true);
    try {
      await generaTappa(progettoId, tappa.numero, nota);
      notify(`Tappa ${tappa.numero} in coda di generazione`, 'success');
      setMostraNota(false);
      onAggiorna();
    } catch (e) { notify(e.message, 'error'); }
    finally { setAttesa(false); }
  };

  const verificata = async () => {
    try { await tappaVerificata(progettoId, tappa.numero); onAggiorna(); }
    catch (e) { notify(e.message, 'error'); }
  };

  const salvaData = async (v) => {
    setData(v);
    try { await salvaDatiCSP(progettoId, { data_inizio_lavori: v || null }); onAggiorna(); }
    catch (e) { notify(e.message, 'error'); }
  };

  const nDav = sezioni.reduce((n, s) => n + (s.tipo === 'testo'
    ? (s.testo || '').toUpperCase().split(DAV).length - 1
    : (s.righe || []).reduce((m, r) => m + r.filter(haDAV).length, 0)), 0);

  return (
    <div className="card" data-testid={`tappa-${tappa.numero}`}>
      {/* Intestazione */}
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', marginBottom: 10 }}>
        <div>
          <div style={{ fontSize: '0.72rem', color: '#C88B2A', fontWeight: 700 }}>TAPPA {tappa.numero} DI 12</div>
          <h3 style={{ margin: '2px 0 6px', color: '#1A3A5C' }}>{tappa.titolo}</h3>
          <div style={{ fontSize: '0.8rem', color: '#5A6B7D', maxWidth: 720 }}>{tappa.obiettivo}</div>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {tappa.da_ricontrollare && (
            <button className="btn btn-gold btn-sm" onClick={verificata} disabled={bloccata}>✔ Segna come verificata</button>
          )}
          {!attiva && !manuale && (
            <button className="btn btn-ghost btn-sm" onClick={() => setMostraNota(v => !v)} disabled={bloccata || attesa}>
              {tappa.contenuto ? '↻ Rigenera…' : '✨ Genera…'}
            </button>
          )}
        </div>
      </div>

      {/* Avvisi di stato */}
      {tappa.da_ricontrollare && (
        <div className="warn-box" style={{ marginBottom: 10, fontSize: '0.82rem' }}>
          ⚠️ <strong>Da ricontrollare:</strong> una tappa precedente è cambiata ma questa, modificata a mano,
          non è stata rigenerata. Verifica che sia ancora coerente, poi premi "Segna come verificata".
        </div>
      )}
      {tappa.da_aggiornare && !tappa.da_ricontrollare && (
        <div className="warn-box" style={{ marginBottom: 10, fontSize: '0.82rem' }}>
          ⚠️ <strong>Da aggiornare:</strong> una tappa precedente è cambiata ma la rigenerazione di questa
          si è interrotta. Puoi rigenerarla o segnarla come verificata.
          <button className="btn btn-ghost btn-sm" style={{ marginLeft: 8 }} onClick={verificata}>Segna come verificata</button>
        </div>
      )}
      {tappa.stato === 'errore' && (
        <div className="warn-box" style={{ marginBottom: 10, fontSize: '0.82rem', borderColor: '#C0392B' }}>
          ❌ {tappa.errore || 'Errore nella generazione'}
        </div>
      )}
      {attiva && (
        <div className="info-box" style={{ marginBottom: 10, fontSize: '0.82rem' }}>
          ⏳ {tappa.stato === 'in_generazione' ? 'Generazione in corso…' : 'In coda: verrà generata dopo le tappe precedenti.'}
        </div>
      )}

      {/* Data di inizio lavori (tappa QUANDO) */}
      {tappa.numero === 5 && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '6px 0 14px', fontSize: '0.85rem' }}>
          <label htmlFor="data-inizio"><strong>Data di inizio lavori</strong> (settimana 1 del cronoprogramma):</label>
          <input id="data-inizio" type="date" className="form-control" style={{ maxWidth: 180 }}
            value={data} onChange={e => salvaData(e.target.value)} disabled={bloccata} />
          {!data && <span style={{ color: '#5A6B7D' }} data-testid="nota-giorni-cantiere">Data non indicata: il cronoprogramma usa i giorni di cantiere (1° giorno = lunedì, settimana di 5 giorni lavorativi)</span>}
        </div>
      )}

      {/* Nota per la (ri)generazione */}
      {mostraNota && !attiva && (
        <div style={{ background: '#F8F5F0', borderRadius: 8, padding: 12, marginBottom: 14 }}>
          <div style={{ fontSize: '0.82rem', marginBottom: 6 }}>
            Nota per l'AI (facoltativa), es. <em>"considera anche l'impianto fotovoltaico in copertura"</em>:
          </div>
          <Area value={nota} onChange={setNota} />
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={() => setMostraNota(false)}>Annulla</button>
            <button className="btn btn-gold btn-sm" onClick={genera} disabled={attesa}>
              {tappa.contenuto ? 'Rigenera la tappa' : 'Genera la tappa'}
            </button>
          </div>
        </div>
      )}

      {!tappa.contenuto && !attiva && (
        <div className="empty-state" style={{ padding: 30 }}>
          <div className="empty-icon">✨</div>
          <p>Tappa non ancora generata. Usa "Genera…" oppure "Genera bozza completa".</p>
        </div>
      )}

      {/* Sezioni */}
      {tappa.contenuto && sezioni.map((s, i) => (
        <div key={s.id} style={{ marginBottom: 18 }}>
          <div style={{ fontWeight: 700, color: '#1A3A5C', fontSize: '0.9rem', marginBottom: 6 }}>{s.titolo}</div>
          {s.tipo === 'testo' ? (
            <>
              <Area value={s.testo || ''} onChange={v => cambiaTesto(i, v)} minRows={3} disabled={bloccata}
                stile={haDAV(s.testo) ? { background: '#FFF8E1', borderColor: '#E0A800' } : {}} />
              {haDAV(s.testo) && <div style={{ fontSize: '0.72rem', color: '#8A6D00' }}>⚠️ Il testo contiene dati DA VERIFICARE</div>}
            </>
          ) : (
            <div className="table-wrapper" style={{ overflowX: 'auto' }}>
              <table style={{ fontSize: '0.78rem', minWidth: 120 * s.colonne.length }}>
                <thead>
                  <tr>{s.colonne.map(c => <th key={c}>{c}</th>)}<th style={{ width: 36 }}></th></tr>
                </thead>
                <tbody>
                  {s.righe.map((riga, r) => (
                    <tr key={r}>
                      {riga.map((cella, c) => (
                        <td key={c} style={{ padding: 3, background: haDAV(cella) ? '#FFF4D6' : undefined }}>
                          <Area value={cella} onChange={v => cambiaCella(i, r, c, v)} minRows={1} disabled={bloccata}
                            stile={{ fontSize: '0.78rem', padding: '4px 6px', background: haDAV(cella) ? '#FFF4D6' : 'white' }} />
                        </td>
                      ))}
                      <td style={{ padding: 3 }}>
                        <button className="btn btn-ghost btn-sm" title="Elimina riga" disabled={bloccata}
                          onClick={() => eliminaRiga(i, r)}>✕</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <button className="btn btn-ghost btn-sm" style={{ marginTop: 6 }} disabled={bloccata}
                onClick={() => aggiungiRiga(i)}>＋ Aggiungi riga</button>
            </div>
          )}
        </div>
      ))}

      {/* Blocco 4: uomini-giorno (tappa 5) e stima dei costi (tappa 11), sui dati salvati della tappa */}
      {tappa.contenuto && !attiva && tappa.numero === 5 && (
        <UominiGiorno progettoId={progettoId} versione={`${tappa.generata_at}|${contenutoServer.length}|${dataInizio}`} />
      )}
      {tappa.contenuto && !attiva && tappa.numero === 9 && (
        <PresidiEmergenza progettoId={progettoId} onAggiorna={onAggiorna} onApriSchema={onApriSchema} manuale={manuale} />
      )}
      {tappa.contenuto && !attiva && tappa.numero === 11 && (
        <StimaCosti progettoId={progettoId} versione={`${tappa.generata_at}|${contenutoServer.length}`} />
      )}

      {/* Dati da verificare segnalati dall'AI */}
      {tappa.contenuto?.da_verificare?.length > 0 && (
        <div style={{ background: '#FFF8E1', borderRadius: 8, padding: '10px 14px', fontSize: '0.8rem', marginBottom: 14 }}>
          <strong>Dati da verificare in questa tappa</strong> (inseriti anche nel questionario del sopralluogo):
          <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
            {tappa.contenuto.da_verificare.map((d, k) => (
              <li key={k}>{d.campo}{d.motivo ? ` — ${d.motivo}` : ''}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Barra di salvataggio */}
      {tappa.contenuto && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10,
          borderTop: '1px solid #EEF1F5', paddingTop: 12 }}>
          <div style={{ fontSize: '0.75rem', color: '#8A9BB0' }}>
            {manuale ? '✍️ Compilata a mano · ' : tappa.modificata_a_mano ? '✔ Modificata da te · ' : '🤖 Generata dall\'AI · '}
            {nDav > 0 ? `${nDav} dati DA VERIFICARE` : 'nessun dato da verificare'}
            {modificata && <strong style={{ color: '#C88B2A' }}> · modifiche non salvate</strong>}
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={annulla} disabled={!modificata || attesa}>Annulla modifiche</button>
            <button className="btn btn-gold btn-sm" onClick={salva} disabled={!modificata || attesa || bloccata}>
              {attesa ? 'Salvataggio…' : '💾 Salva modifiche'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
