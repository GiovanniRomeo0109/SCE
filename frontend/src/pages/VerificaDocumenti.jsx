import { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNotify } from '../App';
import { verificaPsc, verificaPos, verificaCongruita, generaVerbale as apiGeneraVerbale } from '../utils/api';

// ── Costanti ─────────────────────────────────────────────────────────────────
const SEV = {
  CRITICO:    { color: '#C0392B', bg: '#FDEDEC', badge: '#C0392B', emoji: '🔴', label: 'CRITICO' },
  IMPORTANTE: { color: '#E67E22', bg: '#FEF9E7', badge: '#E67E22', emoji: '🟡', label: 'IMPORTANTE' },
  CONSIGLIO:  { color: '#27AE60', bg: '#EAFAF1', badge: '#27AE60', emoji: '🟢', label: 'CONSIGLIO' },
};

const GIUDIZIO_COLOR = {
  'CONFORME':              '#27AE60',
  'NON CONFORME':          '#C0392B',
  'CONFORME CON RISERVE':  '#E67E22',
  'CONGRUENTE':            '#27AE60',
  'NON CONGRUENTE':        '#C0392B',
  'CONGRUENTE CON RISERVE':'#E67E22',
};

// ── Componenti UI ─────────────────────────────────────────────────────────────

function DropZone({ label, accept, multiple, onFiles, files }) {
  const ref = useRef();
  const [drag, setDrag] = useState(false);

  const handleDrop = (e) => {
    e.preventDefault();
    setDrag(false);
    const dropped = Array.from(e.dataTransfer.files);
    onFiles(multiple ? dropped : [dropped[0]]);
  };

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDrag(true); }}
      onDragLeave={() => setDrag(false)}
      onDrop={handleDrop}
      onClick={() => ref.current.click()}
      style={{
        border: `2px dashed ${drag ? '#1A3A5C' : '#B0BEC5'}`,
        borderRadius: 10, padding: '24px 16px', textAlign: 'center',
        cursor: 'pointer', background: drag ? '#EEF4FA' : '#FAFAFA',
        transition: 'all 0.2s',
      }}>
      <input ref={ref} type="file" accept={accept}
        multiple={multiple} style={{ display: 'none' }}
        onChange={e => onFiles(Array.from(e.target.files))} />
      <div style={{ fontSize: '2rem', marginBottom: 8 }}>📄</div>
      <div style={{ fontWeight: 600, color: '#1A3A5C', marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: '0.8rem', color: '#8A9BB0' }}>
        {multiple ? 'Trascina qui uno o più file (max 5)' : 'Trascina qui il file'}
        {' '} — PDF o DOCX
      </div>
      {files.length > 0 && (
        <div style={{ marginTop: 10, display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'center' }}>
          {files.map((f, i) => (
            <span key={i} style={{
              background: '#E3F2FD', color: '#1A3A5C', borderRadius: 20,
              padding: '3px 10px', fontSize: '0.78rem', fontWeight: 500,
            }}>📎 {f.name}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function BadgeSeverita({ sev }) {
  const s = SEV[sev] || SEV.CONSIGLIO;
  return (
    <span style={{
      background: s.badge, color: '#fff', borderRadius: 12,
      padding: '2px 10px', fontSize: '0.72rem', fontWeight: 700,
      letterSpacing: '0.5px',
    }}>{s.emoji} {s.label}</span>
  );
}

function Punteggio({ valore, giudizio }) {
  const col = GIUDIZIO_COLOR[giudizio] || '#8A9BB0';
  const size = 90;
  const r = 36, cx = 45, cy = 45;
  const circ = 2 * Math.PI * r;
  const dash = (valore / 100) * circ;

  return (
    <div style={{ textAlign: 'center' }}>
      <svg width={size} height={size}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#EEE" strokeWidth={8} />
        <circle cx={cx} cy={cy} r={r} fill="none" stroke={col} strokeWidth={8}
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`} />
        <text x={cx} y={cy+5} textAnchor="middle"
          style={{ fontSize: 15, fontWeight: 700, fill: col }}>{valore}%</text>
      </svg>
      <div style={{ fontSize: '0.72rem', fontWeight: 700, color: col, marginTop: 2 }}>{giudizio}</div>
    </div>
  );
}

function NonConformita({ item, index, onModifica }) {
  const [aperta, setAperta] = useState(item.severita === 'CRITICO');
  const [nota, setNota] = useState(item.nota_utente || '');
  const s = SEV[item.severita] || SEV.CONSIGLIO;

  return (
    <div style={{
      border: `1.5px solid ${s.color}40`,
      borderRadius: 8, marginBottom: 10, overflow: 'hidden',
    }}>
      {/* Header incongruenza */}
      <div
        onClick={() => setAperta(!aperta)}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 14px', cursor: 'pointer',
          background: s.bg, borderBottom: aperta ? `1px solid ${s.color}30` : 'none',
        }}>
        <span style={{ fontSize: '1.1rem' }}>{aperta ? '▼' : '▶'}</span>
        <BadgeSeverita sev={item.severita} />
        <span style={{ fontWeight: 600, color: '#1A3A5C', fontSize: '0.875rem', flex: 1 }}>
          <span style={{ color: '#8A9BB0', marginRight: 6 }}>{item.id}</span>
          {item.descrizione || item.elemento}
        </span>
        {item.validata && (
          <span style={{ color: '#27AE60', fontWeight: 700, fontSize: '0.78rem' }}>✅ VALIDATA</span>
        )}
      </div>

      {/* Corpo espandibile */}
      {aperta && (
        <div style={{ padding: '12px 14px', background: '#fff' }}>
          {/* Campi specifici verifica */}
          {item.norma_violata && (
            <div style={{ marginBottom: 8 }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#8A9BB0' }}>NORMA VIOLATA: </span>
              <span style={{ fontSize: '0.85rem', color: '#C0392B', fontWeight: 600 }}>{item.norma_violata}</span>
            </div>
          )}
          {item.sanzione_applicabile && (
            <div style={{ marginBottom: 8, padding: '6px 10px', background: '#FFF3F3', borderRadius: 6 }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#C0392B' }}>⚖️ SANZIONE: </span>
              <span style={{ fontSize: '0.82rem', color: '#8B0000' }}>{item.sanzione_applicabile}</span>
            </div>
          )}

          {/* Campi congruità */}
          {item.valore_psc && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
              <div style={{ padding: 8, background: '#EEF4FA', borderRadius: 6 }}>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#1A3A5C', marginBottom: 3 }}>📗 NEL PSC:</div>
                <div style={{ fontSize: '0.85rem' }}>{item.valore_psc}</div>
              </div>
              <div style={{ padding: 8, background: '#FEF9E7', borderRadius: 6 }}>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#C88B2A', marginBottom: 3 }}>📄 NEL POS:</div>
                <div style={{ fontSize: '0.85rem' }}>{item.valore_pos}</div>
              </div>
            </div>
          )}

          {/* Testo trovato / testo corretto */}
          {item.testo_trovato && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#8A9BB0', marginBottom: 3 }}>TESTO TROVATO:</div>
              <div style={{ padding: '6px 10px', background: '#F5F5F5', borderRadius: 6, fontSize: '0.82rem', fontStyle: item.testo_trovato === 'ASSENTE' ? 'italic' : 'normal', color: item.testo_trovato === 'ASSENTE' ? '#C0392B' : 'inherit' }}>
                {item.testo_trovato}
              </div>
            </div>
          )}

          {(item.testo_corretto || item.modifica_richiesta) && (
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#27AE60', marginBottom: 3 }}>
                {item.testo_corretto ? '✏️ TESTO CORRETTO DA INSERIRE:' : '🔧 MODIFICA RICHIESTA:'}
              </div>
              <div style={{ padding: '6px 10px', background: '#EAFAF1', borderRadius: 6, fontSize: '0.85rem', color: '#1A5C2A' }}>
                {item.testo_corretto || item.modifica_richiesta}
              </div>
            </div>
          )}

          {item.sezione_pos_da_modificare && (
            <div style={{ fontSize: '0.78rem', color: '#8A9BB0', marginBottom: 8 }}>
              📍 Sezione da modificare: <strong>{item.sezione_pos_da_modificare}</strong>
            </div>
          )}

          {/* Nota del professionista */}
          <div>
            <label style={{ fontSize: '0.75rem', fontWeight: 700, color: '#8A9BB0', display: 'block', marginBottom: 4 }}>
              📝 NOTA DEL PROFESSIONISTA (opzionale):
            </label>
            <textarea
              value={nota}
              onChange={e => setNota(e.target.value)}
              placeholder="Aggiungi una nota o modifica la soluzione proposta..."
              rows={2}
              style={{ width: '100%', borderRadius: 6, border: '1px solid #DDD', padding: '6px 8px', fontSize: '0.85rem', resize: 'vertical', boxSizing: 'border-box' }}
            />
          </div>

          <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
            <button
              className="btn btn-primary"
              style={{ fontSize: '0.82rem', padding: '6px 14px' }}
              onClick={() => onModifica(index, 'validata', true, nota)}>
              ✅ Valida modifica
            </button>
            {item.validata && (
              <button
                className="btn btn-ghost"
                style={{ fontSize: '0.82rem', padding: '6px 14px' }}
                onClick={() => onModifica(index, 'validata', false, nota)}>
                ↩ Annulla validazione
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function RiepilogoCard({ rie, giudizio, punteggio }) {
  return (
    <div style={{
      display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 20,
      padding: 20, background: '#F8F5F0', borderRadius: 10,
      border: '1px solid #E0D4C0', marginBottom: 20,
    }}>
      <Punteggio valore={punteggio} giudizio={giudizio} />
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {[
          { label: 'CRITICI',    val: rie.critici,    color: '#C0392B', bg: '#FDEDEC' },
          { label: 'IMPORTANTI', val: rie.importanti, color: '#E67E22', bg: '#FEF9E7' },
          { label: 'CONSIGLI',   val: rie.consigli,   color: '#27AE60', bg: '#EAFAF1' },
          { label: 'CONFORMI',   val: rie.conformi || rie.congruenti, color: '#1A3A5C', bg: '#EEF4FA' },
        ].map(({ label, val, color, bg }) => (
          <div key={label} style={{ textAlign: 'center', padding: '10px 6px', background: bg, borderRadius: 8 }}>
            <div style={{ fontSize: '1.6rem', fontWeight: 700, color }}>{val ?? 0}</div>
            <div style={{ fontSize: '0.7rem', color, fontWeight: 600 }}>{label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════
// PAGINA PRINCIPALE
// ═══════════════════════════════════════════════════════════════════════════

export default function VerificaDocumenti() {
  const notify = useNotify();
  const nav = useNavigate();

  // Modalità attiva: 'psc' | 'pos' | 'congruita'
  const [modo, setModo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState('');
  const [nomeCantiere, setNomeCantiere] = useState('');

  // File caricati
  const [filePsc, setFilePsc] = useState([]);
  const [filePos, setFilePos] = useState([]);
  const [filePscCongruita, setFilePscCongruita] = useState([]);
  const [filePosCongruita, setFilePosCongruita] = useState([]);

  // Risultati
  const [risultatoPsc, setRisultatoPsc]         = useState(null);
  const [risultatiPos, setRisultatiPos]          = useState([]);
  const [risultatiCongruita, setRisultatiCongruita] = useState([]);

  // Incongruenze modificabili
  const [incMap, setIncMap] = useState({}); // { posFilename: [incongruenze] }

  const aggiornaIncongruenza = (posFilename, idx, campo, valore, nota) => {
    setIncMap(prev => {
      const lista = [...(prev[posFilename] || [])];
      lista[idx] = { ...lista[idx], [campo]: valore, nota_utente: nota };
      return { ...prev, [posFilename]: lista };
    });
  };

  // ── Avvia verifica PSC ────────────────────────────────────────────────────
  const avviaVerificaPsc = async () => {
    if (!filePsc.length) return notify('Carica un PSC da verificare', 'error');
    setLoading(true);
    setLoadingMsg('Analisi PSC in corso — può richiedere 1-2 minuti...');
    try {
      const fd = new FormData();
      fd.append('file', filePsc[0]);
      fd.append('nome_cantiere', nomeCantiere || filePsc[0].name);
      const res = await verificaPsc(fd);
      setRisultatoPsc(res.data);
      notify('Verifica PSC completata ✓', 'success');
    } catch (e) {
      notify('Errore: ' + e.message, 'error');
    } finally { setLoading(false); setLoadingMsg(''); }
  };

  // ── Avvia verifica POS ────────────────────────────────────────────────────
  const avviaVerificaPos = async () => {
    if (!filePos.length) return notify('Carica almeno un POS da verificare', 'error');
    setLoading(true);
    setLoadingMsg(`Analisi di ${filePos.length} POS in corso...`);
    try {
      const fd = new FormData();
      filePos.forEach(f => fd.append('files', f));
      fd.append('nome_cantiere', nomeCantiere || 'Cantiere');
      const res = await verificaPos(fd);
      setRisultatiPos(res.data.risultati || []);
      notify(`Verifica di ${res.data.totale_pos} POS completata ✓`, 'success');
    } catch (e) {
      notify('Errore: ' + e.message, 'error');
    } finally { setLoading(false); setLoadingMsg(''); }
  };

  // ── Avvia verifica congruità ──────────────────────────────────────────────
  const avviaVerificaCongruita = async () => {
    if (!filePscCongruita.length) return notify('Carica il PSC di riferimento', 'error');
    if (!filePosCongruita.length) return notify('Carica almeno un POS', 'error');
    setLoading(true);
    setLoadingMsg('Analisi congruità PSC-POS in corso...');
    try {
      const fd = new FormData();
      fd.append('psc', filePscCongruita[0]);
      filePosCongruita.forEach(f => fd.append('pos_files', f));
      fd.append('nome_cantiere', nomeCantiere || 'Cantiere');
      const res = await verificaCongruita(fd);
      setRisultatiCongruita(res.data.risultati || []);
      // Inizializza le incongruenze modificabili
      const newIncMap = {};
      (res.data.risultati || []).forEach(r => {
        newIncMap[r.pos_filename] = r.incongruenze || [];
      });
      setIncMap(newIncMap);
      notify('Verifica congruità completata ✓', 'success');
    } catch (e) {
      notify('Errore: ' + e.message, 'error');
    } finally { setLoading(false); setLoadingMsg(''); }
  };

  // ── Genera verbale ────────────────────────────────────────────────────────
  const generaVerbale = async (posFilename, pscFilename, incongruenze) => {
    setLoading(true);
    setLoadingMsg('Generazione verbale PDF...');
    try {
      const res = await apiGeneraVerbale({
        incongruenze,
        pos_filename: posFilename,
        psc_filename: pscFilename,
        nome_cantiere: nomeCantiere || 'Cantiere',
      });
      window.open(`/api/documents/download/${res.data.doc_id}`, '_blank');
      notify('Verbale generato ✓', 'success');
    } catch (e) {
      notify('Errore generazione verbale: ' + e.message, 'error');
    } finally { setLoading(false); setLoadingMsg(''); }
  };

  // ── Genera report PDF verifica ────────────────────────────────────────────
  const generaReportPdf = async (docId) => {
    window.open(`/api/documents/download/${docId}`, '_blank');
  };

  // ═══════════════════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════════════════

  return (
    <div>
      <div className="page-header">
        <h1>🔍 Verifica Documenti di Sicurezza</h1>
        <p>Verifica conformità PSC e POS al D.Lgs. 81/2008 — Aggiornato Marzo 2026</p>
      </div>

      {/* Overlay loading */}
      {loading && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(26,58,92,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 1000, flexDirection: 'column', gap: 16,
        }}>
          <div style={{ fontSize: '3rem' }}>🔍</div>
          <div style={{ color: '#fff', fontWeight: 700, fontSize: '1.1rem' }}>{loadingMsg}</div>
          <div style={{ color: '#C88B2A', fontSize: '0.85rem' }}>
            L'agente sta leggendo e analizzando il documento...
          </div>
        </div>
      )}

      <div style={{ maxWidth: 900 }}>

        {/* ── Campo nome cantiere ── */}
        <div className="form-group" style={{ marginBottom: 20 }}>
          <label className="form-label">Nome cantiere / progetto (per lo storico)</label>
          <input className="form-control" value={nomeCantiere}
            onChange={e => setNomeCantiere(e.target.value)}
            placeholder="es. Ristrutturazione Via Leopardi, Monza" />
        </div>

        {/* ── Selezione modalità ── */}
        {!modo ? (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16, marginBottom: 28 }}>
            {[
              { id: 'psc',      icon: '📗', label: 'Verifica PSC',          desc: 'Verifica conformità del Piano di Sicurezza e Coordinamento all\'Allegato XV' },
              { id: 'pos',      icon: '📘', label: 'Verifica POS',          desc: 'Verifica conformità di 1-5 Piani Operativi di Sicurezza all\'Allegato XV pt.3' },
              { id: 'congruita',icon: '🔗', label: 'Verifica Congruità',    desc: 'Verifica che i POS siano coerenti con il PSC di riferimento' },
            ].map(m => (
              <div key={m.id} onClick={() => setModo(m.id)} style={{
                padding: 20, borderRadius: 12, cursor: 'pointer',
                border: '2px solid #E0D4C0', background: '#FAFAFA',
                transition: 'all 0.2s', textAlign: 'center',
              }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = '#1A3A5C'; e.currentTarget.style.background = '#EEF4FA'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = '#E0D4C0'; e.currentTarget.style.background = '#FAFAFA'; }}>
                <div style={{ fontSize: '2.5rem', marginBottom: 8 }}>{m.icon}</div>
                <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 6 }}>{m.label}</div>
                <div style={{ fontSize: '0.78rem', color: '#8A9BB0', lineHeight: 1.4 }}>{m.desc}</div>
              </div>
            ))}
          </div>
        ) : (
          <button className="btn btn-ghost" style={{ marginBottom: 16 }}
            onClick={() => { setModo(null); setRisultatoPsc(null); setRisultatiPos([]); setRisultatiCongruita([]); }}>
            ← Cambia modalità
          </button>
        )}

        {/* ════════════════════════════════════════ */}
        {/* MODO: VERIFICA PSC                       */}
        {/* ════════════════════════════════════════ */}
        {modo === 'psc' && (
          <>
            <div style={{ padding: 20, background: '#F8F5F0', borderRadius: 10, marginBottom: 20 }}>
              <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 12, fontSize: '1rem' }}>
                📗 Verifica PSC — Carica il documento
              </div>
              <div className="info-box" style={{ marginBottom: 14, fontSize: '0.82rem' }}>
                L'agente verificherà: completezza formale (All. XV), soggetti, analisi rischi,
                organizzazione cantiere, DPI, costi sicurezza e correttezza normativa aggiornata a Marzo 2026.
              </div>
              <DropZone label="Carica PSC (PDF o DOCX)" accept=".pdf,.docx"
                multiple={false} files={filePsc} onFiles={setFilePsc} />
              <div style={{ marginTop: 14, textAlign: 'right' }}>
                <button className="btn btn-gold" onClick={avviaVerificaPsc}
                  disabled={!filePsc.length || loading}>
                  🔍 Avvia verifica PSC →
                </button>
              </div>
            </div>

            {risultatoPsc && (
              <div>
                <RiepilogoCard
                  rie={risultatoPsc.riepilogo || {}}
                  giudizio={risultatoPsc.giudizio_sintetico}
                  punteggio={risultatoPsc.punteggio_conformita} />

                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <h3 style={{ color: '#1A3A5C', margin: 0 }}>Non conformità rilevate</h3>
                  {risultatoPsc.doc_id && (
                    <button className="btn btn-primary" style={{ fontSize: '0.82rem' }}
                      onClick={() => generaReportPdf(risultatoPsc.doc_id)}>
                      ↓ Scarica Report PDF
                    </button>
                  )}
                </div>

                {(risultatoPsc.non_conformita || []).length === 0 ? (
                  <div className="info-box">✅ Nessuna non conformità rilevata — documento conforme.</div>
                ) : (
                  (risultatoPsc.non_conformita || []).map((item, i) => (
                    <NonConformita key={i} item={item} index={i}
                      onModifica={(idx, campo, val, nota) => {
                        setRisultatoPsc(prev => {
                          const nc = [...prev.non_conformita];
                          nc[idx] = { ...nc[idx], [campo]: val, nota_utente: nota };
                          return { ...prev, non_conformita: nc };
                        });
                      }} />
                  ))
                )}

                {risultatoPsc.note_aggiuntive && (
                  <div className="warn-box" style={{ marginTop: 16, fontSize: '0.85rem' }}>
                    📋 <strong>Note:</strong> {risultatoPsc.note_aggiuntive}
                  </div>
                )}
              </div>
            )}
          </>
        )}

        {/* ════════════════════════════════════════ */}
        {/* MODO: VERIFICA POS                       */}
        {/* ════════════════════════════════════════ */}
        {modo === 'pos' && (
          <>
            <div style={{ padding: 20, background: '#F8F5F0', borderRadius: 10, marginBottom: 20 }}>
              <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 12 }}>
                📘 Verifica POS — Carica i documenti (max 5)
              </div>
              <div className="info-box" style={{ marginBottom: 14, fontSize: '0.82rem' }}>
                Verifica: dati impresa, figure sicurezza, elenco lavoratori, formazione,
                macchine, sostanze pericolose, valutazione rischi specifici.
                Controlla anche il patentino imprese (art. 27 — obbligatorio dal 1/10/2024).
              </div>
              <DropZone label="Carica POS (PDF o DOCX) — fino a 5 file" accept=".pdf,.docx"
                multiple={true} files={filePos}
                onFiles={f => setFilePos(f.slice(0, 5))} />
              <div style={{ marginTop: 14, textAlign: 'right' }}>
                <button className="btn btn-gold" onClick={avviaVerificaPos}
                  disabled={!filePos.length || loading}>
                  🔍 Avvia verifica {filePos.length} POS →
                </button>
              </div>
            </div>

            {risultatiPos.map((ris, posIdx) => (
              <div key={posIdx} style={{ marginBottom: 28 }}>
                <div style={{
                  padding: '10px 16px', background: '#1A3A5C', borderRadius: '8px 8px 0 0',
                  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                  <span style={{ color: '#fff', fontWeight: 700 }}>
                    📘 POS {posIdx + 1}: {ris.impresa || ris.nome_file}
                  </span>
                  <span style={{
                    background: GIUDIZIO_COLOR[ris.giudizio_sintetico] || '#8A9BB0',
                    color: '#fff', borderRadius: 12, padding: '2px 12px', fontSize: '0.78rem', fontWeight: 700,
                  }}>{ris.giudizio_sintetico}</span>
                </div>
                <div style={{ border: '1px solid #1A3A5C', borderTop: 'none', borderRadius: '0 0 8px 8px', padding: 16 }}>
                  <RiepilogoCard rie={ris.riepilogo || {}} giudizio={ris.giudizio_sintetico}
                    punteggio={ris.punteggio_conformita} />
                  {(ris.non_conformita || []).map((item, i) => (
                    <NonConformita key={i} item={item} index={i} onModifica={() => {}} />
                  ))}
                  {ris.doc_id && (
                    <button className="btn btn-primary" style={{ marginTop: 10, fontSize: '0.82rem' }}
                      onClick={() => generaReportPdf(ris.doc_id)}>
                      ↓ Scarica Report PDF
                    </button>
                  )}
                </div>
              </div>
            ))}
          </>
        )}

        {/* ════════════════════════════════════════ */}
        {/* MODO: VERIFICA CONGRUITÀ                 */}
        {/* ════════════════════════════════════════ */}
        {modo === 'congruita' && (
          <>
            <div style={{ padding: 20, background: '#F8F5F0', borderRadius: 10, marginBottom: 20 }}>
              <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 12 }}>
                🔗 Verifica Congruità PSC-POS
              </div>
              <div className="info-box" style={{ marginBottom: 14, fontSize: '0.82rem' }}>
                L'agente verificherà che ogni POS sia coerente con il PSC:
                cantiere, date, attività, rischi interferenza, DPI, procedure e piano emergenze.
                Potrai validare ogni incongruenza e generare il Verbale PDF.
              </div>
              <div className="form-grid">
                <div>
                  <div style={{ fontWeight: 600, color: '#1A3A5C', marginBottom: 8, fontSize: '0.875rem' }}>
                    📗 PSC di riferimento
                  </div>
                  <DropZone label="Carica PSC" accept=".pdf,.docx"
                    multiple={false} files={filePscCongruita}
                    onFiles={setFilePscCongruita} />
                </div>
                <div>
                  <div style={{ fontWeight: 600, color: '#1A3A5C', marginBottom: 8, fontSize: '0.875rem' }}>
                    📘 POS da verificare (max 5)
                  </div>
                  <DropZone label="Carica POS (1-5 file)" accept=".pdf,.docx"
                    multiple={true} files={filePosCongruita}
                    onFiles={f => setFilePosCongruita(f.slice(0, 5))} />
                </div>
              </div>
              <div style={{ marginTop: 14, textAlign: 'right' }}>
                <button className="btn btn-gold" onClick={avviaVerificaCongruita}
                  disabled={!filePscCongruita.length || !filePosCongruita.length || loading}>
                  🔗 Avvia verifica congruità →
                </button>
              </div>
            </div>

            {risultatiCongruita.map((ris, posIdx) => {
              const posFilename = ris.pos_filename;
              const incLista = incMap[posFilename] || ris.incongruenze || [];
              const validate = incLista.filter(i => i.validata);

              return (
                <div key={posIdx} style={{ marginBottom: 28 }}>
                  <div style={{
                    padding: '10px 16px', background: '#2C3E50',
                    borderRadius: '8px 8px 0 0',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}>
                    <span style={{ color: '#fff', fontWeight: 700 }}>
                      🔗 {posFilename}
                    </span>
                    <span style={{
                      background: GIUDIZIO_COLOR[ris.giudizio] || '#8A9BB0',
                      color: '#fff', borderRadius: 12, padding: '2px 12px',
                      fontSize: '0.78rem', fontWeight: 700,
                    }}>{ris.giudizio}</span>
                  </div>

                  <div style={{ border: '1px solid #2C3E50', borderTop: 'none', borderRadius: '0 0 8px 8px', padding: 16 }}>
                    <RiepilogoCard
                      rie={ris.riepilogo || {}}
                      giudizio={ris.giudizio}
                      punteggio={Math.round(
                        ((ris.riepilogo?.congruenti || 0) /
                          Math.max(ris.riepilogo?.totale_verifiche || 1, 1)) * 100
                      )} />

                    {incLista.length === 0 ? (
                      <div className="info-box">✅ Nessuna incongruenza — POS congruente con il PSC.</div>
                    ) : (
                      <>
                        <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 10 }}>
                          Incongruenze rilevate — valida ciascuna per procedere
                        </div>
                        {incLista.map((inc, i) => (
                          <NonConformita key={i} item={inc} index={i}
                            onModifica={(idx, campo, val, nota) =>
                              aggiornaIncongruenza(posFilename, idx, campo, val, nota)
                            } />
                        ))}
                      </>
                    )}

                    {/* Azioni Verbale */}
                    <div style={{ marginTop: 16, display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                      <button className="btn btn-gold"
                        onClick={() => generaVerbale(posFilename, ris.psc_riferimento || filePscCongruita[0]?.name, incLista)}>
                        📄 Genera Verbale PDF (tutte le incongruenze)
                      </button>
                      {validate.length > 0 && (
                        <button className="btn btn-primary"
                          onClick={() => generaVerbale(posFilename, ris.psc_riferimento || filePscCongruita[0]?.name, validate)}>
                          ✅ Genera Verbale PDF (solo validate — {validate.length})
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </>
        )}

      </div>
    </div>
  );
}
