import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCommittenti, getCoordinatori, checkObbligatorieta, generaDocumento } from '../utils/api';
import { useNotify } from '../App';
import Field from './Field';

const STEPS = ['Verifica', 'Cantiere', 'Committente', 'Coordinatori', 'Genera'];

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

export default function WizardNotifica() {
  const [step, setStep]           = useState(0);
  const [form, setForm]           = useState({ rischi_allegato_xi: false });
  const [checkResult, setCheckResult] = useState(null);
  const [committenti, setCommittenti] = useState([]);
  const [coordinatori, setCoordinatori] = useState([]);
  const [loading, setLoading]     = useState(false);
  const [docId, setDocId]         = useState(null);
  const notify = useNotify();
  const nav    = useNavigate();

  useEffect(() => {
    getCommittenti().then(r => setCommittenti(r.data)).catch(() => {});
    getCoordinatori().then(r => setCoordinatori(r.data)).catch(() => {});
  }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const handleVerifica = async () => {
    setLoading(true);
    try {
      const res = await checkObbligatorieta({
        document_type:    'notifica_preliminare',
        uomini_giorno:    parseInt(form.uomini_giorno) || 0,
        max_lavoratori:   parseInt(form.max_lavoratori) || 0,
        rischi_allegato_xi: form.rischi_allegato_xi,
      });
      setCheckResult(res.data);
      setStep(1);
    } catch { notify('Errore nella verifica', 'error'); }
    finally   { setLoading(false); }
  };

  const loadCommittente = (id) => {
    const c = committenti.find(x => x.id === parseInt(id));
    if (!c) return;
    setForm(f => ({ ...f,
      committente_tipo:             c.tipo,
      committente_nome:             c.nome,
      committente_cognome:          c.cognome,
      committente_ragione_sociale:  c.ragione_sociale,
      committente_cf:               c.codice_fiscale,
      committente_piva:             c.piva,
      committente_indirizzo:        c.indirizzo,
      committente_citta:            c.citta,
      committente_telefono:         c.telefono,
      committente_email:            c.email,
    }));
  };

  const loadCoord = (id, ruolo) => {
    const c = coordinatori.find(x => x.id === parseInt(id));
    if (!c) return;
    const p = ruolo === 'csp' ? 'csp_' : 'cse_';
    setForm(f => ({ ...f,
      [`${p}nome`]:         c.nome,
      [`${p}cognome`]:      c.cognome,
      [`${p}ordine`]:       c.ordine_professionale,
      [`${p}numero_ordine`]: c.numero_ordine,
      [`${p}telefono`]:     c.telefono,
      [`${p}pec`]:          c.pec,
    }));
  };

  const handleGenera = async () => {
    setLoading(true);
    try {
      const res = await generaDocumento({
        tipo_documento: 'notifica_preliminare',
        form_data:      form,
        nome_cantiere:  form.citta_cantiere || 'Cantiere',
      });
      setDocId(res.data.doc_id);
      setStep(5);
      notify('Notifica Preliminare generata! ✓', 'success');
    } catch (e) {
      notify('Errore: ' + (e.response?.data?.detail || e.message), 'error');
    } finally { setLoading(false); }
  };

  

  return (
    <div>
      <div className="page-header">
        <h1>📋 Notifica Preliminare</h1>
        <p>Art. 99 — D.Lgs. 81/2008 — Allegato XII</p>
      </div>
      <div style={{ maxWidth: 820 }}>
        <StepBar step={step} steps={STEPS} />
        <div className="wizard-body">

          {/* STEP 0 – Verifica */}
          {step === 0 && (
            <>
              <div className="wizard-title">Verifica obbligatorietà</div>
              <div className="info-box">
                La Notifica è obbligatoria se: durata &gt; 200 uomini-giorno,
                oppure &gt; 20 lavoratori contemporanei, oppure lavori con rischi Allegato XI.
              </div>
              <div className="form-grid">
                <Field form={form} set={set} label="Durata prevista (uomini-giorno)" field="uomini_giorno" type="number"
                   hint="Somma: n. lavoratori × giorni per ogni fase" placeholder="es. 250" />
                <Field form={form} set={set} label="Max lavoratori contemporanei" field="max_lavoratori" type="number" placeholder="es. 15" />
              </div>
              <div className="form-group">
                <label className="form-label">Sono previsti lavori con rischi Allegato XI?</label>
                <div style={{ display: 'flex', gap: 20, marginTop: 8 }}>
                  {[
                    { v: false, l: 'No — nessun rischio speciale' },
                    { v: true,  l: 'Sì — scavi profondi, amianto, esplosivi...' },
                  ].map(o => (
                    <label key={String(o.v)} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.875rem' }}>
                      <input type="radio" name="rax"
                        checked={form.rischi_allegato_xi === o.v}
                        onChange={() => set('rischi_allegato_xi', o.v)} />
                      {o.l}
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

          {/* STEP 1 – Cantiere */}
          {step === 1 && (
            <>
              <div className="wizard-title">Dati del cantiere</div>
              {checkResult && (
                <div className={checkResult.obbligatorio ? 'info-box' : 'warn-box'} style={{ marginBottom: 20 }}>
                  <strong>{checkResult.obbligatorio ? '✅ OBBLIGATORIA' : '⚠️ Non obbligatoria'}</strong>
                  {' — '}{checkResult.motivazioni?.join('; ')}
                  {checkResult.riferimenti_normativi?.length > 0 && (
                    <div style={{ fontSize: '0.75rem', marginTop: 4, opacity: .8 }}>
                      {checkResult.riferimenti_normativi.join(', ')}
                    </div>
                  )}
                </div>
              )}
              <div className="form-grid">
                <Field form={form} set={set} label="Indirizzo cantiere" field="indirizzo_cantiere" />
                <Field form={form} set={set} label="Comune"             field="citta_cantiere" />
                <Field form={form} set={set} label="Provincia"          field="provincia_cantiere" placeholder="es. MI" />
                <Field form={form} set={set} label="CAP"                field="cap_cantiere" />
              </div>
              <div className="form-group">
                <label className="form-label">Natura dell'opera</label>
                <select className="form-control" value={form.natura_opera || ''}
                  onChange={e => set('natura_opera', e.target.value)}>
                  <option value="">Seleziona...</option>
                  {['Nuova costruzione residenziale','Nuova costruzione commerciale/industriale',
                    'Ristrutturazione edilizia','Manutenzione straordinaria',
                    'Opere di urbanizzazione','Opere stradali','Demolizione'].map(o => <option key={o}>{o}</option>)}
                </select>
              </div>
              <Field form={form} set={set} label="Descrizione sommaria" field="descrizione_opera" type="textarea" />
              <div className="form-grid">
                <Field form={form} set={set} label="Data inizio lavori"  field="data_inizio"        type="date" />
                <Field form={form} set={set} label="Durata prevista"     field="durata_lavori"      placeholder="es. 6 mesi" />
                <Field form={form} set={set} label="ASL destinataria"    field="asl_destinataria"   placeholder="ASL di..." />
                <Field form={form} set={set} label="ITL destinatario"    field="itl_destinatario"   placeholder="ITL di..." />
              </div>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(0)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(2)}>Avanti →</button>
              </div>
            </>
          )}

          {/* STEP 2 – Committente */}
          {step === 2 && (
            <>
              <div className="wizard-title">Committente</div>
              {committenti.length > 0 && (
                <div className="form-group">
                  <label className="form-label">📁 Carica da anagrafica</label>
                  <select className="form-control" defaultValue=""
                    onChange={e => loadCommittente(e.target.value)}>
                    <option value="">— Seleziona committente esistente —</option>
                    {committenti.map(c => (
                      <option key={c.id} value={c.id}>
                        {c.tipo === 'persona_giuridica' ? c.ragione_sociale : `${c.nome || ''} ${c.cognome || ''}`}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="form-group">
                <label className="form-label">Tipo committente</label>
                <div style={{ display: 'flex', gap: 20, marginTop: 8 }}>
                  {['persona_fisica','persona_giuridica'].map(t => (
                    <label key={t} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: '0.875rem' }}>
                      <input type="radio" name="ctipo"
                        checked={form.committente_tipo === t}
                        onChange={() => set('committente_tipo', t)} />
                      {t === 'persona_fisica' ? 'Persona Fisica' : 'Persona Giuridica'}
                    </label>
                  ))}
                </div>
              </div>
              <div className="form-grid">
                {form.committente_tipo === 'persona_giuridica' && (
                  <Field form={form} set={set} label="Ragione Sociale" field="committente_ragione_sociale" />
                )}
                <Field form={form} set={set} label="Nome"        field="committente_nome" />
                <Field form={form} set={set} label="Cognome"     field="committente_cognome" />
                <Field form={form} set={set} label="Codice Fiscale" field="committente_cf" />
                <Field form={form} set={set} label="Indirizzo"   field="committente_indirizzo" />
                <Field form={form} set={set} label="Città"       field="committente_citta" />
                <Field form={form} set={set} label="Telefono"    field="committente_telefono" />
                <Field form={form} set={set} label="Email / PEC" field="committente_email" />
              </div>
              <div className="section-divider" style={{ marginTop: 20 }}>Responsabile dei Lavori (se diverso)</div>
              <div className="form-grid">
                <Field form={form} set={set} label="Nome RL"    field="rl_nome" />
                <Field form={form} set={set} label="Cognome RL" field="rl_cognome" />
                <Field form={form} set={set} label="Qualifica"  field="rl_qualifica" placeholder="es. Direttore Lavori" />
                <Field form={form} set={set} label="Telefono RL" field="rl_telefono" />
              </div>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(1)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(3)}>Avanti →</button>
              </div>
            </>
          )}

          {/* STEP 3 – Coordinatori */}
          {step === 3 && (
            <>
              <div className="wizard-title">Coordinatori per la Sicurezza</div>
              {['csp','cse'].map(ruolo => (
                <div key={ruolo}>
                  <div className="section-divider">
                    {ruolo === 'csp' ? '🔵 CSP — Coordinatore per la Progettazione' : '🟢 CSE — Coordinatore per l\'Esecuzione'}
                  </div>
                  {coordinatori.length > 0 && (
                    <div className="form-group">
                      <label className="form-label">📁 Carica da anagrafica</label>
                      <select className="form-control" defaultValue=""
                        onChange={e => loadCoord(e.target.value, ruolo)}>
                        <option value="">— Seleziona coordinatore —</option>
                        {coordinatori.map(c => <option key={c.id} value={c.id}>{c.cognome} {c.nome}</option>)}
                      </select>
                    </div>
                  )}
                  <div className="form-grid">
                    <Field form={form} set={set} label="Nome"              field={`${ruolo}_nome`} />
                    <Field form={form} set={set} label="Cognome"           field={`${ruolo}_cognome`} />
                    <Field form={form} set={set} label="Ordine Professionale" field={`${ruolo}_ordine`} />
                    <Field form={form} set={set} label="N. Iscrizione"     field={`${ruolo}_numero_ordine`} />
                    <Field form={form} set={set} label="Telefono"          field={`${ruolo}_telefono`} />
                    <Field form={form} set={set} label="PEC"               field={`${ruolo}_pec`} />
                  </div>
                </div>
              ))}
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(2)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(4)}>Avanti →</button>
              </div>
            </>
          )}

          {/* STEP 4 – Genera */}
          {step === 4 && (
            <>
              <div className="wizard-title">Genera documento</div>
              <div style={{ background: '#F8F5F0', borderRadius: 8, padding: 20, marginBottom: 20, fontSize: '0.875rem' }}>
                <div style={{ fontWeight: 600, color: '#1A3A5C', marginBottom: 12 }}>Riepilogo dati</div>
                {[
                  ['Cantiere',    `${form.indirizzo_cantiere || ''}, ${form.citta_cantiere || ''} (${form.provincia_cantiere || ''})`],
                  ['Natura',      form.natura_opera],
                  ['Inizio',      form.data_inizio],
                  ['Committente', `${form.committente_nome || ''} ${form.committente_cognome || ''} ${form.committente_ragione_sociale || ''}`],
                  ['CSP',         `${form.csp_nome || ''} ${form.csp_cognome || ''}`],
                  ['CSE',         `${form.cse_nome || ''} ${form.cse_cognome || ''}`],
                ].map(([k, v]) => v?.trim() && (
                  <div key={k} style={{ display: 'flex', gap: 12, marginBottom: 4 }}>
                    <span style={{ color: '#8A9BB0', minWidth: 100 }}>{k}:</span>
                    <span>{v}</span>
                  </div>
                ))}
              </div>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(3)}>← Indietro</button>
                <button className="btn btn-gold" onClick={handleGenera} disabled={loading}>
                  {loading ? '⏳ Generazione in corso...' : '📄 Genera Notifica Preliminare'}
                </button>
              </div>
            </>
          )}

          {/* STEP 5 – Successo */}
          {step === 5 && (
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{ fontSize: '3rem', marginBottom: 16 }}>✅</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#1A3A5C', marginBottom: 8 }}>
                Notifica Preliminare generata!
              </div>
              <p style={{ color: '#5A6B7D', marginBottom: 24 }}>
                Il documento DOCX è pronto. Verificalo e firmalo prima dell'invio ad ASL e ITL.
              </p>
              {docId && (
                <a href={`/api/documents/download/${docId}`} className="btn btn-gold"
                   download style={{ fontSize: '1rem', padding: '12px 28px' }}>
                  ↓ Scarica DOCX
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