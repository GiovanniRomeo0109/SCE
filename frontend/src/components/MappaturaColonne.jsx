import { useState } from 'react';

/**
 * Schermata di associazione colonne per un elenco prezzi (ODS/XLS/XLSX)
 * le cui intestazioni non sono state riconosciute.
 *
 * props:
 *  - anteprima: { righe: string[][], n_colonne: number }
 *  - onConferma(mappatura)  → { riga_intestazione, codice, descrizione, um, prezzo, perc_manodopera }
 *  - onAnnulla()
 */
const CAMPI = [
  { k: 'codice',          label: 'Codice',       obbl: true },
  { k: 'descrizione',     label: 'Descrizione',  obbl: true },
  { k: 'um',              label: 'Unità di misura', obbl: true },
  { k: 'prezzo',          label: 'Prezzo',       obbl: true },
  { k: 'perc_manodopera', label: '% Manodopera', obbl: false },
];

const lettera = (i) => String.fromCharCode(65 + (i % 26)) + (i >= 26 ? Math.floor(i / 26) : '');

export default function MappaturaColonne({ anteprima, onConferma, onAnnulla, inCorso }) {
  const righe = anteprima?.righe || [];
  const nCol = Math.max(anteprima?.n_colonne || 0, ...righe.map(r => r.length));
  const [rigaInt, setRigaInt] = useState(0);
  const [m, setM] = useState({ codice: '', descrizione: '', um: '', prezzo: '', perc_manodopera: '' });

  const completa = CAMPI.filter(c => c.obbl).every(c => m[c.k] !== '');

  const conferma = () => {
    const out = { riga_intestazione: Number(rigaInt) };
    CAMPI.forEach(c => { out[c.k] = m[c.k] === '' ? null : Number(m[c.k]); });
    onConferma(out);
  };

  const coloreColonna = (j) => {
    const c = CAMPI.find(c => m[c.k] !== '' && Number(m[c.k]) === j);
    return c ? '#FFF4D6' : 'transparent';
  };

  return (
    <div className="card" style={{ border: '1.5px solid #C88B2A' }}>
      <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 6 }}>
        🧩 Indica le colonne dell'elenco prezzi
      </div>
      <p style={{ fontSize: '0.82rem', color: '#5A6B7D', marginTop: 0 }}>
        Non ho riconosciuto automaticamente le intestazioni. Scegli la riga di intestazione e
        indica quale colonna contiene ciascun dato. Le righe senza prezzo verranno usate come titoli di capitolo.
      </p>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 14 }}>
        <label style={{ fontSize: '0.8rem' }}>
          Riga di intestazione<br />
          <select className="form-control" value={rigaInt} onChange={e => setRigaInt(e.target.value)}>
            {righe.map((_, i) => <option key={i} value={i}>Riga {i + 1}</option>)}
          </select>
        </label>
        {CAMPI.map(c => (
          <label key={c.k} style={{ fontSize: '0.8rem' }}>
            {c.label}{c.obbl ? ' *' : ''}<br />
            <select className="form-control" value={m[c.k]}
              onChange={e => setM(prev => ({ ...prev, [c.k]: e.target.value }))}>
              <option value="">{c.obbl ? '— scegli —' : '— nessuna —'}</option>
              {Array.from({ length: nCol }).map((_, j) => (
                <option key={j} value={j}>
                  Colonna {lettera(j)}{righe[rigaInt]?.[j] ? ` · ${righe[rigaInt][j].slice(0, 25)}` : ''}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>

      <div className="table-wrapper" style={{ maxHeight: 280, overflow: 'auto', marginBottom: 14 }}>
        <table style={{ fontSize: '0.75rem' }}>
          <thead>
            <tr><th>#</th>{Array.from({ length: nCol }).map((_, j) => <th key={j}>{lettera(j)}</th>)}</tr>
          </thead>
          <tbody>
            {righe.map((r, i) => (
              <tr key={i} style={{ fontWeight: i === Number(rigaInt) ? 700 : 400 }}>
                <td>{i + 1}</td>
                {Array.from({ length: nCol }).map((_, j) => (
                  <td key={j} style={{ background: coloreColonna(j) }}>{r[j] || ''}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
        {onAnnulla && <button className="btn btn-ghost" onClick={onAnnulla}>Annulla</button>}
        <button className="btn btn-gold" disabled={!completa || inCorso} onClick={conferma}>
          {inCorso ? 'Lettura in corso…' : 'Conferma e leggi le voci'}
        </button>
      </div>
    </div>
  );
}
