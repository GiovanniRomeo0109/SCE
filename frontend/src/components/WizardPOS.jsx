import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';   // ← aggiungi useLocation
import { useNavigate } from 'react-router-dom';
import { getImprese, checkObbligatorieta, generaDocumento, generaContenutoAI } from '../utils/api';
import { useNotify } from '../App';
import Field from './Field';

const STEPS = ['Verifica', 'Impresa', 'Cantiere', 'Lavoratori', 'Rischi', 'Genera'];

function StepBar({ step, steps }) {
  return (
    <div className="wizard-steps">
      {steps.map((s, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', flex: i < steps.length - 1 ? 1 : 0 }}>
          <div className={`wizard-step ${i === step ? 'active' : i < step ? 'done' : ''}`}>
            <div className="step-num">{i < step ? '✓' : i + 1}</div>
            <div className="step-label">{s}</div>
          </div>
          {i < steps.length - 1 && <div className={`wizard-divider ${i < step ? 'done' : ''}`} />}
        </div>
      ))}
    </div>
  );
}

export default function WizardPOS() {
  const location    = useLocation();                                        // ← NUOVO
  const initialData = location.state?.initialData || {};                   // ← NUOVO

  const [step, setStep] = useState(0);
  const [form, setForm] = useState({ tipo_soggetto: 'impresa_esecutrice', ...initialData }); // ← modifica
  const [checkResult, setCheckResult] = useState(null);
  const [imprese, setImprese]         = useState([]);
  const [loading, setLoading]         = useState(false);
  const [docId, setDocId]             = useState(null);
  const notify = useNotify();
  const nav    = useNavigate();

  useEffect(() => {
    getImprese().then(r => setImprese(r.data)).catch(() => {});
  }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  

  const handleVerifica = async () => {
    setLoading(true);
    try {
      const res = await checkObbligatorieta({
        document_type: 'pos',
        tipo_soggetto: form.tipo_soggetto,
      });
      setCheckResult(res.data);
      setStep(1);
    } catch { notify('Errore nella verifica', 'error'); }
    finally   { setLoading(false); }
  };

  const loadImpresa = (id) => {
    const imp = imprese.find(x => x.id === parseInt(id));
    if (!imp) return;
    setForm(f => ({ ...f,
      impresa_ragione_sociale: imp.ragione_sociale,
      impresa_cf:              imp.codice_fiscale,
      impresa_piva:            imp.piva,
      impresa_indirizzo:       imp.indirizzo,
      impresa_citta:           imp.citta,
      impresa_provincia:       imp.provincia,
      impresa_telefono:        imp.telefono,
      impresa_email:           imp.email,
      impresa_cciaa:           imp.cciaa,
      impresa_numero_cciaa:    imp.numero_cciaa,
      impresa_inail_pat:       imp.inail_pat,
      impresa_cassa_edile:     imp.cassa_edile,
      impresa_ccnl:            imp.ccnl,
      nome_dl:                 imp.nome_dl,
      cognome_dl:              imp.cognome_dl,
      nome_rspp:               imp.nome_rspp,
      cognome_rspp:            imp.cognome_rspp,
      nome_mc:                 imp.nome_mc,
      cognome_mc:              imp.cognome_mc,
      nome_rls:                imp.nome_rls,
      cognome_rls:             imp.cognome_rls,
    }));
  };

  const handleGenera = async () => {
    setLoading(true);
    try {
      let contenutoAI = null;
      try {
        const aiRes = await generaContenutoAI({ tipo_documento: 'pos', form_data: form });
        contenutoAI = aiRes.data.contenuto;
      } catch {}
      const res = await generaDocumento({
        tipo_documento: 'pos',
        form_data:      form,
        contenuto_ai:   contenutoAI,
        nome_cantiere:  form.citta_cantiere || 'Cantiere',
        impresa_nome:   form.impresa_ragione_sociale || '',
      });
      setDocId(res.data.doc_id);
      setStep(6);
      notify('POS generato! ✓', 'success');
    } catch (e) {
      notify('Errore: ' + (e.response?.data?.detail || e.message), 'error');
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div className="page-header">
        <h1>📘 Piano Operativo di Sicurezza</h1>
        <p>Art. 101 — D.Lgs. 81/2008 — Allegato XV punto 3</p>
      </div>
      <div style={{ maxWidth: 820 }}>
        <StepBar step={step} steps={STEPS} />
        <div className="wizard-body">

          {step === 0 && (
            <>
              <div className="wizard-title">Verifica obbligatorietà POS</div>
              <div className="info-box">
                Il POS è obbligatorio per ogni <strong>impresa esecutrice</strong>, indipendentemente
                dal numero di lavoratori o dalla dimensione del cantiere (Art. 101 D.Lgs. 81/2008).
              </div>
              <div className="form-group">
                <label className="form-label">Tipo di soggetto</label>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 10 }}>
                  {[
                    { v: 'impresa_esecutrice',   l: 'Impresa esecutrice',                   desc: 'Ha dipendenti o collaboratori — POS obbligatorio' },
                    { v: 'lavoratore_autonomo',  l: 'Lavoratore autonomo (senza dipendenti)', desc: 'Non obbligatorio, ma deve rispettare il PSC' },
                  ].map(o => (
                    <label key={o.v} style={{
                      display: 'flex', alignItems: 'flex-start', gap: 12, cursor: 'pointer',
                      padding: '14px 16px', borderRadius: 8, border: '1.5px solid',
                      borderColor: form.tipo_soggetto === o.v ? '#1A3A5C' : 'var(--border)',
                      background:  form.tipo_soggetto === o.v ? '#EEF4FA' : 'white',
                    }}>
                      <input type="radio" name="tipo_soggetto" style={{ marginTop: 3 }}
                        checked={form.tipo_soggetto === o.v}
                        onChange={() => set('tipo_soggetto', o.v)} />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.9rem', color: '#1A3A5C' }}>{o.l}</div>
                        <div style={{ fontSize: '0.78rem', color: '#5A6B7D', marginTop: 2 }}>{o.desc}</div>
                      </div>
                    </label>
                  ))}
                </div>
              </div>
              <div className="wizard-nav">
                <span />
                <button className="btn btn-primary" onClick={handleVerifica} disabled={loading}>
                  {loading ? '⏳...' : '🔍 Verifica obbligatorietà →'}
                </button>
              </div>
            </>
          )}

          {step === 1 && (
            <>
              <div className="wizard-title">Dati dell'impresa esecutrice</div>
              {checkResult && (
                <div className={checkResult.obbligatorio ? 'info-box' : 'warn-box'} style={{ marginBottom: 20 }}>
                  <strong>{checkResult.obbligatorio ? '✅ POS OBBLIGATORIO' : '⚠️ POS non obbligatorio'}</strong>
                  {' — '}{checkResult.motivazioni?.join('; ')}
                  {checkResult.avvertenze?.length > 0 && <div style={{ fontSize: '0.75rem', marginTop: 4 }}>{checkResult.avvertenze[0]}</div>}
                </div>
              )}
              {imprese.length > 0 && (
                <div className="form-group">
                  <label className="form-label">📁 Carica da anagrafica imprese</label>
                  <select className="form-control" defaultValue="" onChange={e => loadImpresa(e.target.value)}>
                    <option value="">— Seleziona impresa esistente —</option>
                    {imprese.map(i => <option key={i.id} value={i.id}>{i.ragione_sociale}</option>)}
                  </select>
                </div>
              )}
              <div className="section-divider">Dati societari</div>
              <div className="form-grid">
                <Field form={form} set={set} label="Ragione Sociale"       field="impresa_ragione_sociale" />
                <Field form={form} set={set} label="P.IVA"                 field="impresa_piva" />
                <Field form={form} set={set} label="Codice Fiscale"         field="impresa_cf" />
                <Field form={form} set={set} label="Sede legale"            field="impresa_indirizzo" />
                <Field form={form} set={set} label="Città"                  field="impresa_citta" />
                <Field form={form} set={set} label="Provincia"              field="impresa_provincia" placeholder="es. MI" />
                <Field form={form} set={set} label="Telefono"               field="impresa_telefono" />
                <Field form={form} set={set} label="Email / PEC"            field="impresa_email" />
                <Field form={form} set={set} label="CCIAA"                  field="impresa_cciaa" />
                <Field form={form} set={set} label="Posizione INAIL (PAT)"  field="impresa_inail_pat" />
              </div>
              <div className="form-group">
                <label className="form-label">CCNL applicato</label>
                <select className="form-control" value={form.impresa_ccnl || 'CCNL Edilizia Industria'}
                  onChange={e => set('impresa_ccnl', e.target.value)}>
                  <option>CCNL Edilizia Industria</option>
                  <option>CCNL Edilizia Artigianato</option>
                  <option>CCNL Edilizia Cooperazione</option>
                  <option>CCNL Metalmeccanico</option>
                </select>
              </div>
              <div className="section-divider">Figure della sicurezza</div>
              <div className="form-grid">
                <Field form={form} set={set} label="Nome Datore di Lavoro"      field="nome_dl" />
                <Field form={form} set={set} label="Cognome Datore di Lavoro"   field="cognome_dl" />
                <Field form={form} set={set} label="Nome RSPP"                  field="nome_rspp" />
                <Field form={form} set={set} label="Cognome RSPP"               field="cognome_rspp" />
                <Field form={form} set={set} label="Nome Medico Competente"      field="nome_mc" />
                <Field form={form} set={set} label="Cognome Medico Competente"   field="cognome_mc" />
                <Field form={form} set={set} label="Nome RLS / RLST"             field="nome_rls" />
                <Field form={form} set={set} label="Cognome RLS / RLST"          field="cognome_rls" />
                <Field form={form} set={set} label="Preposto di cantiere (Nome)" field="nome_preposto" />
                <Field form={form} set={set} label="Preposto di cantiere (Cognome)" field="cognome_preposto" />
              </div>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(0)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(2)}>Avanti →</button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <div className="wizard-title">Attività nel cantiere</div>
              <div className="form-grid">
                <Field form={form} set={set} label="Indirizzo cantiere" field="indirizzo_cantiere" />
                <Field form={form} set={set} label="Comune"             field="citta_cantiere" />
              </div>
              <Field form={form} set={set} label="Attività svolta dall'impresa nel cantiere" field="attivita_cantiere"
                 type="textarea" placeholder="es. Opere murarie, intonaci, pavimentazioni..." />
              <Field form={form} set={set} label="Fasi di lavoro proprie dell'impresa" field="fasi_proprie"
                 type="textarea" placeholder="es. Fase 1: fondazioni (sett-ott), Fase 2: elevazione (nov-gen)..." />
              <div className="form-grid">
                <Field form={form} set={set} label="Periodo di intervento"    field="periodo_intervento" placeholder="es. Settembre 2025 — Marzo 2026" />
                <Field form={form} set={set} label="N. lavoratori impiegati"  field="num_lavoratori" type="number" placeholder="es. 5" />
                <Field form={form} set={set} label="Addetto Primo Soccorso"   field="addetto_ps" />
                <Field form={form} set={set} label="Addetto Antincendio"      field="addetto_ai" />
                <Field form={form} set={set} label="Ospedale / PS più vicino" field="ospedale_vicino" />
              </div>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(1)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(3)}>Avanti →</button>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <div className="wizard-title">Lavoratori e formazione</div>
              <div className="info-box">
                Tutti i lavoratori devono aver completato la formazione obbligatoria
                (Accordo Stato-Regioni 21/12/2011 — settore edilizia: 4h + 12h).
              </div>
              <div className="form-group">
                <label className="form-label">Formazione completata dai lavoratori</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
                  {[
                    ['form_generale',  'Formazione generale (4h)'],
                    ['form_specifica', 'Formazione specifica alto rischio (12h)'],
                    ['form_ps',        'Primo soccorso (12h o 16h)'],
                    ['form_ai',        'Antincendio (4h o 8h)'],
                    ['form_quota',     'Lavori in quota'],
                    ['form_ponteggi',  'Montaggio ponteggi (PIMUS)'],
                    ['form_gru',       'Operatore gru'],
                    ['form_macchine',  'Patentino macchine movimento terra'],
                  ].map(([field, label]) => (
                    <label key={field} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem', cursor: 'pointer' }}>
                      <input type="checkbox" checked={!!form[field]} onChange={e => set(field, e.target.checked)} />
                      {label}
                    </label>
                  ))}
                </div>
              </div>
              <div className="section-divider">Macchine e attrezzature</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
                {[
                  ['att_betoniera',   'Betoniera'],
                  ['att_sega',        'Sega circolare'],
                  ['att_flex',        'Smerigliatrice (flex)'],
                  ['att_trapano',     'Trapano a percussione'],
                  ['att_ponteggio',   'Ponteggio metallico'],
                  ['att_trabattello', 'Trabattello'],
                  ['att_gru',         'Gru a torre'],
                  ['att_escavatore',  'Escavatore'],
                  ['att_compressore', 'Compressore'],
                  ['att_saldatrice',  'Saldatrice'],
                ].map(([field, label]) => (
                  <label key={field} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem', cursor: 'pointer' }}>
                    <input type="checkbox" checked={!!form[field]} onChange={e => set(field, e.target.checked)} />
                    {label}
                  </label>
                ))}
              </div>
              <Field form={form} set={set} label="Altre attrezzature" field="altre_attrezzature" placeholder="es. Fresa, Laser di livello..." />
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(2)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(4)}>Avanti →</button>
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <div className="wizard-title">Rischi specifici e DPI</div>
              <div className="form-group">
                <label className="form-label">Rischi principali per le lavorazioni dell'impresa</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 8 }}>
                  {[
                    ['r_caduta_alto',    'Caduta dall\'alto'],
                    ['r_investimento',   'Investimento mezzi meccanici'],
                    ['r_elettrico',      'Elettrocuzione'],
                    ['r_rumore',         'Rumore (Lex,8h > 80 dB)'],
                    ['r_polveri',        'Polveri / fibre'],
                    ['r_chimico',        'Agenti chimici (vernici, solventi)'],
                    ['r_movimentazione', 'Movimentazione manuale carichi'],
                    ['r_vibrazioni',     'Vibrazioni mano-braccio / corpo intero'],
                    ['r_scivolamento',   'Scivolamento / caduta stesso livello'],
                    ['r_calore',         'Stress termico (lavori estivi)'],
                  ].map(([field, label]) => (
                    <label key={field} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem', cursor: 'pointer' }}>
                      <input type="checkbox" checked={!!form[field]} onChange={e => set(field, e.target.checked)} />
                      {label}
                    </label>
                  ))}
                </div>
              </div>
              <Field form={form} set={set} label="Misure di prevenzione adottate" field="misure_prevenzione" type="textarea"
                 placeholder="es. Parapetti anticaduta, imbragature, quadri elettrici CEI, aspiratori polveri..." />
              <div className="section-divider">DPI previsti</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {[
                  ['dpi_casco',       'Casco EN 397 — sempre in cantiere'],
                  ['dpi_scarpe',      'Scarpe S3 EN ISO 20345 — sempre'],
                  ['dpi_guanti',      'Guanti EN 420 — durante lavorazioni'],
                  ['dpi_occhiali',    'Occhiali EN 166 — taglio, molatura'],
                  ['dpi_cuffie',      'Cuffie EN 352 — se rumore > 80 dB'],
                  ['dpi_maschere',    'Maschera FFP2/FFP3 — polveri, agenti chimici'],
                  ['dpi_gilet',       'Gilet EN ISO 20471 — lavori stradali'],
                  ['dpi_imbragatura', 'Imbragatura EN 361 — lavori in quota >2m'],
                ].map(([field, label]) => (
                  <label key={field} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem', cursor: 'pointer' }}>
                    <input type="checkbox" checked={!!form[field]} onChange={e => set(field, e.target.checked)} />
                    {label}
                  </label>
                ))}
              </div>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(3)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(5)}>Avanti →</button>
              </div>
            </>
          )}

          {step === 5 && (
            <>
              <div className="wizard-title">Genera POS</div>
              <div style={{ background: '#F8F5F0', borderRadius: 8, padding: 20, fontSize: '0.875rem', marginBottom: 20 }}>
                <div style={{ fontWeight: 600, color: '#1A3A5C', marginBottom: 10 }}>Riepilogo</div>
                {[
                  ['Impresa',        form.impresa_ragione_sociale],
                  ['P.IVA',          form.impresa_piva],
                  ['Datore Lavoro',  `${form.nome_dl || ''} ${form.cognome_dl || ''}`],
                  ['RSPP',           `${form.nome_rspp || ''} ${form.cognome_rspp || ''}`],
                  ['Cantiere',       `${form.indirizzo_cantiere || ''}, ${form.citta_cantiere || ''}`],
                  ['Attività',       form.attivita_cantiere],
                  ['Lavoratori',     form.num_lavoratori],
                ].map(([k, v]) => v && (
                  <div key={k} style={{ display: 'flex', gap: 12, marginBottom: 4 }}>
                    <span style={{ color: '#8A9BB0', minWidth: 110 }}>{k}:</span>
                    <span>{v}</span>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: '0.82rem', color: '#5A6B7D', marginBottom: 20 }}>
                L'AI genererà le sezioni narrative conformi all'Allegato XV punto 3.
              </p>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(4)}>← Indietro</button>
                <button className="btn btn-gold" onClick={handleGenera} disabled={loading}>
                  {loading ? '⏳ Generazione con AI in corso...' : '🤖 Genera POS con AI →'}
                </button>
              </div>
            </>
          )}

          {step === 6 && (
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{ fontSize: '3rem', marginBottom: 16 }}>📘</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#1A3A5C', marginBottom: 8 }}>POS Generato!</div>
              <p style={{ color: '#5A6B7D', marginBottom: 24, maxWidth: 460, margin: '0 auto 24px' }}>
                Fallo firmare dal Datore di Lavoro prima di consegnarlo al CSE.
              </p>
              {docId && (
                <a href={`/api/documents/download/${docId}`} className="btn btn-gold" download
                   style={{ fontSize: '1rem', padding: '12px 28px' }}>
                  ↓ Scarica POS in DOCX
                </a>
              )}
              <div style={{ marginTop: 20 }}>
                <button className="btn btn-ghost" onClick={() => nav('/storico')}>Vai allo Storico</button>
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}