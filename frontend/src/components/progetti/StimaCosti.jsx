import { useState, useEffect, useCallback, useRef } from 'react';
import { getCosti, aggiornaCosti, cercaVociCosti, modificaCosto, exportUrl } from '../../utils/api';
import { useNotify } from '../../App';

const euro = (v) => (v === null || v === undefined ? '—' : `€ ${Number(v).toLocaleString('it-IT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`);
// Numeri all'italiana: "1.234,56" → 1234.56 · "21,71" → 21.71 · "21.71" → 21.71 · "250.000" → 250000
const perNumero = (s) => {
  let t = String(s ?? '').trim().replace(/[€\s]/g, '');
  if (t === '') return null;
  if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.');
  else if (/^\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, '');   // solo separatori delle migliaia
  const n = Number(t);
  return Number.isFinite(n) ? n : NaN;
};
// Valore mostrato nei campi: virgola decimale, senza separatore delle migliaia
const inCampo = (v) => (v === null || v === undefined || v === '' ? '' : Number(v).toLocaleString('it-IT', { useGrouping: false, maximumFractionDigits: 4 }));
const LIVELLO = { progetto: 'Progetto', account: 'Account', sistema: 'Sistema', manuale: 'Manuale' };

function CampoCella({ valore, onSalva, testid, placeholder }) {
  const [t, setT] = useState(inCampo(valore));
  useEffect(() => { setT(inCampo(valore)); }, [valore]);
  const salva = () => {
    const n = perNumero(t);
    if (n === null || Number.isNaN(n) || n === valore) { setT(inCampo(valore)); return; }
    onSalva(n);
  };
  return (
    <input className="form-control" data-testid={testid} value={t} placeholder={placeholder}
      style={{ width: 90, padding: '4px 6px', fontSize: '0.8rem', textAlign: 'right', background: '#FFF8E1' }}
      onChange={e => setT(e.target.value)} onBlur={salva} onKeyDown={e => e.key === 'Enter' && e.target.blur()} />
  );
}

export default function StimaCosti({ progettoId, versione }) {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [d, setD] = useState(null);
  const [ricerca, setRicerca] = useState(null);     // { riga, q, voci }

  const carica = useCallback(async () => {
    try { const r = await getCosti(progettoId); setD(r.data); }
    catch (e) { notifyRef.current(e.message, 'error'); }
  }, [progettoId]);
  useEffect(() => { carica(); }, [carica, versione]);
  useEffect(() => {
    if (!d?.in_abbinamento) return;
    const t = setInterval(carica, 2500);
    return () => clearInterval(t);
  }, [d?.in_abbinamento, carica]);

  const modifica = async (riga, dati) => {
    try { await modificaCosto(progettoId, riga.id, dati); carica(); }
    catch (e) { notify(e.message, 'error'); }
  };

  const cerca = async (riga, q) => {
    try {
      const r = await cercaVociCosti(progettoId, q, riga.um_misura);
      setRicerca({ riga, q, voci: r.data });
    } catch (e) { notify(e.message, 'error'); }
  };

  const aggiorna = async () => {
    try {
      const r = await aggiornaCosti(progettoId);
      notify(r.data.da_abbinare ? `Ricerca prezzi avviata per ${r.data.da_abbinare} misure` : 'Stima allineata alla tabella delle misure', 'success');
      carica();
    } catch (e) { notify(e.message, 'error'); }
  };

  if (!d) return null;
  const perCategoria = {};
  d.righe.forEach(r => { (perCategoria[r.categoria_lettera] = perCategoria[r.categoria_lettera] || []).push(r); });

  return (
    <div data-testid="stima-costi" style={{ borderTop: '2px solid #EEF1F5', marginTop: 8, paddingTop: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
        <div>
          <div style={{ fontWeight: 700, color: '#1A3A5C' }}>💶 Stima analitica dei costi della sicurezza</div>
          <div style={{ fontSize: '0.75rem', color: '#8A9BB0' }}>
            Prezzi dagli elenchi in quest'ordine: progetto → account → sistema → prezzo da definire.
            Quantità e prezzi sono modificabili.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={aggiorna} disabled={d.in_abbinamento}>↻ Aggiorna prezzi</button>
          <a className="btn btn-gold btn-sm" href={exportUrl(progettoId, 'costi')} download>⬇ Costi Excel</a>
        </div>
      </div>

      {d.in_abbinamento && <div className="info-box" style={{ fontSize: '0.8rem', marginBottom: 10 }}>⏳ Ricerca delle voci di prezzo in corso…</div>}
      {d.messaggio && !d.in_abbinamento && <div className="warn-box" style={{ fontSize: '0.8rem', marginBottom: 10 }}>⚠️ {d.messaggio}</div>}
      {d.elenchi.length === 0 && (
        <div className="warn-box" style={{ fontSize: '0.8rem', marginBottom: 10 }}>
          Nessun elenco prezzi disponibile: caricane uno tra i documenti del progetto oppure nella pagina "Elenchi prezzi".
        </div>
      )}
      {d.righe.length === 0 ? (
        <div style={{ fontSize: '0.82rem', color: '#8A9BB0' }}>Nessuna misura: la stima si compila dalla tabella delle misure della tappa 11.</div>
      ) : (
        <div className="table-wrapper" style={{ overflowX: 'auto' }}>
          <table style={{ fontSize: '0.78rem' }}>
            <thead>
              <tr><th>Misura</th><th>Voce di prezzo</th><th>U.M.</th><th>Quantità</th><th>Prezzo unit.</th><th>Importo</th><th></th></tr>
            </thead>
            <tbody>
              {d.totali.categorie.map(cat => (
                [<tr key={`c-${cat.lettera}`}><td colSpan={7} style={{ background: '#EEF4FA', fontWeight: 700, color: '#1A3A5C' }}>
                  {cat.lettera !== 'altro' ? `${cat.lettera}) ` : ''}{cat.descrizione}
                </td></tr>,
                ...(perCategoria[cat.lettera] || []).map(r => (
                  <tr key={r.id} data-testid={`costo-${r.id}`}>
                    <td style={{ maxWidth: 220 }}>{r.misura}</td>
                    <td style={{ maxWidth: 320 }}>
                      {r.prezzo !== null && r.descrizione_voce ? (
                        <>
                          {r.codice && <strong>{r.codice} </strong>}
                          <span title={r.descrizione_voce}>{r.descrizione_voce.length > 110 ? r.descrizione_voce.slice(0, 110) + '…' : r.descrizione_voce}</span>
                          <div style={{ fontSize: '0.68rem', color: '#8A9BB0' }}>
                            {LIVELLO[r.livello] || ''}{r.elenco_nome ? ` · ${r.elenco_nome}` : ''}{r.stato === 'manuale' ? ' · scelta tua' : ''}
                          </div>
                        </>
                      ) : r.stato === 'da_abbinare' ? (
                        <span style={{ color: '#8A9BB0' }}>Ricerca in corso…</span>
                      ) : (
                        <span style={{ color: '#C0392B', fontWeight: 600 }}>Prezzo da definire</span>
                      )}
                      {r.um_diverse && <div style={{ fontSize: '0.7rem', color: '#8A6D00' }}>⚠️ U.M. diverse: misura in {r.um_misura}, voce in {r.um_voce}</div>}
                      {r.nota && r.stato !== 'manuale' && <div style={{ fontSize: '0.7rem', color: '#5A6B7D' }}>{r.nota}</div>}
                    </td>
                    <td>{r.um_voce || r.um_misura}</td>
                    <td><CampoCella valore={r.quantita} testid={`q-${r.id}`} onSalva={v => modifica(r, { quantita: v })} /></td>
                    <td><CampoCella valore={r.prezzo} testid={`p-${r.id}`} placeholder="€" onSalva={v => modifica(r, { prezzo: v })} /></td>
                    <td style={{ textAlign: 'right', fontWeight: 600, whiteSpace: 'nowrap' }}>{euro(r.importo)}</td>
                    <td><button className="btn btn-ghost btn-sm" onClick={() => cerca(r, r.misura)}>🔍 Voce</button></td>
                  </tr>
                )),
                <tr key={`s-${cat.lettera}`}>
                  <td colSpan={5} style={{ textAlign: 'right', fontSize: '0.76rem', color: '#5A6B7D' }}>
                    Subtotale {cat.lettera !== 'altro' ? `${cat.lettera})` : ''}{cat.da_definire ? ` · ${cat.da_definire} da definire` : ''}
                  </td>
                  <td style={{ textAlign: 'right', fontWeight: 700 }}>{euro(cat.importo)}</td><td />
                </tr>]
              ))}
              <tr>
                <td colSpan={5} style={{ textAlign: 'right', fontWeight: 700, background: '#E8F5E9' }}>TOTALE COSTI DELLA SICUREZZA</td>
                <td style={{ textAlign: 'right', fontWeight: 700, background: '#E8F5E9', whiteSpace: 'nowrap' }} data-testid="totale-costi">{euro(d.totali.totale)}</td>
                <td style={{ background: '#E8F5E9' }} />
              </tr>
            </tbody>
          </table>
          {d.totali.da_definire > 0 && (
            <div style={{ fontSize: '0.76rem', color: '#C0392B', marginTop: 6 }}>
              {d.totali.da_definire} misure con prezzo da definire non sono conteggiate nel totale.
            </div>
          )}
        </div>
      )}

      {/* Scelta manuale della voce */}
      {ricerca && (
        <div className="card" style={{ marginTop: 14, border: '1.5px solid #C88B2A' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <strong style={{ color: '#1A3A5C' }}>Scegli la voce per: {ricerca.riga.misura}</strong>
            <button className="btn btn-ghost btn-sm" onClick={() => setRicerca(null)}>✕ Chiudi</button>
          </div>
          <input className="form-control" defaultValue={ricerca.q} placeholder="Cerca per parole della descrizione…"
            onKeyDown={e => e.key === 'Enter' && cerca(ricerca.riga, e.target.value)} />
          <div className="table-wrapper" style={{ maxHeight: 320, overflow: 'auto', marginTop: 8 }}>
            <table style={{ fontSize: '0.76rem' }}>
              <thead><tr><th>Elenco</th><th>Codice</th><th>Descrizione</th><th>U.M.</th><th>Prezzo</th><th></th></tr></thead>
              <tbody>
                {ricerca.voci.length === 0 && <tr><td colSpan={6} style={{ color: '#8A9BB0' }}>Nessuna voce trovata: prova altre parole.</td></tr>}
                {ricerca.voci.map(v => (
                  <tr key={v.voce_id}>
                    <td>{LIVELLO[v.livello]}</td><td style={{ whiteSpace: 'nowrap' }}>{v.codice}</td>
                    <td>{v.descrizione}</td><td>{v.um}</td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>{euro(v.prezzo)}</td>
                    <td><button className="btn btn-gold btn-sm" onClick={() => { modifica(ricerca.riga, { voce_id: v.voce_id }); setRicerca(null); }}>Usa</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
