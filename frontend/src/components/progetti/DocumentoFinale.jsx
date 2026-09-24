import { useState, useEffect, useCallback, useRef } from 'react';
import {
  getChecklist, salvaVoceChecklist, getExportInfo, esportaPsc, chiudiProgetto, pubblicaEsempio, downloadUrl,
} from '../../utils/api';
import { useNotify } from '../../App';

const ESITI = [['si', 'Sì'], ['no', 'No'], ['np', 'Non pertinente']];

function Voce({ v, disabilitata, onSalva }) {
  const [motiv, setMotiv] = useState(v.motivazione || '');
  useEffect(() => { setMotiv(v.motivazione || ''); }, [v.motivazione]);
  return (
    <div data-testid={`voce-${v.voce}`} style={{ padding: '6px 0', borderBottom: '1px solid #F1F3F6' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <span style={{ width: 34, fontSize: '0.72rem', color: '#8A9BB0' }}>{v.voce}</span>
        <span style={{ flex: 1, minWidth: 220, fontSize: '0.84rem' }}>{v.testo}</span>
        {ESITI.map(([k, label]) => (
          <label key={k} style={{ fontSize: '0.78rem', display: 'flex', gap: 4, alignItems: 'center', cursor: 'pointer',
            color: v.esito === k ? (k === 'no' ? '#C0392B' : '#1A3A5C') : '#5A6B7D', fontWeight: v.esito === k ? 700 : 400 }}>
            <input type="radio" name={`esito-${v.voce}`} checked={v.esito === k} disabled={disabilitata}
              onChange={() => onSalva(v.voce, { esito: k, motivazione: k === 'np' ? motiv : null })} />
            {label}
          </label>
        ))}
        <span style={{ width: 18 }}>{v.ok ? '✅' : ''}</span>
      </div>
      {v.esito === 'np' && (
        <input className="form-control" placeholder="Motivazione (obbligatoria)" value={motiv} disabled={disabilitata}
          style={{ marginLeft: 44, marginTop: 4, width: 'calc(100% - 44px)', fontSize: '0.8rem',
            borderColor: v.motivazione ? undefined : '#C0392B' }}
          onChange={e => setMotiv(e.target.value)}
          onBlur={() => { if (motiv !== (v.motivazione || '')) onSalva(v.voce, { esito: 'np', motivazione: motiv }); }} />
      )}
      {v.esito === 'no' && <div style={{ marginLeft: 44, fontSize: '0.72rem', color: '#C0392B' }}>
        Risolvi questo punto nelle tappe: con "No" l'export resta bloccato.</div>}
    </div>
  );
}

export default function DocumentoFinale({ progettoId, onChiuso }) {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [ck, setCk] = useState(null);
  const [info, setInfo] = useState(null);
  const [form, setForm] = useState({ revisione: 0, data: '', coordinatore_id: '' });
  const [inCorso, setInCorso] = useState(false);

  const carica = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([getChecklist(progettoId), getExportInfo(progettoId)]);
      setCk(a.data); setInfo(b.data);
      setForm(f => ({ revisione: f.data ? f.revisione : b.data.revisione_proposta,
        data: f.data || b.data.data_proposta, coordinatore_id: f.coordinatore_id || b.data.coordinatore_id || '' }));
    } catch (e) { notifyRef.current(e.message, 'error'); }
  }, [progettoId]);
  useEffect(() => { carica(); }, [carica]);

  const salvaVoce = async (voce, dati) => {
    try {
      const r = await salvaVoceChecklist(progettoId, voce, dati);
      setCk(r.data);
      setInfo(x => ({ ...x, checklist: { ...x.checklist, completa: r.data.completa, compilate: r.data.compilate, mancanti: r.data.mancanti } }));
    } catch (e) { notify(e.message, 'error'); }
  };

  const esporta = async () => {
    const giaPresente = info.revisioni.some(r => r.revisione === Number(form.revisione));
    if (giaPresente && !window.confirm(`La Rev. ${form.revisione} è già nello Storico: il file verrà sostituito con quello nuovo. Continuare?`)) return;
    setInCorso(true);
    try {
      const r = await esportaPsc(progettoId, { revisione: Number(form.revisione), data: form.data,
        coordinatore_id: form.coordinatore_id ? Number(form.coordinatore_id) : null });
      const a = document.createElement('a');
      a.href = downloadUrl(r.data.doc_id); a.download = ''; document.body.appendChild(a); a.click(); a.remove();
      notify(`PSC Rev. ${r.data.revisione} generato (${r.data.storico === 'nuova' ? 'aggiunto' : 'aggiornato'} nello Storico)` +
        (r.data.punti_da_verificare ? ` — ${r.data.punti_da_verificare} punti DA VERIFICARE` : ''), 'success');
      carica();
    } catch (e) { notify(e.message, 'error'); }
    finally { setInCorso(false); }
  };

  const chiudi = async () => {
    if (!window.confirm('Chiudere il progetto?\n\n• I file originali caricati verranno ELIMINATI definitivamente.\n' +
      '• Il progetto diventerà in sola lettura (non potrai più modificare tappe, costi, schemi e checklist).\n' +
      '• Potrai ancora consultarlo e scaricare il PSC.\n\nL\'operazione non si può annullare.')) return;
    try { await chiudiProgetto(progettoId); notify('Progetto chiuso', 'success'); carica(); if (onChiuso) onChiuso(); }
    catch (e) { notify(e.message, 'error'); }
  };

  const pubblica = async () => {
    if (!window.confirm('Pubblicare questo progetto come progetto di esempio?\nOgni account che non l\'ha ancora ricevuto ne avrà una copia personale.')) return;
    try { await pubblicaEsempio(progettoId); notify('Progetto di esempio pubblicato ✓', 'success'); carica(); }
    catch (e) { notify(e.message, 'error'); }
  };

  if (!ck || !info) return <div style={{ padding: 30, color: '#8A9BB0' }}>Caricamento…</div>;
  const chiuso = info.stato === 'chiuso';
  const perc = Math.round((ck.compilate / ck.totale) * 100);
  const coord = info.coordinatori.find(c => String(c.id) === String(form.coordinatore_id));

  return (
    <div data-testid="documento-finale">
      {/* Export */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 10 }}>📄 Documento finale del PSC</div>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={{ fontSize: '0.8rem' }}>Revisione<br />
            <input className="form-control" type="number" min="0" style={{ width: 90 }} data-testid="revisione"
              value={form.revisione} onChange={e => setForm(f => ({ ...f, revisione: e.target.value }))} /></label>
          <label style={{ fontSize: '0.8rem' }}>Data (gg/mm/aaaa)<br />
            <input className="form-control" style={{ width: 130 }} data-testid="data-revisione"
              value={form.data} onChange={e => setForm(f => ({ ...f, data: e.target.value }))} /></label>
          <label style={{ fontSize: '0.8rem' }}>Coordinatore che firma<br />
            <select className="form-control" style={{ minWidth: 220 }} data-testid="coordinatore" value={form.coordinatore_id}
              onChange={e => setForm(f => ({ ...f, coordinatore_id: e.target.value }))}>
              <option value="">— nessuno —</option>
              {info.coordinatori.map(c => <option key={c.id} value={c.id}>{c.nome}{c.predefinito ? ' (predefinito)' : ''}</option>)}
            </select></label>
          <button className="btn btn-gold" onClick={esporta} disabled={!info.checklist.completa || inCorso} data-testid="scarica-psc"
            title={info.checklist.completa ? '' : 'Completa prima la checklist A–M'}>
            {inCorso ? 'Generazione…' : '⬇ Scarica il PSC (DOCX)'}
          </button>
        </div>
        <div style={{ fontSize: '0.76rem', color: '#5A6B7D', marginTop: 10, lineHeight: 1.6 }}>
          {!info.checklist.completa && <div style={{ color: '#C0392B' }}>⛔ Export bloccato: completa la checklist A–M ({ck.compilate}/{ck.totale}).</div>}
          {!info.studio.completo && <div>⚠️ Dati dello studio non compilati: la copertina sarà senza intestazione (Anagrafica → Coordinatori).</div>}
          {info.coordinatori.length === 0 && <div>⚠️ Nessun coordinatore in anagrafica: il nome del CSP risulterà DA VERIFICARE.</div>}
          {coord && !coord.ha_firma && <div>ℹ️ {coord.nome} non ha una firma caricata: nel documento ci sarà lo spazio per firmare a mano.</div>}
          {info.tappe_mancanti.length > 0 && <div>⚠️ Tappe non ancora generate: {info.tappe_mancanti.join(', ')} (i capitoli corrispondenti risulteranno DA VERIFICARE).</div>}
          <div>I dati DA VERIFICARE ancora presenti vengono evidenziati in giallo e riepilogati all'inizio del documento.</div>
        </div>
        {info.revisioni.length > 0 && (
          <div style={{ marginTop: 12, fontSize: '0.8rem' }} data-testid="revisioni">
            <strong>Revisioni nello Storico:</strong>{' '}
            {info.revisioni.map(r => (
              <a key={r.id} href={downloadUrl(r.id)} style={{ marginRight: 10 }}>Rev. {r.revisione}</a>
            ))}
          </div>
        )}
      </div>

      {/* Checklist */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <div style={{ fontWeight: 700, color: '#1A3A5C' }}>✅ Checklist A–M (verifica obbligatoria prima dell'export)</div>
          <span style={{ fontSize: '0.8rem', color: ck.completa ? '#27AE60' : '#8A6D00' }} data-testid="stato-checklist">
            {ck.compilate}/{ck.totale} {ck.completa ? '— completa' : ''}</span>
        </div>
        <div style={{ height: 6, background: '#EEF1F5', borderRadius: 3, overflow: 'hidden', marginBottom: 10 }}>
          <div style={{ width: `${perc}%`, height: '100%', background: ck.completa ? '#27AE60' : '#C88B2A' }} />
        </div>
        <div style={{ fontSize: '0.75rem', color: '#8A9BB0', marginBottom: 10 }}>
          Ogni voce deve essere "Sì" oppure "Non pertinente" con una motivazione. La checklist resta nell'app e non entra nel documento.
        </div>
        {ck.sezioni.map(sz => (
          <div key={sz.lettera} style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 700, fontSize: '0.86rem', color: '#1A3A5C', background: '#EEF4FA', padding: '4px 8px', borderRadius: 4 }}>
              {sz.lettera} — {sz.titolo} <span style={{ fontWeight: 400, color: '#8A9BB0' }}>
                ({sz.voci.filter(v => v.ok).length}/{sz.voci.length})</span>
            </div>
            {sz.voci.map(v => <Voce key={v.voce} v={v} disabilitata={chiuso} onSalva={salvaVoce} />)}
          </div>
        ))}
      </div>

      {/* Chiusura e pubblicazione */}
      <div className="card">
        <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          {chiuso ? (
            <span style={{ fontSize: '0.84rem', color: '#5A6B7D' }}>🔒 Progetto chiuso: in sola lettura, file originali eliminati.</span>
          ) : (
            <>
              <button className="btn btn-danger" onClick={chiudi} data-testid="chiudi-progetto">🔒 Chiudi il progetto</button>
              <span style={{ fontSize: '0.76rem', color: '#8A9BB0' }}>Elimina i file originali e rende il progetto in sola lettura. Il PSC resta scaricabile.</span>
            </>
          )}
          {info.is_admin && !info.is_esempio && (
            <button className="btn btn-ghost" style={{ marginLeft: 'auto' }} onClick={pubblica} data-testid="pubblica-esempio">
              {info.esempio_pubblicato ? '✔ Pubblicato come esempio (ripubblica)' : '🌐 Pubblica come progetto di esempio'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
