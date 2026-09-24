import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getPresidi, salvaIndirizzo, cercaPresidi, aggiungiPresidio, modificaPresidio, eliminaPresidio, getSchemi,
} from '../../utils/api';
import { useNotify } from '../../App';

const CAMPI = [['nome', 'Nome', 200], ['indirizzo', 'Indirizzo', 200], ['telefono', 'Telefono', 110],
  ['distanza', 'Distanza', 100], ['percorso', 'Percorso', 140]];

/** Campo che salva all'uscita solo se il valore è cambiato. */
function Campo({ valore, onSalva, larghezza, placeholder }) {
  const [t, setT] = useState(valore || '');
  useEffect(() => { setT(valore || ''); }, [valore]);
  return (
    <input className="form-control" value={t} placeholder={placeholder}
      style={{ width: larghezza, padding: '4px 6px', fontSize: '0.78rem' }}
      onChange={e => setT(e.target.value)}
      onBlur={() => { if (t !== (valore || '')) onSalva(t); }}
      onKeyDown={e => e.key === 'Enter' && e.target.blur()} />
  );
}

export default function PresidiEmergenza({ progettoId, onAggiorna, onApriSchema, manuale }) {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [d, setD] = useState(null);
  const [indirizzo, setIndirizzo] = useState('');
  const [cercando, setCercando] = useState(false);
  const [nSchemi, setNSchemi] = useState(null);
  const [nuovo, setNuovo] = useState(null);

  const carica = useCallback(async () => {
    try {
      const r = await getPresidi(progettoId);
      setD(r.data);
      setIndirizzo(r.data.indirizzo_cantiere || r.data.indirizzo_proposto || '');
      const s = await getSchemi(progettoId);
      setNSchemi(s.data.schemi.length);
    } catch (e) { notifyRef.current(e.message, 'error'); }
  }, [progettoId]);
  useEffect(() => { carica(); }, [carica]);

  const dopo = (r) => { setD(x => ({ ...x, presidi: r.data.presidi })); onAggiorna(); };

  const salvaInd = async () => {
    if (indirizzo === (d.indirizzo_cantiere || '')) return;
    try { await salvaIndirizzo(progettoId, indirizzo); setD(x => ({ ...x, indirizzo_cantiere: indirizzo })); }
    catch (e) { notify(e.message, 'error'); }
  };

  const cerca = async () => {
    if (indirizzo.trim().length < 5) { notify('Indica l\'indirizzo del cantiere', 'error'); return; }
    const giaTrovati = d.presidi.filter(p => !p.confermato && !p.manuale).length;
    if (!window.confirm(`Cercare sul web i presidi di emergenza vicini a:\n${indirizzo}\n\n` +
      (giaTrovati ? `I ${giaTrovati} presidi non ancora confermati verranno sostituiti; quelli confermati o inseriti da te restano.\n` : '') +
      'Costo stimato: circa € 0,15. La ricerca richiede fino a un minuto.')) return;
    setCercando(true);
    try {
      await salvaIndirizzo(progettoId, indirizzo);
      const r = await cercaPresidi(progettoId);
      notify(`Trovati ${r.data.trovati} presidi: verificali e premi "Confermato"`, 'success');
      dopo(r);
    } catch (e) { notify(e.message, 'error'); }
    finally { setCercando(false); }
  };

  const modifica = async (p, dati) => {
    try { dopo(await modificaPresidio(progettoId, p.id, dati)); } catch (e) { notify(e.message, 'error'); }
  };
  const elimina = async (p) => {
    if (!window.confirm(`Eliminare "${p.nome || p.tipo_etichetta}"?`)) return;
    try { dopo(await eliminaPresidio(progettoId, p.id)); } catch (e) { notify(e.message, 'error'); }
  };
  const aggiungi = async () => {
    if (!nuovo.nome && !nuovo.telefono) { notify('Indica almeno il nome o il telefono', 'error'); return; }
    try { dopo(await aggiungiPresidio(progettoId, nuovo)); setNuovo(null); } catch (e) { notify(e.message, 'error'); }
  };

  if (!d) return null;

  return (
    <div data-testid="presidi" style={{ borderTop: '2px solid #EEF1F5', marginTop: 8, paddingTop: 16 }}>
      {/* Collegamento con lo schema di cantiere */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, flexWrap: 'wrap',
        background: nSchemi === 0 ? '#FFF8E1' : '#F8F5F0', borderRadius: 8, padding: '10px 14px', marginBottom: 16 }}>
        <div style={{ fontSize: '0.82rem' }}>
          🗺️ <strong>Schema di cantiere</strong> —{' '}
          {nSchemi === 0 ? 'non hai ancora disegnato uno schema: posiziona sulla planimetria gli elementi descritti qui sopra.'
            : `${nSchemi} ${nSchemi === 1 ? 'schema disegnato' : 'schemi disegnati'}.`}
        </div>
        <button className="btn btn-gold btn-sm" onClick={onApriSchema}>Apri lo schema di cantiere →</button>
      </div>

      <div style={{ fontWeight: 700, color: '#1A3A5C' }}>🚑 Presidi di emergenza</div>
      <div style={{ fontSize: '0.75rem', color: '#8A9BB0', marginBottom: 10 }}>
        {manuale ? 'Progetto manuale: inserisci a mano i presidi di emergenza; compilano la tabella qui sopra.'
          : 'Ricerca sul web a partire dall\'indirizzo del cantiere. Distanze e percorsi sono indicativi (nessun servizio di mappe): ogni presidio resta "da verificare" finché non premi "Confermato". I presidi compilano la tabella qui sopra.'}
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 12 }}>
        <label htmlFor="indirizzo-cantiere" style={{ fontSize: '0.82rem', fontWeight: 600 }}>Indirizzo del cantiere</label>
        <input id="indirizzo-cantiere" className="form-control" style={{ flex: 1, minWidth: 260 }} value={indirizzo}
          placeholder="Via, numero civico, comune (provincia)" onChange={e => setIndirizzo(e.target.value)} onBlur={salvaInd} />
        {!manuale && (
          <button className="btn btn-gold btn-sm" onClick={cerca} disabled={cercando}>
            {cercando ? '⏳ Ricerca in corso…' : '🔎 Cerca presidi di emergenza'}
          </button>
        )}
      </div>
      {!d.indirizzo_cantiere && d.indirizzo_proposto && (
        <div style={{ fontSize: '0.72rem', color: '#5A6B7D', marginTop: -6, marginBottom: 10 }}>Indirizzo proposto dai documenti del progetto: controllalo.</div>
      )}

      {d.presidi.length > 0 && (
        <div className="table-wrapper" style={{ overflowX: 'auto' }}>
          <table style={{ fontSize: '0.76rem' }}>
            <thead><tr><th>Tipo</th>{CAMPI.map(([k, t]) => <th key={k}>{t}</th>)}<th>Fonte</th><th>Stato</th><th></th></tr></thead>
            <tbody>
              {d.presidi.map(p => (
                <tr key={p.id} data-testid={`presidio-${p.id}`} style={{ background: p.confermato ? undefined : '#FFFBF0' }}>
                  <td style={{ whiteSpace: 'nowrap' }}>{p.tipo_etichetta}</td>
                  {CAMPI.map(([k, , w]) => (
                    <td key={k}><Campo valore={p[k]} larghezza={w} onSalva={v => modifica(p, { [k]: v })} /></td>
                  ))}
                  <td style={{ maxWidth: 140 }}>
                    {p.fonte_url ? <a href={p.fonte_url} target="_blank" rel="noopener noreferrer" title={p.fonte_url}>
                      {(p.fonte_titolo || p.fonte_url).slice(0, 40)}</a> : (p.manuale ? 'Inserito da te' : '—')}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    {p.confermato ? (
                      <button className="btn btn-ghost btn-sm" style={{ color: '#27AE60' }} title="Clicca per annullare la conferma"
                        onClick={() => modifica(p, { confermato: false })}>✔ Confermato</button>
                    ) : (
                      <button className="btn btn-gold btn-sm" onClick={() => modifica(p, { confermato: true })}>Confermato</button>
                    )}
                    {!p.confermato && <div style={{ fontSize: '0.66rem', color: '#8A6D00' }}>da verificare</div>}
                  </td>
                  <td><button className="btn btn-ghost btn-sm" onClick={() => elimina(p)}>✕</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {nuovo ? (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginTop: 10 }}>
          <select className="form-control" style={{ width: 160 }} value={nuovo.tipo}
            onChange={e => setNuovo(n => ({ ...n, tipo: e.target.value }))}>
            {Object.entries(d.tipi).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          {CAMPI.map(([k, t, w]) => (
            <input key={k} className="form-control" placeholder={t} style={{ width: w }} value={nuovo[k] || ''}
              onChange={e => setNuovo(n => ({ ...n, [k]: e.target.value }))} />
          ))}
          <button className="btn btn-gold btn-sm" onClick={aggiungi}>Aggiungi</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setNuovo(null)}>Annulla</button>
        </div>
      ) : (
        <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }} onClick={() => setNuovo({ tipo: 'pronto_soccorso' })}>
          ＋ Aggiungi un presidio a mano
        </button>
      )}
    </div>
  );
}
