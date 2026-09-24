import { useState, useEffect, useRef, useCallback } from 'react';
import {
  getSchema, salvaSchema, caricaSfondo, sfondoDaDocumento, togliSfondo, sfondoUrl, dxfUrl, getTappe,
} from '../../utils/api';
import { useNotify } from '../../App';

const AVVISO = 'Schema indicativo generato con SafetyDocs: va rifinito in CAD prima dell\'uso definitivo.';
const ICONE = {
  accesso_carrabile: '🚚', accesso_pedonale: '🚶', spogliatoio: '👕', ufficio: '🗂️', refettorio: '🍽️', wc: '🚻',
  deposito: '📦', rifiuti: '🗑️', gru: '🏗️', autogru: '🚛', betoniera: '⚙️', quadro: '⚡', estintore: '🧯',
  primo_soccorso: '➕', punto_raccolta: '🟢', carico_scarico: '⇅', parcheggio: '🅿️', lavorazione: '🔨',
  recinzione: '▭', ponteggio: '▤', percorso: '➜', testo: 'T',
};
const COLORE = { recinzione: '#C0392B', ponteggio: '#2E6DB4', percorso: '#27AE60', gru: '#8E44AD', testo: '#1A3A5C' };
const colore = (t) => COLORE[t] || '#C88B2A';
const PAROLE = {
  recinzione: ['recinz'], ponteggio: ['ponteg'], percorso: ['viabil', 'percors'], accesso_carrabile: ['carrab'],
  accesso_pedonale: ['pedonal'], spogliatoio: ['spoglia'], ufficio: ['uffic'], refettorio: ['refett', 'mensa'],
  wc: ['wc', 'bagn', 'igienic'], deposito: ['deposit', 'stoccag'], rifiuti: ['rifiut', 'cassone'], gru: ['gru a torre'],
  autogru: ['autogru'], betoniera: ['betonier', 'silo'], quadro: ['quadro', 'impianto elettric'], estintore: ['estint', 'antincend'],
  primo_soccorso: ['soccorso', 'cassetta'], punto_raccolta: ['punto di raccolta', 'luogo sicuro'], carico_scarico: ['carico', 'scarico'],
  parcheggio: ['parchegg'], lavorazione: ['lavorazione del ferro', 'piegatura', 'legname', 'area di lavorazione'],
};
let contatore = 0;
const nuovoId = () => `e${Date.now().toString(36)}${(contatore++).toString(36)}`;
const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
const fmt = (n, d = 1) => Number(n).toLocaleString('it-IT', { maximumFractionDigits: d });

export default function EditorSchema({ progettoId, schemaId, catalogo, documentiSfondo, onChiudi, solaLettura }) {
  const notify = useNotify();
  const notifyRef = useRef(notify);
  notifyRef.current = notify;
  const [s, setS] = useState(null);
  const [elementi, setElementi] = useState([]);
  const [sel, setSel] = useState(null);
  const [strumento, setStrumento] = useState('seleziona');
  const [bozza, setBozza] = useState([]);                // punti della linea o della taratura in corso
  const [cursore, setCursore] = useState(null);
  const [zoom, setZoom] = useState(null);
  const [stato, setStato] = useState('');
  const [previsti, setPrevisti] = useState({});
  const [docSfondo, setDocSfondo] = useState(documentiSfondo[0]?.id || '');
  const [pagina, setPagina] = useState(1);
  const svgRef = useRef(null);
  const areaRef = useRef(null);
  const trascina = useRef(null);
  const caricato = useRef(false);

  // ── Caricamento ────────────────────────────────────────────────────────────
  useEffect(() => {
    getSchema(progettoId, schemaId).then(r => {
      setS(r.data); setElementi(r.data.elementi || []);
      caricato.current = false;
    }).catch(e => notifyRef.current(e.message, 'error'));
    getTappe(progettoId).then(r => {
      const t9 = r.data.tappe.find(t => t.numero === 9);
      const sez = t9?.contenuto?.sezioni?.find(x => x.id === 'elementi_cantiere');
      const testo = (sez?.righe || []).map(rr => `${rr[0]} ${rr[1]}`).join(' ').toLowerCase()
        + ' ' + (t9?.contenuto?.sezioni?.find(x => x.id === 'layout')?.testo || '').toLowerCase();
      const p = {};
      Object.entries(PAROLE).forEach(([k, parole]) => { if (parole.some(w => testo.includes(w))) p[k] = true; });
      setPrevisti(p);
    }).catch(() => {});
  }, [progettoId, schemaId]);

  // Adatta lo zoom alla larghezza disponibile al primo caricamento
  useEffect(() => {
    if (s && zoom === null && areaRef.current) {
      setZoom(Math.min(1, (areaRef.current.clientWidth - 20) / s.sfondo_w));
    }
  }, [s, zoom]);

  // ── Salvataggio automatico ─────────────────────────────────────────────────
  const idCaricato = s?.id;
  useEffect(() => {
    if (!idCaricato || solaLettura) return;
    if (!caricato.current) { caricato.current = true; return; }
    setStato('Modifiche non salvate…');
    const t = setTimeout(() => {
      setStato('Salvataggio…');
      salvaSchema(progettoId, schemaId, { elementi })
        .then(() => setStato('Salvato ✓'))
        .catch(e => { setStato('Errore di salvataggio'); notifyRef.current(e.message, 'error'); });
    }, 700);
    return () => clearTimeout(t);
  }, [elementi, progettoId, schemaId, idCaricato, solaLettura]);

  const salvaSubito = (dati) => salvaSchema(progettoId, schemaId, dati)
    .then(r => { setS(x => ({ ...x, ...r.data, elementi: undefined })); return r; });

  // ── Geometria ──────────────────────────────────────────────────────────────
  const mpp = s?.scala?.m_per_px || null;                          // metri per pixel (se tarata)
  const pxPerMFallback = s ? s.sfondo_w / 60 : 20;                 // senza scala: area ipotetica di 60 m
  const m2px = (m) => (mpp ? m / mpp : m * pxPerMFallback);
  const px2m = (px) => (mpp ? px * mpp : px / pxPerMFallback);

  const puntoSvg = (e) => {
    const svg = svgRef.current;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    return [Math.round(p.x * 10) / 10, Math.round(p.y * 10) / 10];
  };

  const aggiorna = useCallback((id, f) => setElementi(els => els.map(el => (el.id === id ? f(el) : el))), []);
  const selezionato = elementi.find(e => e.id === sel);

  const aggiungiElemento = (tipo, p, extra = {}) => {
    const cat = catalogo[tipo] || {};
    const [wm, hm] = cat.dimensioni_m || [4, 3];
    const el = { id: nuovoId(), tipo, etichetta: cat.etichetta || tipo, x: p[0], y: p[1],
      w: Math.round(m2px(wm) * 10) / 10, h: Math.round(m2px(hm) * 10) / 10, rot: 0, ...extra };
    if (tipo === 'gru') el.raggio_m = 25;
    setElementi(els => [...els, el]);
    setSel(el.id);
    setStrumento('seleziona');
  };

  const terminaLinea = useCallback(() => {
    if (!strumento.startsWith('linea:')) return;
    const tipo = strumento.slice(6);
    if (bozza.length >= 2) {
      const el = { id: nuovoId(), tipo, etichetta: catalogo[tipo]?.etichetta || tipo, punti: bozza };
      setElementi(els => [...els, el]);
      setSel(el.id);
    }
    setBozza([]); setStrumento('seleziona');
  }, [strumento, bozza, catalogo]);

  // ── Mouse / touch sull'area di disegno ─────────────────────────────────────
  const giuSfondo = (e) => {
    if (solaLettura) return;
    if (e.button !== undefined && e.button !== 0) return;
    const p = puntoSvg(e);
    if (strumento === 'seleziona') { setSel(null); return; }
    if (strumento.startsWith('aggiungi:')) { aggiungiElemento(strumento.slice(9), p); return; }
    if (strumento.startsWith('linea:')) { setBozza(b => [...b, p]); return; }
    if (strumento === 'testo') {
      const testo = window.prompt('Testo dell\'etichetta:');
      if (testo) aggiungiElemento('testo', p, { testo, etichetta: testo });
      else setStrumento('seleziona');
      return;
    }
    if (strumento === 'scala') {
      const punti = [...bozza, p];
      if (punti.length < 2) { setBozza(punti); return; }
      const px = dist(punti[0], punti[1]);
      const risposta = window.prompt(`Distanza reale tra i due punti, in metri (${fmt(px, 0)} px sullo schermo):`);
      const metri = Number(String(risposta || '').replace(',', '.'));
      setBozza([]); setStrumento('seleziona');
      if (!metri || metri <= 0 || px < 5) { if (risposta !== null) notify('Distanza non valida: taratura annullata', 'error'); return; }
      const scala = { m_per_px: metri / px, punti, distanza_m: metri };
      salvaSubito({ scala }).then(() => notify(`Scala tarata: ${fmt(metri)} m = ${fmt(px, 0)} px`, 'success'))
        .catch(err => notify(err.message, 'error'));
    }
  };

  const giuElemento = (e, el, modo = 'sposta', extra = {}) => {
    if (solaLettura) return;
    if (strumento !== 'seleziona') return;
    e.stopPropagation();
    setSel(el.id);
    trascina.current = { modo, id: el.id, inizio: puntoSvg(e), orig: JSON.parse(JSON.stringify(el)), ...extra };
    svgRef.current.setPointerCapture?.(e.pointerId);
  };

  const muovi = (e) => {
    const p = puntoSvg(e);
    if (bozza.length) setCursore(p);
    const t = trascina.current;
    if (!t) return;
    const dx = p[0] - t.inizio[0], dy = p[1] - t.inizio[1];
    const o = t.orig;
    aggiorna(t.id, el => {
      if (t.modo === 'sposta') {
        if (o.punti) return { ...el, punti: o.punti.map(([x, y]) => [x + dx, y + dy]) };
        return { ...el, x: o.x + dx, y: o.y + dy };
      }
      if (t.modo === 'vertice') {
        const punti = o.punti.map(q => [...q]); punti[t.indice] = p; return { ...el, punti };
      }
      if (t.modo === 'ruota') {
        const ang = Math.atan2(p[1] - o.y, p[0] - o.x) * 180 / Math.PI + 90;
        return { ...el, rot: Math.round(((ang % 360) + 360) % 360) };
      }
      if (t.modo === 'ridimensiona') {
        const a = -(o.rot || 0) * Math.PI / 180;
        const lx = (p[0] - o.x) * Math.cos(a) - (p[1] - o.y) * Math.sin(a);
        const ly = (p[0] - o.x) * Math.sin(a) + (p[1] - o.y) * Math.cos(a);
        return { ...el, w: Math.max(4, Math.round(Math.abs(lx) * 20) / 10), h: Math.max(4, Math.round(Math.abs(ly) * 20) / 10) };
      }
      if (t.modo === 'raggio') {
        return { ...el, raggio_m: Math.max(1, Math.round(px2m(dist([o.x, o.y], p)) * 10) / 10) };
      }
      return el;
    });
  };
  const su = () => { trascina.current = null; };

  // ── Tastiera ───────────────────────────────────────────────────────────────
  useEffect(() => {
    const k = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return;
      if ((e.key === 'Delete' || e.key === 'Backspace') && sel) {
        setElementi(els => els.filter(x => x.id !== sel)); setSel(null);
      } else if (e.key === 'Escape') {
        setBozza([]); setStrumento('seleziona');
      } else if (e.key === 'Enter') {
        terminaLinea();
      }
    };
    window.addEventListener('keydown', k);
    return () => window.removeEventListener('keydown', k);
  }, [sel, terminaLinea]);

  // ── Sfondo ─────────────────────────────────────────────────────────────────
  const dopoSfondo = (r, msg) => {
    setS(x => ({ ...x, ...r.data, elementi: undefined })); setZoom(null); notify(msg, 'success');
  };
  const usaDocumento = async () => {
    if (!docSfondo) return;
    try { dopoSfondo(await sfondoDaDocumento(progettoId, schemaId, Number(docSfondo), Number(pagina) || 1), 'Sfondo impostato'); }
    catch (e) { notify(e.message, 'error'); }
  };
  const caricaFile = async (file) => {
    if (!file) return;
    const fd = new FormData(); fd.append('file', file); fd.append('pagina', String(Number(pagina) || 1));
    try { dopoSfondo(await caricaSfondo(progettoId, schemaId, fd), 'Sfondo caricato'); }
    catch (e) { notify(e.message, 'error'); }
  };
  const rimuoviSfondo = async () => {
    if (!window.confirm('Togliere l\'immagine di sfondo? Anche la taratura della scala andrà rifatta.')) return;
    try { dopoSfondo(await togliSfondo(progettoId, schemaId), 'Sfondo rimosso'); } catch (e) { notify(e.message, 'error'); }
  };

  // ── Esportazione PNG (con l'avviso CAD stampato) ───────────────────────────
  const esportaPng = async () => {
    const svg = svgRef.current.cloneNode(true);
    svg.querySelectorAll('[data-ui="1"]').forEach(n => n.remove());
    svg.setAttribute('width', s.sfondo_w); svg.setAttribute('height', s.sfondo_h);
    const img = svg.querySelector('image');
    if (img) {
      const blob = await (await fetch(sfondoUrl(progettoId, schemaId, s.updated_at))).blob();
      const dataUrl = await new Promise(res => { const fr = new FileReader(); fr.onload = () => res(fr.result); fr.readAsDataURL(blob); });
      img.setAttribute('href', dataUrl);
    }
    const testo = new XMLSerializer().serializeToString(svg);
    const immagine = new Image();
    immagine.onload = () => {
      const fascia = Math.max(40, Math.round(s.sfondo_w / 40));
      const c = document.createElement('canvas');
      c.width = s.sfondo_w; c.height = s.sfondo_h + fascia;
      const ctx = c.getContext('2d');
      ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, c.width, c.height);
      ctx.drawImage(immagine, 0, 0);
      ctx.fillStyle = '#FFF4D6'; ctx.fillRect(0, s.sfondo_h, c.width, fascia);
      ctx.fillStyle = '#8A4B00'; ctx.font = `bold ${Math.round(fascia * 0.42)}px Arial`; ctx.textBaseline = 'middle';
      ctx.fillText(`⚠ ${AVVISO}  —  ${s.nome}`, 16, s.sfondo_h + fascia / 2);
      c.toBlob(b => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(b); a.download = `Schema_${s.nome.replace(/[^A-Za-z0-9]+/g, '_')}.png`;
        a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
      }, 'image/png');
    };
    immagine.onerror = () => notify('Esportazione PNG non riuscita', 'error');
    immagine.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(testo);
  };

  if (!s) return <div style={{ padding: 30, color: '#8A9BB0' }}>Caricamento schema…</div>;

  const W = s.sfondo_w, H = s.sfondo_h;
  const tratto = Math.max(1.5, W / 800);
  const font = Math.max(10, W / 110);
  const maniglia = 7 / (zoom || 1);                                // ~7 px sullo schermo a qualsiasi zoom
  const tipiLinea = ['recinzione', 'ponteggio', 'percorso'];
  const simboli = Object.keys(catalogo).filter(k => !tipiLinea.includes(k) && k !== 'testo');
  const cursoreStile = strumento === 'seleziona' ? 'default' : 'crosshair';

  const bottone = (attivo) => ({ fontSize: '0.78rem', padding: '5px 9px', border: `1.5px solid ${attivo ? '#1A3A5C' : '#DCE3ED'}`,
    background: attivo ? '#EEF4FA' : 'white', borderRadius: 6, cursor: 'pointer', textAlign: 'left' });

  return (
    <div data-testid="editor-schema">
      {/* Intestazione */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 10 }}>
        <button className="btn btn-ghost btn-sm" onClick={onChiudi}>← Schemi</button>
        <h3 style={{ margin: 0, color: '#1A3A5C' }}>🗺️ {s.nome}</h3>
        <span style={{ fontSize: '0.75rem', color: '#8A9BB0' }} data-testid="stato-salvataggio">{stato}</span>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
          <button className="btn btn-ghost btn-sm" onClick={esportaPng}>⬇ PNG</button>
          {mpp ? <a className="btn btn-gold btn-sm" href={dxfUrl(progettoId, schemaId)} download>⬇ DXF (CAD)</a>
            : <button className="btn btn-ghost btn-sm" onClick={() => notify('Per esportare in DXF tara prima la scala (📏 Taratura scala)', 'error')}>⬇ DXF (CAD)</button>}
        </div>
      </div>
      <div className="warn-box" style={{ fontSize: '0.8rem', marginBottom: 10 }} data-testid="avviso-cad">⚠️ {AVVISO}</div>
      {solaLettura && <div className="info-box" style={{ fontSize: '0.8rem', marginBottom: 10 }}>🔒 Progetto chiuso: lo schema è in sola lettura (puoi esportarlo).</div>}

      {/* Barra strumenti */}
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
        <button style={bottone(strumento === 'seleziona')} onClick={() => { setStrumento('seleziona'); setBozza([]); }}>🖱️ Seleziona e sposta</button>
        <button style={bottone(strumento === 'scala')} onClick={() => { setStrumento('scala'); setBozza([]); setSel(null); }}>📏 Taratura scala</button>
        <button style={bottone(strumento === 'testo')} onClick={() => { setStrumento('testo'); setBozza([]); }}>T Testo</button>
        <span style={{ fontSize: '0.75rem', color: mpp ? '#27AE60' : '#8A6D00', marginLeft: 6 }} data-testid="stato-scala">
          {mpp ? `Scala: 10 m = ${fmt(10 / mpp, 0)} px` : 'Scala non tarata: misure indicative'}
        </span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: 4, alignItems: 'center' }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setZoom(z => Math.max(0.1, (z || 1) / 1.25))}>－</button>
          <span style={{ fontSize: '0.75rem', width: 44, textAlign: 'center' }}>{Math.round((zoom || 1) * 100)}%</span>
          <button className="btn btn-ghost btn-sm" onClick={() => setZoom(z => Math.min(4, (z || 1) * 1.25))}>＋</button>
          <button className="btn btn-ghost btn-sm" onClick={() => setZoom(null)}>Adatta</button>
        </span>
      </div>
      {strumento === 'scala' && <div className="info-box" style={{ fontSize: '0.8rem', marginBottom: 8 }}>
        📏 Clicca due punti di cui conosci la distanza reale (es. i due estremi di una quota della tavola), poi inserisci i metri.</div>}
      {strumento.startsWith('linea:') && <div className="info-box" style={{ fontSize: '0.8rem', marginBottom: 8 }}>
        ✏️ Clicca i punti della linea. Doppio clic o Invio per terminare, Esc per annullare.
        {bozza.length >= 2 && <button className="btn btn-gold btn-sm" style={{ marginLeft: 8 }} onClick={terminaLinea}>Termina linea</button>}</div>}
      {strumento.startsWith('aggiungi:') && <div className="info-box" style={{ fontSize: '0.8rem', marginBottom: 8 }}>
        ➕ Clicca sullo schema dove posizionare: {catalogo[strumento.slice(9)]?.etichetta}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '250px 1fr', gap: 12, alignItems: 'start' }}>
        {/* Colonna sinistra: tavolozza, proprietà, sfondo */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div className="card" style={{ padding: 10 }}>
            <div style={{ fontWeight: 700, fontSize: '0.8rem', color: '#1A3A5C', marginBottom: 6 }}>Linee</div>
            {tipiLinea.map(t => (
              <button key={t} data-testid={`palette-${t}`} style={{ ...bottone(strumento === `linea:${t}`), width: '100%', marginBottom: 3 }}
                onClick={() => { setStrumento(`linea:${t}`); setBozza([]); setSel(null); }}>
                <span style={{ color: colore(t) }}>{ICONE[t]}</span> {catalogo[t]?.etichetta}
                {previsti[t] && <span title="Previsto nella tappa 9" style={{ color: '#C88B2A' }}> ●</span>}
              </button>
            ))}
            <div style={{ fontWeight: 700, fontSize: '0.8rem', color: '#1A3A5C', margin: '8px 0 6px' }}>Elementi</div>
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              {simboli.map(t => (
                <button key={t} data-testid={`palette-${t}`} style={{ ...bottone(strumento === `aggiungi:${t}`), width: '100%', marginBottom: 3 }}
                  onClick={() => { setStrumento(`aggiungi:${t}`); setBozza([]); }}>
                  {ICONE[t]} {catalogo[t]?.etichetta}
                  {previsti[t] && <span title="Previsto nella tappa 9" style={{ color: '#C88B2A' }}> ●</span>}
                </button>
              ))}
            </div>
            {Object.keys(previsti).length > 0 && <div style={{ fontSize: '0.68rem', color: '#8A9BB0', marginTop: 6 }}>
              <span style={{ color: '#C88B2A' }}>●</span> previsto nella tappa 9</div>}
          </div>

          {selezionato && (
            <div className="card" style={{ padding: 10 }} data-testid="proprieta">
              <div style={{ fontWeight: 700, fontSize: '0.8rem', color: '#1A3A5C', marginBottom: 6 }}>Elemento selezionato</div>
              <label style={{ fontSize: '0.72rem' }}>Etichetta</label>
              <input className="form-control" style={{ fontSize: '0.8rem', marginBottom: 6 }} value={selezionato.etichetta || ''}
                onChange={e => aggiorna(sel, el => ({ ...el, etichetta: e.target.value, ...(el.tipo === 'testo' ? { testo: e.target.value } : {}) }))} />
              {selezionato.w !== undefined && selezionato.tipo !== 'testo' && selezionato.tipo !== 'gru' && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 4, fontSize: '0.72rem' }}>
                  <label>Largh. ({mpp ? 'm' : '≈m'})<input className="form-control" type="number" step="0.1" value={Math.round(px2m(selezionato.w) * 10) / 10}
                    onChange={e => aggiorna(sel, el => ({ ...el, w: m2px(Number(e.target.value) || 0.1) }))} /></label>
                  <label>Prof. ({mpp ? 'm' : '≈m'})<input className="form-control" type="number" step="0.1" value={Math.round(px2m(selezionato.h) * 10) / 10}
                    onChange={e => aggiorna(sel, el => ({ ...el, h: m2px(Number(e.target.value) || 0.1) }))} /></label>
                  <label>Rot. (°)<input className="form-control" type="number" value={selezionato.rot || 0}
                    onChange={e => aggiorna(sel, el => ({ ...el, rot: Number(e.target.value) || 0 }))} /></label>
                </div>
              )}
              {selezionato.tipo === 'gru' && (
                <label style={{ fontSize: '0.72rem' }}>Raggio d'azione ({mpp ? 'm' : '≈m, scala non tarata'})
                  <input className="form-control" type="number" step="0.5" data-testid="raggio-gru" value={selezionato.raggio_m || 0}
                    onChange={e => aggiorna(sel, el => ({ ...el, raggio_m: Number(e.target.value) || 1 }))} /></label>
              )}
              {selezionato.punti && (
                <div style={{ fontSize: '0.75rem', color: '#5A6B7D' }} data-testid="lunghezza-linea">
                  Lunghezza: {fmt(px2m(selezionato.punti.slice(1).reduce((t, q, i) => t + dist(selezionato.punti[i], q), 0)))} m{mpp ? '' : ' (indicativa)'}
                  <div style={{ fontSize: '0.68rem' }}>Trascina i punti per modificarla.</div>
                </div>
              )}
              <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => {
                  const c = { ...JSON.parse(JSON.stringify(selezionato)), id: nuovoId() };
                  if (c.punti) c.punti = c.punti.map(([x, y]) => [x + 20, y + 20]); else { c.x += 20; c.y += 20; }
                  setElementi(els => [...els, c]); setSel(c.id);
                }}>Duplica</button>
                <button className="btn btn-danger btn-sm" onClick={() => { setElementi(els => els.filter(x => x.id !== sel)); setSel(null); }}>Elimina</button>
              </div>
            </div>
          )}

          <div className="card" style={{ padding: 10 }}>
            <div style={{ fontWeight: 700, fontSize: '0.8rem', color: '#1A3A5C', marginBottom: 6 }}>Sfondo (planimetria)</div>
            {s.sfondo_origine && <div style={{ fontSize: '0.7rem', color: '#5A6B7D', marginBottom: 6 }}>Attuale: {s.sfondo_origine}</div>}
            {documentiSfondo.length > 0 && (
              <>
                <select className="form-control" style={{ fontSize: '0.75rem', marginBottom: 4 }} value={docSfondo} onChange={e => setDocSfondo(e.target.value)}>
                  {documentiSfondo.map(d => <option key={d.id} value={d.id}>{d.nome_file}{d.pagine ? ` (${d.pagine} pag.)` : ''}</option>)}
                </select>
              </>
            )}
            <div style={{ display: 'flex', gap: 4, alignItems: 'center', fontSize: '0.72rem', marginBottom: 4 }}>
              Pagina <input className="form-control" type="number" min="1" style={{ width: 60 }} value={pagina} onChange={e => setPagina(e.target.value)} />
              {documentiSfondo.length > 0 && <button className="btn btn-ghost btn-sm" onClick={usaDocumento}>Usa</button>}
            </div>
            <label className="btn btn-ghost btn-sm" style={{ display: 'block', textAlign: 'center', cursor: 'pointer' }}>
              Carica PDF / immagine…
              <input type="file" accept=".pdf,.jpg,.jpeg,.png" style={{ display: 'none' }} data-testid="file-sfondo"
                onChange={e => { caricaFile(e.target.files?.[0]); e.target.value = ''; }} />
            </label>
            {s.ha_sfondo && <button className="btn btn-ghost btn-sm" style={{ width: '100%', marginTop: 4 }} onClick={rimuoviSfondo}>Togli sfondo</button>}
          </div>
        </div>

        {/* Area di disegno */}
        <div ref={areaRef} style={{ overflow: 'auto', maxHeight: '78vh', border: '1px solid #DCE3ED', borderRadius: 8, background: '#F4F6F9' }}>
          <svg ref={svgRef} xmlns="http://www.w3.org/2000/svg" data-testid="area-schema"
            width={W * (zoom || 1)} height={H * (zoom || 1)} viewBox={`0 0 ${W} ${H}`}
            style={{ display: 'block', cursor: cursoreStile, touchAction: 'none', userSelect: 'none' }}
            onPointerMove={muovi} onPointerUp={su} onPointerLeave={su}
            onDoubleClick={() => terminaLinea()}>
            <defs>
              <pattern id="griglia" width="50" height="50" patternUnits="userSpaceOnUse">
                <path d="M 50 0 L 0 0 0 50" fill="none" stroke="#E3E8EF" strokeWidth="1" />
              </pattern>
              <marker id="freccia" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto" markerUnits="strokeWidth">
                <path d="M0,0 L10,5 L0,10 z" fill={COLORE.percorso} />
              </marker>
            </defs>
            <rect x="0" y="0" width={W} height={H} fill={s.ha_sfondo ? 'white' : 'url(#griglia)'} onPointerDown={giuSfondo} />
            {s.ha_sfondo && <image href={sfondoUrl(progettoId, schemaId, s.updated_at)} x="0" y="0" width={W} height={H}
              preserveAspectRatio="none" onPointerDown={giuSfondo} />}

            {elementi.map(el => {
              const c = colore(el.tipo);
              const scelto = el.id === sel;
              if (el.punti) {
                const d = el.punti.map(q => q.join(',')).join(' ');
                return (
                  <g key={el.id} data-testid={`el-${el.tipo}`}>
                    <polyline points={d} fill="none" stroke="transparent" strokeWidth={tratto * 8} style={{ cursor: 'move' }}
                      onPointerDown={e => giuElemento(e, el)} />
                    <polyline points={d} fill="none" stroke={c} pointerEvents="none"
                      strokeWidth={el.tipo === 'ponteggio' ? tratto * 4 : tratto * 2.5}
                      strokeDasharray={el.tipo === 'recinzione' ? `${tratto * 6},${tratto * 3}` : undefined}
                      markerEnd={el.tipo === 'percorso' ? 'url(#freccia)' : undefined} />
                    <text x={el.punti[0][0]} y={el.punti[0][1] - font * 0.6} fontSize={font} fill={c} fontWeight="bold" pointerEvents="none">{el.etichetta}</text>
                    {scelto && el.punti.map((q, i) => (
                      <circle key={i} data-ui="1" cx={q[0]} cy={q[1]} r={maniglia} fill="white" stroke={c} strokeWidth={tratto}
                        style={{ cursor: 'grab' }} onPointerDown={e => giuElemento(e, el, 'vertice', { indice: i })} />
                    ))}
                  </g>
                );
              }
              if (el.tipo === 'testo') {
                return (
                  <text key={el.id} data-testid="el-testo" x={el.x} y={el.y} fontSize={font * 1.2} fill={c} fontWeight="bold"
                    style={{ cursor: 'move' }} stroke={scelto ? '#FFD54F' : 'none'} strokeWidth={scelto ? 0.6 : 0}
                    onPointerDown={e => giuElemento(e, el)}>{el.testo || el.etichetta}</text>
                );
              }
              if (el.tipo === 'gru') {
                const r = m2px(el.raggio_m || 25);
                return (
                  <g key={el.id} data-testid="el-gru">
                    <circle cx={el.x} cy={el.y} r={r} fill={c} fillOpacity="0.07" stroke={c} strokeWidth={tratto} strokeDasharray={`${tratto * 5},${tratto * 3}`} pointerEvents="none" />
                    <circle cx={el.x} cy={el.y} r={el.w / 2} fill={c} fillOpacity="0.35" stroke={c} strokeWidth={tratto * 1.5}
                      style={{ cursor: 'move' }} onPointerDown={e => giuElemento(e, el)} />
                    <text x={el.x} y={el.y - el.w / 2 - font * 0.4} fontSize={font} textAnchor="middle" fill={c} fontWeight="bold" pointerEvents="none">
                      {el.etichetta} · R {fmt(el.raggio_m || 25)} m</text>
                    {scelto && <circle data-ui="1" cx={el.x + r} cy={el.y} r={maniglia} fill="white" stroke={c} strokeWidth={tratto}
                      style={{ cursor: 'ew-resize' }} onPointerDown={e => giuElemento(e, el, 'raggio')} />}
                  </g>
                );
              }
              return (
                <g key={el.id} data-testid={`el-${el.tipo}`} transform={`translate(${el.x} ${el.y}) rotate(${el.rot || 0})`}>
                  <rect x={-el.w / 2} y={-el.h / 2} width={el.w} height={el.h} fill={c} fillOpacity="0.28" stroke={scelto ? '#1A3A5C' : c}
                    strokeWidth={scelto ? tratto * 2 : tratto} rx={tratto} style={{ cursor: 'move' }} onPointerDown={e => giuElemento(e, el)} />
                  <text x="0" y={Math.min(el.h / 2, font) * 0.35} fontSize={Math.min(font * 1.3, el.h * 0.8, el.w * 0.8)} textAnchor="middle" pointerEvents="none">{ICONE[el.tipo] || '■'}</text>
                  <text x="0" y={el.h / 2 + font * 1.1} fontSize={font * 0.85} textAnchor="middle" fill="#1A3A5C" fontWeight="bold" pointerEvents="none">{el.etichetta}</text>
                  {scelto && (
                    <g data-ui="1">
                      <circle cx={el.w / 2} cy={el.h / 2} r={maniglia} fill="white" stroke="#1A3A5C" strokeWidth={tratto} style={{ cursor: 'nwse-resize' }}
                        onPointerDown={e => giuElemento(e, el, 'ridimensiona')} />
                      <line x1="0" y1={-el.h / 2} x2="0" y2={-el.h / 2 - maniglia * 3} stroke="#1A3A5C" strokeWidth={tratto} />
                      <circle cx="0" cy={-el.h / 2 - maniglia * 3} r={maniglia} fill="#FFD54F" stroke="#1A3A5C" strokeWidth={tratto} style={{ cursor: 'grab' }}
                        onPointerDown={e => giuElemento(e, el, 'ruota')} />
                    </g>
                  )}
                </g>
              );
            })}

            {/* Linea o taratura in corso */}
            {bozza.length > 0 && (
              <g data-ui="1" pointerEvents="none">
                <polyline points={[...bozza, ...(cursore ? [cursore] : [])].map(q => q.join(',')).join(' ')} fill="none"
                  stroke={strumento === 'scala' ? '#E67E22' : colore(strumento.slice(6))} strokeWidth={tratto * 2} strokeDasharray={`${tratto * 4},${tratto * 2}`} />
                {bozza.map((q, i) => <circle key={i} cx={q[0]} cy={q[1]} r={maniglia * 0.8} fill="#E67E22" />)}
              </g>
            )}
            {s.scala?.punti && strumento === 'scala' && bozza.length === 0 && (
              <line data-ui="1" x1={s.scala.punti[0][0]} y1={s.scala.punti[0][1]} x2={s.scala.punti[1][0]} y2={s.scala.punti[1][1]}
                stroke="#E67E22" strokeWidth={tratto * 2} pointerEvents="none" />
            )}
          </svg>
        </div>
      </div>
    </div>
  );
}
