import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';   // ← aggiungi useLocation

import { getCommittenti, getCoordinatori, getImprese, checkObbligatorieta, generaDocumento, generaContenutoAI } from '../utils/api';
import { useNotify } from '../App';
import Field from './Field';

const STEPS = ['Verifica', 'Cantiere', 'Soggetti', 'Imprese', 'Lavorazioni', 'Costi', 'Genera'];

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

export default function WizardPSC() {
  const location    = useLocation();                                        // ← NUOVO
  const initialData = location.state?.initialData || {};                   // ← NUOVO

  const [step, setStep]  = useState(0);
  const [form, setForm]  = useState({ ...initialData });                   // ← modifica
 
  const [checkResult, setCheckResult] = useState(null);
  const [impreseSel, setImpreseSel]   = useState([]);
  const [committenti, setCommittenti] = useState([]);
  const [coordinatori, setCoordinatori] = useState([]);
  const [imprese, setImprese]         = useState([]);
  const [loading, setLoading]         = useState(false);
  const [docId, setDocId]             = useState(null);
  const notify = useNotify();
  const nav    = useNavigate();

  useEffect(() => {
    getCommittenti().then(r => setCommittenti(r.data)).catch(() => {});
    getCoordinatori().then(r => setCoordinatori(r.data)).catch(() => {});
    getImprese().then(r => setImprese(r.data)).catch(() => {});
  }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
 

  const handleVerifica = async () => {
    setLoading(true);
    try {
      const res = await checkObbligatorieta({
        document_type: 'psc',
        num_imprese:   parseInt(form.num_imprese) || 1,
        uomini_giorno: parseInt(form.uomini_giorno) || 0,
      });
      setCheckResult(res.data);
      setStep(1);
    } catch { notify('Errore nella verifica', 'error'); }
    finally   { setLoading(false); }
  };

  const loadFromAnagrafica = (id, tipo) => {
    if (tipo === 'committente') {
      const c = committenti.find(x => x.id === parseInt(id));
      if (!c) return;
      setForm(f => ({ ...f,
        committente_tipo: c.tipo, committente_nome: c.nome, committente_cognome: c.cognome,
        committente_ragione_sociale: c.ragione_sociale, committente_cf: c.codice_fiscale,
        committente_piva: c.piva, committente_indirizzo: c.indirizzo,
        committente_citta: c.citta, committente_telefono: c.telefono, committente_email: c.email,
      }));
    }
    if (tipo === 'csp' || tipo === 'cse') {
      const c = coordinatori.find(x => x.id === parseInt(id));
      if (!c) return;
      const p = tipo === 'csp' ? 'csp_' : 'cse_';
      setForm(f => ({ ...f,
        [`${p}nome`]: c.nome, [`${p}cognome`]: c.cognome,
        [`${p}ordine`]: c.ordine_professionale, [`${p}numero_ordine`]: c.numero_ordine,
        [`${p}data_aggiornamento`]: c.data_aggiornamento, [`${p}pec`]: c.pec,
      }));
    }
  };

  const addImpresa = (id) => {
    const imp = imprese.find(x => x.id === parseInt(id));
    if (imp && !impreseSel.find(x => x.id === imp.id))
      setImpreseSel(prev => [...prev, { ...imp, attivita: '' }]);
  };

  const handleGenera = async () => {
    setLoading(true);
    try {
      const formData = { ...form, imprese_esecutrici: impreseSel };
      let contenutoAI = null;
      try {
        const aiRes = await generaContenutoAI({ tipo_documento: 'psc', form_data: formData });
        contenutoAI = aiRes.data.contenuto;
      } catch {}
      const res = await generaDocumento({
        tipo_documento: 'psc',
        form_data:      formData,
        contenuto_ai:   contenutoAI,
        nome_cantiere:  form.citta_cantiere || 'Cantiere',
      });
      setDocId(res.data.doc_id);
      setStep(7);
      notify('PSC generato! ✓', 'success');
    } catch (e) {
      notify('Errore: ' + (e.response?.data?.detail || e.message), 'error');
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div className="page-header">
        <h1>📗 Piano di Sicurezza e Coordinamento</h1>
        <p>Art. 100 — D.Lgs. 81/2008 — Allegato XV</p>
      </div>
      <div style={{ maxWidth: 860 }}>
        <StepBar step={step} steps={STEPS} />
        <div className="wizard-body">

          {step === 0 && (
            <>
              <div className="wizard-title">Verifica obbligatorietà PSC</div>
              <div className="info-box">Il PSC è obbligatorio quando operano più imprese esecutrici nel cantiere (anche non contemporaneamente).</div>
              <div className="form-grid">
                <Field form={form} set={set} label="N. imprese esecutrici previste" field="num_imprese" type="number"
                   hint="Includere subappaltatori e lavoratori autonomi con mezzi propri" placeholder="es. 3" />
                <Field form={form} set={set} label="Durata prevista (uomini-giorno)" field="uomini_giorno" type="number" placeholder="es. 400" />
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
              <div className="wizard-title">Dati del cantiere</div>
              {checkResult && (
                <div className={checkResult.obbligatorio ? 'info-box' : 'warn-box'} style={{ marginBottom: 16 }}>
                  <strong>{checkResult.obbligatorio ? '✅ PSC OBBLIGATORIO' : '⚠️ PSC non obbligatorio'}</strong>
                  {' — '}{checkResult.motivazioni?.join('; ')}
                  {checkResult.avvertenze?.length > 0 && <div style={{ fontSize: '0.75rem', marginTop: 4 }}>{checkResult.avvertenze[0]}</div>}
                </div>
              )}
              <div className="form-group">
                <label className="form-label">Natura dell'opera</label>
                <select className="form-control" value={form.natura_opera || ''}
                  onChange={e => set('natura_opera', e.target.value)}>
                  <option value="">Seleziona...</option>
                  {['Nuova costruzione residenziale','Nuova costruzione commerciale/industriale',
                    'Ristrutturazione edilizia','Manutenzione straordinaria','Demolizione','Opere stradali']
                    .map(o => <option key={o}>{o}</option>)}
                </select>
              </div>
              <Field form={form} set={set} label="Descrizione opera" field="descrizione_opera" type="textarea" />
              <div className="form-grid">
                <Field form={form} set={set} label="Indirizzo cantiere"             field="indirizzo_cantiere" />
                <Field form={form} set={set} label="Comune"                         field="citta_cantiere" />
                <Field form={form} set={set} label="Provincia"                      field="provincia_cantiere" placeholder="MI" />
                <Field form={form} set={set} label="Data inizio lavori"             field="data_inizio"      type="date" />
                <Field form={form} set={set} label="Data fine lavori"               field="data_fine"        type="date" />
                <Field form={form} set={set} label="Max lavoratori contemporanei"   field="max_lavoratori"   type="number" />
                <Field form={form} set={set} label="Importo lavori (€)"             field="importo_lavori"   type="number" />
              </div>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(0)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(2)}>Avanti →</button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <div className="wizard-title">Soggetti con compiti di sicurezza</div>
              <div className="section-divider">Committente</div>
              {committenti.length > 0 && (
                <div className="form-group">
                  <label className="form-label">📁 Carica da anagrafica</label>
                  <select className="form-control" defaultValue=""
                    onChange={e => loadFromAnagrafica(e.target.value, 'committente')}>
                    <option value="">— Seleziona —</option>
                    {committenti.map(c => (
                      <option key={c.id} value={c.id}>
                        {c.tipo === 'persona_giuridica' ? c.ragione_sociale : `${c.nome || ''} ${c.cognome || ''}`}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              <div className="form-grid">
                <Field form={form} set={set} label="Nome"            field="committente_nome" />
                <Field form={form} set={set} label="Cognome"         field="committente_cognome" />
                <Field form={form} set={set} label="Ragione Sociale" field="committente_ragione_sociale" />
                <Field form={form} set={set} label="Codice Fiscale"  field="committente_cf" />
                <Field form={form} set={set} label="Telefono"        field="committente_telefono" />
                <Field form={form} set={set} label="Email / PEC"     field="committente_email" />
              </div>
              {['csp','cse'].map(ruolo => (
                <div key={ruolo}>
                  <div className="section-divider">
                    {ruolo === 'csp' ? 'CSP — Coordinatore Progettazione' : 'CSE — Coordinatore Esecuzione'}
                  </div>
                  {coordinatori.length > 0 && (
                    <div className="form-group">
                      <label className="form-label">📁 Carica da anagrafica</label>
                      <select className="form-control" defaultValue=""
                        onChange={e => loadFromAnagrafica(e.target.value, ruolo)}>
                        <option value="">— Seleziona —</option>
                        {coordinatori.map(c => <option key={c.id} value={c.id}>{c.cognome} {c.nome}</option>)}
                      </select>
                    </div>
                  )}
                  <div className="form-grid">
                    <Field form={form} set={set} label="Nome"                 field={`${ruolo}_nome`} />
                    <Field form={form} set={set} label="Cognome"              field={`${ruolo}_cognome`} />
                    <Field form={form} set={set} label="Ordine Professionale" field={`${ruolo}_ordine`} />
                    <Field form={form} set={set} label="N. Iscrizione"        field={`${ruolo}_numero_ordine`} />
                    <Field form={form} set={set} label="Data aggiornamento"   field={`${ruolo}_data_aggiornamento`} type="date"
                       hint="Aggiornamento 40h ogni 5 anni" />
                    <Field form={form} set={set} label="PEC" field={`${ruolo}_pec`} />
                  </div>
                </div>
              ))}
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(1)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(3)}>Avanti →</button>
              </div>
            </>
          )}

          {step === 3 && (
            <>
              <div className="wizard-title">Imprese esecutrici</div>
              {imprese.length > 0 && (
                <div className="form-group">
                  <label className="form-label">📁 Aggiungi impresa da anagrafica</label>
                  <select className="form-control" defaultValue=""
                    onChange={e => { addImpresa(e.target.value); e.target.value = ''; }}>
                    <option value="">— Seleziona impresa da aggiungere —</option>
                    {imprese.map(i => <option key={i.id} value={i.id}>{i.ragione_sociale}</option>)}
                  </select>
                </div>
              )}
              {impreseSel.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {impreseSel.map(imp => (
                    <div key={imp.id} style={{ border: '1.5px solid var(--border)', borderRadius: 8, padding: 16 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                        <div>
                          <strong>{imp.ragione_sociale}</strong>
                          <span style={{ fontSize: '0.78rem', color: '#8A9BB0', marginLeft: 8 }}>P.IVA: {imp.piva}</span>
                        </div>
                        <button className="btn btn-danger btn-sm"
                          onClick={() => setImpreseSel(p => p.filter(x => x.id !== imp.id))}>
                          ✕ Rimuovi
                        </button>
                      </div>
                      <div className="form-group" style={{ margin: 0 }}>
                        <label className="form-label">Attività nel cantiere</label>
                        <input className="form-control"
                          placeholder="es. Strutture in c.a., murature..."
                          value={imp.attivita || ''}
                          onChange={e => setImpreseSel(p => p.map(x => x.id === imp.id ? { ...x, attivita: e.target.value } : x))} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state" style={{ padding: '32px 0' }}>
                  <div className="empty-icon">🏢</div>
                  <p>Nessuna impresa aggiunta. Selezionane una dall'anagrafica.</p>
                </div>
              )}
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(2)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(4)}>Avanti →</button>
              </div>
            </>
          )}

          {step === 4 && (
            <>
              <div className="wizard-title">Lavorazioni e rischi principali</div>
              <div className="info-box">Descrivi le lavorazioni. L'AI genererà le sezioni narrative di analisi dei rischi e misure di prevenzione.</div>
              <Field form={form} set={set} label="Principali fasi lavorative" field="fasi_descrizione" type="textarea"
                 placeholder="es. Demolizioni parziali, scavo fondazioni, struttura in c.a., murature, impianti, finiture..." />
              <Field form={form} set={set} label="Lavorazioni critiche / ad alto rischio" field="lavorazioni_critiche" type="textarea"
                 placeholder="es. Lavori in quota >2m, scavi >1.5m, demolizioni strutturali, vicinanza linee elettriche..." />
              <div className="form-grid">
                <div className="form-group">
                  <label className="form-label">Rischi Allegato XI presenti</label>
                  <select className="form-control" value={form.rischi_allegato_xi_desc || ''}
                    onChange={e => set('rischi_allegato_xi_desc', e.target.value)}>
                    <option value="">Nessuno specifico</option>
                    <option>Scavi profondi (&gt;5m)</option>
                    <option>Rischio amianto/fibre</option>
                    <option>Lavori in galleria</option>
                    <option>Uso di esplosivi</option>
                    <option>Linee elettriche aeree</option>
                  </select>
                </div>
                <Field form={form} set={set} label="ASL competente"          field="asl_destinataria"  placeholder="ASL di..." />
                <Field form={form} set={set} label="Ospedale / PS più vicino" field="ospedale_vicino" />
              </div>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(3)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(5)}>Avanti →</button>
              </div>
            </>
          )}

          {step === 5 && (
            <>
              <div className="wizard-title">Stima costi della sicurezza</div>
              <div className="warn-box">⚠ I costi della sicurezza NON sono soggetti a ribasso d'asta — Art. 100 co. 1, D.Lgs. 81/2008</div>
              <div className="form-grid">
                {[
                  ['Apprestamenti (ponteggi, trabattelli...)', 'costo_apprestamenti'],
                  ['Misure preventive, protettive e DPI',      'costo_dpi'],
                  ['Impianto di terra e prot. scariche',       'costo_impianti'],
                  ['Protezioni collettive',                    'costo_protezioni'],
                  ['Procedure per imprese speciali',           'costo_procedure'],
                  ['Presidi PS e antincendio',                 'costo_ps_ai'],
                  ['Cartellonistica di sicurezza',             'costo_cartelli'],
                ].map(([label, field]) => (
                  <Field key={field} form={form} set={set} label={`${label} (€)`} field={field} type="number" />
                ))}
                <div className="form-group" style={{ background: '#EEF4FA', padding: 12, borderRadius: 8 }}>
                  <label className="form-label" style={{ fontWeight: 700 }}>TOTALE COSTI SICUREZZA (€)</label>
                  <input type="number" className="form-control"
                    value={form.costi_sicurezza || ''}
                    onChange={e => set('costi_sicurezza', e.target.value)}
                    style={{ fontWeight: 700 }} />
                </div>
              </div>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(4)}>← Indietro</button>
                <button className="btn btn-primary" onClick={() => setStep(6)}>Avanti →</button>
              </div>
            </>
          )}

          {step === 6 && (
            <>
              <div className="wizard-title">Genera PSC</div>
              <div style={{ background: '#F8F5F0', borderRadius: 8, padding: 20, fontSize: '0.875rem', marginBottom: 20 }}>
                <div style={{ fontWeight: 600, color: '#1A3A5C', marginBottom: 10 }}>Riepilogo</div>
                {[
                  ['Opera',      form.descrizione_opera],
                  ['Cantiere',   `${form.indirizzo_cantiere || ''}, ${form.citta_cantiere || ''}`],
                  ['Committente',`${form.committente_nome || ''} ${form.committente_cognome || ''}`],
                  ['CSP',        `${form.csp_nome || ''} ${form.csp_cognome || ''}`],
                  ['Imprese',    impreseSel.map(i => i.ragione_sociale).join(', ')],
                  ['Costi sic.', form.costi_sicurezza ? `€ ${form.costi_sicurezza}` : ''],
                ].map(([k, v]) => v?.trim() && (
                  <div key={k} style={{ display: 'flex', gap: 12, marginBottom: 4 }}>
                    <span style={{ color: '#8A9BB0', minWidth: 100 }}>{k}:</span>
                    <span>{v}</span>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: '0.82rem', color: '#5A6B7D', marginBottom: 20 }}>
                L'AI genererà automaticamente le sezioni narrative conformi all'Allegato XV.
              </p>
              <div className="wizard-nav">
                <button className="btn btn-ghost" onClick={() => setStep(5)}>← Indietro</button>
                <button className="btn btn-gold" onClick={handleGenera} disabled={loading}>
                  {loading ? '⏳ Generazione con AI in corso...' : '🤖 Genera PSC con AI →'}
                </button>
              </div>
            </>
          )}

          {step === 7 && (
            <div style={{ textAlign: 'center', padding: '32px 0' }}>
              <div style={{ fontSize: '3rem', marginBottom: 16 }}>📗</div>
              <div style={{ fontSize: '1.4rem', fontWeight: 700, color: '#1A3A5C', marginBottom: 8 }}>PSC Generato!</div>
              <p style={{ color: '#5A6B7D', marginBottom: 24, maxWidth: 460, margin: '0 auto 24px' }}>
                Verificalo e firmalo prima dell'utilizzo in cantiere.
              </p>
              {docId && (
                <a href={`http://localhost:8000/api/documents/download/${docId}`} className="btn btn-gold" download>
                  ↓ Scarica PSC in DOCX
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