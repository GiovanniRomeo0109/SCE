import { useState, useEffect, useCallback, useRef } from 'react';
import { getQuestionario, rispondiDomanda, applicaRisposte } from '../../utils/api';
import { useNotify } from '../../App';

const esc = (t) => String(t || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

export default function Questionario({ progettoId, onApplicate }) {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [dati, setDati] = useState(null);
  const [bozze, setBozze] = useState({});       // id → testo in scrittura
  const [attesa, setAttesa] = useState(false);

  const carica = useCallback(async () => {
    try { const r = await getQuestionario(progettoId); setDati(r.data); }
    catch (e) { notifyRef.current(e.message, 'error'); }
  }, [progettoId]);
  useEffect(() => { carica(); }, [carica]);

  const salva = async (d) => {
    const testo = bozze[d.id];
    if (testo === undefined || testo === d.risposta) return;
    try {
      await rispondiDomanda(progettoId, d.id, testo);
      setBozze(b => { const n = { ...b }; delete n[d.id]; return n; });
      carica();
    } catch (e) { notify(e.message, 'error'); }
  };

  const applica = async () => {
    if (!window.confirm(`Applicare ${dati.da_applicare} risposte? Le tappe interessate e le successive verranno rigenerate ` +
      '(quelle modificate a mano saranno solo segnate "da ricontrollare").')) return;
    setAttesa(true);
    try {
      const r = await applicaRisposte(progettoId);
      notify(r.data.rigenerate.length ? `Rigenerazione avviata per le tappe ${r.data.rigenerate.join(', ')}`
        : 'Risposte registrate: verranno usate nelle prossime generazioni', 'success');
      carica();
      if (onApplicate) onApplicate();
    } catch (e) { notify(e.message, 'error'); }
    finally { setAttesa(false); }
  };

  const stampa = () => {
    const html = `<!DOCTYPE html><html lang="it"><head><meta charset="UTF-8">
<title>Questionario sopralluogo — ${esc(dati.progetto)}</title>
<style>
 body{font-family:Arial,sans-serif;font-size:11px;color:#1A2E42;margin:20px}
 h1{font-size:17px;color:#1A3A5C;margin:0 0 4px} h2{font-size:12.5px;color:#1A3A5C;margin:16px 0 6px;border-bottom:1px solid #ccd;padding-bottom:3px}
 .q{margin:0 0 10px;page-break-inside:avoid} .t{font-weight:bold} .tag{font-size:9px;color:#8A6D00}
 .r{border:1px solid #bbb;min-height:34px;margin-top:4px;padding:4px;white-space:pre-wrap}
 .meta{color:#5A6B7D;font-size:10px;margin-bottom:12px}
</style></head><body>
<h1>Questionario per il sopralluogo</h1>
<div class="meta">Progetto: ${esc(dati.progetto)} · Stampato il ${new Date().toLocaleDateString('it-IT')} · SafetyDocs — D.Lgs. 81/2008</div>
${dati.gruppi.map(g => `<h2>Tappa ${g.tappa} — ${esc(g.titolo)}</h2>
${g.domande.map((d, i) => `<div class="q"><div class="t">${i + 1}. ${esc(d.testo)}
 ${d.origine === 'da_verificare' ? '<span class="tag">[DA VERIFICARE]</span>' : ''}</div>
 <div class="r">${esc(d.risposta)}</div></div>`).join('')}`).join('')}
<p style="margin-top:24px">Data del sopralluogo: ____________ &nbsp;&nbsp; Firma del CSP: ______________________</p>
</body></html>`;
    const w = window.open('', '_blank');
    if (!w) { notify('Il browser ha bloccato la finestra di stampa: consenti i popup per questo sito', 'error'); return; }
    w.document.write(html);
    w.document.close();
    setTimeout(() => w.print(), 400);
  };

  if (!dati) return <div style={{ padding: 30, color: '#8A9BB0' }}>Caricamento questionario…</div>;

  if (!dati.gruppi.length) {
    return (
      <div className="card"><div className="empty-state">
        <div className="empty-icon">📝</div>
        <p>Il questionario si compila da solo quando generi le tappe: raccoglie le domande per il sopralluogo e i dati DA VERIFICARE.</p>
      </div></div>
    );
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ flex: 1, fontSize: '0.85rem' }}>
          <strong>{dati.aperte}</strong> domande aperte · <strong>{dati.da_applicare}</strong> risposte da applicare.
          <div style={{ fontSize: '0.75rem', color: '#8A9BB0' }}>
            Stampa il questionario per il sopralluogo, poi riporta qui le risposte e premi "Applica risposte".
          </div>
        </div>
        <button className="btn btn-ghost" onClick={stampa}>🖨️ Stampa / Salva PDF</button>
        <button className="btn btn-gold" onClick={applica} disabled={!dati.da_applicare || attesa}>
          {attesa ? 'Applicazione…' : '↻ Applica risposte alle tappe'}
        </button>
      </div>

      {dati.gruppi.map(g => (
        <div key={g.tappa} className="card" style={{ marginBottom: 14 }}>
          <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 10 }}>Tappa {g.tappa} — {g.titolo}</div>
          {g.domande.map(d => {
            const valore = bozze[d.id] !== undefined ? bozze[d.id] : d.risposta;
            return (
              <div key={d.id} style={{ marginBottom: 12 }}>
                <div style={{ fontSize: '0.84rem', marginBottom: 4 }}>
                  {d.origine === 'da_verificare' && <span className="badge badge-notifica" style={{ marginRight: 6 }}>DA VERIFICARE</span>}
                  {d.testo}
                  {d.stato === 'applicata' && <span style={{ fontSize: '0.72rem', color: '#27AE60' }}> · applicata</span>}
                  {d.stato === 'risposta' && <span style={{ fontSize: '0.72rem', color: '#C88B2A' }}> · da applicare</span>}
                </div>
                <textarea className="form-control" rows={2} value={valore} placeholder="Risposta dopo il sopralluogo…"
                  onChange={e => setBozze(b => ({ ...b, [d.id]: e.target.value }))}
                  onBlur={() => salva(d)} style={{ width: '100%', boxSizing: 'border-box' }} />
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
