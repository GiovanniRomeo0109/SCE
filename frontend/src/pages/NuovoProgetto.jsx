import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { estraiDati } from '../utils/api';
import { useNotify } from '../App';
import ReviewDati from '../components/ReviewDati';

const TIPI = [
  {
    id: 'notifica_preliminare', path: '/nuovo/notifica',
    icon: '📋', titolo: 'Notifica Preliminare', norma: 'Art. 99 — D.Lgs. 81/2008',
    desc: 'Da inviare ad ASL e ITL prima dell\'inizio lavori',
    suggeriti: [
      { nome: 'Contratto d\'appalto', desc: 'Committente, impresa, opera, importo, date', icona: '📄' },
      { nome: 'Documento identità committente', desc: 'Codice fiscale, dati anagrafici', icona: '🪪' },
      { nome: 'Relazione tecnica / progetto', desc: 'Natura opera, descrizione, cantiere', icona: '📐' },
    ]
  },
  {
    id: 'psc', path: '/nuovo/psc',
    icon: '📗', titolo: 'Piano di Sicurezza e Coordinamento', norma: 'Art. 100 — D.Lgs. 81/2008',
    desc: 'Obbligatorio con più imprese in cantiere',
    suggeriti: [
      { nome: 'Contratto d\'appalto', desc: 'Committente, imprese, importo, date lavori', icona: '📄' },
      { nome: 'Visura camerale impresa', desc: 'Ragione sociale, PIVA, DL, sede legale', icona: '🏢' },
      { nome: 'Progetto architettonico', desc: 'Natura opera, lavorazioni, dati cantiere', icona: '📐' },
      { nome: 'Computo metrico / capitolato', desc: 'Lavorazioni specifiche, importi sicurezza', icona: '📊' },
    ]
  },
  {
    id: 'pos', path: '/nuovo/pos',
    icon: '📘', titolo: 'Piano Operativo di Sicurezza', norma: 'Art. 101 — D.Lgs. 81/2008',
    desc: 'Obbligatorio per ogni impresa esecutrice',
    suggeriti: [
      { nome: 'Visura camerale impresa', desc: 'Ragione sociale, PIVA, DL, RSPP, sede', icona: '🏢' },
      { nome: 'Contratto d\'appalto / subappalto', desc: 'Attività in cantiere, periodo, importo', icona: '📄' },
      { nome: 'Nomina RSPP / MC', desc: 'Figure della sicurezza con dati completi', icona: '👷' },
    ]
  }
];

const STEPS = ['Tipo documento', 'Carica documenti', 'Analisi AI', 'Revisione dati'];

function StepBar({ step }) {
  return (
    <div className="wizard-steps" style={{ marginBottom: 32 }}>
      {STEPS.map((s, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', flex: i < STEPS.length - 1 ? 1 : 0 }}>
          <div className={`wizard-step ${i === step ? 'active' : i < step ? 'done' : ''}`}>
            <div className="step-num">{i < step ? '✓' : i + 1}</div>
            <div className="step-label">{s}</div>
          </div>
          {i < STEPS.length - 1 && <div className={`wizard-divider ${i < step ? 'done' : ''}`} />}
        </div>
      ))}
    </div>
  );
}

export default function NuovoProgetto() {
  const [step, setStep]             = useState(0);
  const [tipoId, setTipoId]         = useState(null);
  const [files, setFiles]           = useState([]);
  const [dragging, setDragging]     = useState(false);
  const [loading, setLoading]       = useState(false);
  const [risultato, setRisultato]   = useState(null);
  const [datiFinali, setDatiFinali] = useState({});
  const [risolti, setRisolti]       = useState({});
  const notify = useNotify();
  const nav = useNavigate();

  const tipo = TIPI.find(t => t.id === tipoId);

  const addFiles = (fileList) => {
    const accettati = Array.from(fileList).filter(f => {
      const ext = f.name.toLowerCase().split('.').pop();
      return ['pdf', 'docx', 'xlsx', 'xls', 'jpg', 'jpeg', 'png'].includes(ext);
    });
    const dwg = Array.from(fileList).filter(f => f.name.toLowerCase().endsWith('.dwg'));
    if (dwg.length > 0) {
      notify(`File DWG non supportati. Esporta come PDF da AutoCAD: ${dwg.map(f => f.name).join(', ')}`, 'error');
    }
    setFiles(prev => {
      const nomi = new Set(prev.map(f => f.name));
      return [...prev, ...accettati.filter(f => !nomi.has(f.name))];
    });
  };

  const removeFile = (nome) => setFiles(prev => prev.filter(f => f.name !== nome));

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    addFiles(e.dataTransfer.files);
  };

  const handleAnalizza = async () => {
    setLoading(true);
    setStep(2);
    try {
      const fd = new FormData();
      files.forEach(f => fd.append('files', f));
      const res = await estraiDati(fd);
      setRisultato(res.data);

      // Costruisci mappa piatta field→valore dai dati estratti
      const df = {};
      Object.values(res.data.dati).forEach(campi => {
        Object.entries(campi).forEach(([k, info]) => {
          if (info.valore) df[k] = info.valore;
        });
      });
      setDatiFinali(df);
      setStep(3);
    } catch (e) {
      notify('Errore durante l\'analisi: ' + (e.response?.data?.detail || e.message), 'error');
      setStep(1);
    } finally {
      setLoading(false);
    }
  };

  const risolviConflitto = (campo, valore) => {
    const chiave = campo.split('.')[1];
    setRisolti(prev => ({ ...prev, [campo]: valore }));
    setDatiFinali(prev => ({ ...prev, [chiave]: valore }));
  };

  const handleProcedi = () => {
    // Applica i conflitti non ancora risolti: usa valore_a come default
    const datiFiniti = { ...datiFinali };
    risultato?.conflitti?.forEach(c => {
      if (!risolti[c.campo]) {
        const chiave = c.campo.split('.')[1];
        datiFiniti[chiave] = c.valore_a;
      }
    });
    nav(tipo.path, { state: { initialData: datiFiniti } });
  };

  const fileIcon = (nome) => {
    const ext = nome.toLowerCase().split('.').pop();
    if (ext === 'pdf')   return '📕';
    if (ext === 'docx')  return '📘';
    if (['xlsx','xls'].includes(ext)) return '📗';
    return '🖼️';
  };

  return (
    <div>
      <div className="page-header">
        <h1>🤖 Nuovo Progetto con AI</h1>
        <p>Carica i documenti che hai — l'agente estrae automaticamente tutti i dati e pre-compila il modulo</p>
      </div>

      <StepBar step={step} />

      {/* ── STEP 0: Scelta tipo documento ── */}
      {step === 0 && (
        <>
          <div className="info-box" style={{ marginBottom: 24 }}>
            💡 Seleziona il tipo di documento. Nel passo successivo potrai caricare
            i documenti già in tuo possesso — l'AI estrarrà tutti i dati automaticamente.
          </div>
          <div className="doc-types">
            {TIPI.map(t => (
              <div key={t.id} className="doc-type-card"
                onClick={() => { setTipoId(t.id); setStep(1); }}>
                <div className="doc-icon">{t.icon}</div>
                <h3>{t.titolo}</h3>
                <p style={{ fontSize: '0.7rem', color: '#C88B2A', fontWeight: 600, marginBottom: 8 }}>{t.norma}</p>
                <p>{t.desc}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── STEP 1: Upload documenti ── */}
      {step === 1 && tipo && (
        <div style={{ maxWidth: 800 }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28, alignItems: 'start' }}>

            {/* Upload area */}
            <div>
              <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 12 }}>
                📎 Carica i documenti
              </div>
              <div
                onDragOver={e => { e.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={handleDrop}
                onClick={() => document.getElementById('fi').click()}
                style={{
                  border: `2px dashed ${dragging ? '#1A3A5C' : '#C88B2A'}`,
                  borderRadius: 12, padding: '36px 20px', textAlign: 'center',
                  cursor: 'pointer', background: dragging ? '#EEF4FA' : '#FFFDF9',
                  transition: 'all .2s', marginBottom: 16,
                }}>
                <div style={{ fontSize: '2.8rem', marginBottom: 8 }}>📂</div>
                <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 4 }}>
                  Trascina i file qui
                </div>
                <div style={{ fontSize: '0.78rem', color: '#8A9BB0' }}>
                  o clicca per selezionare
                </div>
                <div style={{ fontSize: '0.7rem', color: '#8A9BB0', marginTop: 8 }}>
                  PDF · Word · Excel · JPG · PNG
                </div>
              </div>
              <input id="fi" type="file" multiple
                accept=".pdf,.docx,.xlsx,.xls,.jpg,.jpeg,.png"
                style={{ display: 'none' }}
                onChange={e => addFiles(e.target.files)} />

              {files.length > 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {files.map(f => (
                    <div key={f.name} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '8px 12px', background: '#F8F5F0',
                      borderRadius: 6, border: '1px solid var(--border)'
                    }}>
                      <span style={{ fontSize: '1.2rem' }}>{fileIcon(f.name)}</span>
                      <span style={{ flex: 1, fontSize: '0.82rem', color: '#2C3E50', wordBreak: 'break-all' }}>
                        {f.name}
                      </span>
                      <span style={{ fontSize: '0.7rem', color: '#8A9BB0', whiteSpace: 'nowrap' }}>
                        {(f.size / 1024).toFixed(0)} KB
                      </span>
                      <button onClick={e => { e.stopPropagation(); removeFile(f.name); }}
                        style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#C0392B', fontSize: '1.1rem', lineHeight: 1 }}>
                        ✕
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Documenti suggeriti */}
            <div>
              <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 12 }}>
                💡 Documenti consigliati per {tipo.icon} {tipo.titolo}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                {tipo.suggeriti.map(d => (
                  <div key={d.nome} style={{
                    padding: '12px 14px', background: 'white',
                    borderRadius: 8, border: '1.5px solid var(--border)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
                      <span>{d.icona}</span>
                      <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#1A3A5C' }}>{d.nome}</span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: '#8A9BB0', paddingLeft: 26 }}>{d.desc}</div>
                  </div>
                ))}
              </div>
              <div className="warn-box" style={{ fontSize: '0.78rem' }}>
                ⚠️ File DWG non supportati direttamente.<br />
                Esporta come PDF da AutoCAD prima di caricare.
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 28 }}>
            <button className="btn btn-ghost" onClick={() => setStep(0)}>← Indietro</button>
            <div style={{ display: 'flex', gap: 12 }}>
              <button className="btn btn-ghost"
                onClick={() => nav(tipo.path, { state: { initialData: {} } })}>
                Salta — compila manualmente
              </button>
              <button className="btn btn-gold" onClick={handleAnalizza} disabled={files.length === 0}>
                🤖 Analizza con AI →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── STEP 2: Loading ── */}
      {step === 2 && (
        <div style={{ textAlign: 'center', padding: '80px 20px' }}>
          <div style={{ fontSize: '3.5rem', marginBottom: 20 }}>🤖</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700, color: '#1A3A5C', marginBottom: 8 }}>
            Analisi in corso...
          </div>
          <p style={{ color: '#5A6B7D', marginBottom: 36 }}>
            Claude sta leggendo i tuoi documenti ed estraendo tutti i dati. Attendere.
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 10 }}>
            {[0, 1, 2].map(i => (
              <div key={i} style={{
                width: 12, height: 12, borderRadius: '50%', background: '#C88B2A',
                animation: `dot 1.4s ease-in-out ${i * 0.25}s infinite`
              }} />
            ))}
          </div>
          <style>{`@keyframes dot{0%,80%,100%{opacity:.2;transform:scale(.8)}40%{opacity:1;transform:scale(1.2)}}`}</style>
        </div>
      )}

      {/* ── STEP 3: Revisione dati ── */}
      {step === 3 && risultato && (
        <ReviewDati
          risultato={risultato}
          datiFinali={datiFinali}
          risolti={risolti}
          onRisolvi={risolviConflitto}
          onProcedi={handleProcedi}
          onBack={() => setStep(1)}
          tipoDoc={tipo?.titolo}
        />
      )}
    </div>
  );
}