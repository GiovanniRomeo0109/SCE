import { useState, useEffect } from 'react';
import { getImprese, createImpresa, updateImpresa, deleteImpresa } from '../utils/api';
import { useNotify } from '../App';
import Field from '../components/Field';

const EMPTY = { ragione_sociale: '', codice_fiscale: '', piva: '', indirizzo: '', citta: '', provincia: '', telefono: '', email: '', cciaa: '', numero_cciaa: '', inail_pat: '', cassa_edile: '', ccnl: 'CCNL Edilizia Industria', nome_dl: '', cognome_dl: '', nome_rspp: '', cognome_rspp: '', nome_mc: '', cognome_mc: '', nome_rls: '', cognome_rls: '' };

export default function AnagraficaImprese() {
  const [list, setList]       = useState([]);
  const [form, setForm]       = useState(EMPTY);
  const [editing, setEditing] = useState(null);
  const [showForm, setShow]   = useState(false);
  const notify = useNotify();

  const carica = () => {
    getImprese().then(r => setList(r.data)).catch(() => {});
  };

  useEffect(() => { carica(); }, []);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const apri = (item = null) => { setEditing(item); setForm(item ? { ...item } : EMPTY); setShow(true); };

  const salva = async (e) => {
    e.preventDefault();
    if (!form.ragione_sociale || !form.piva) { notify('Ragione sociale e P.IVA sono obbligatorie', 'error'); return; }
    try {
      if (editing) await updateImpresa(editing.id, form);
      else         await createImpresa(form);
      notify(editing ? 'Impresa aggiornata ✓' : 'Impresa aggiunta ✓', 'success');
      setShow(false); carica();
    } catch { notify('Errore durante il salvataggio', 'error'); }
  };

  const elimina = async (id) => {
    if (!window.confirm('Eliminare questa impresa?')) return;
    try { await deleteImpresa(id); notify('Eliminata', 'success'); carica(); }
    catch { notify('Errore', 'error'); }
  };

  return (
    <div>
      <div className="page-header"><h1>🏢 Imprese Esecutrici</h1><p>Anagrafica imprese persistente</p></div>
      <div className="toolbar">
        <span style={{ color: '#8A9BB0', fontSize: '0.85rem' }}>{list.length} imprese</span>
        <button className="btn btn-primary" onClick={() => apri()}>+ Nuova Impresa</button>
      </div>

      {showForm && (
        <div className="card" style={{ marginBottom: 20, borderColor: '#BFDBFE', borderWidth: 2 }}>
          <div style={{ fontWeight: 700, fontSize: '1rem', color: '#1A3A5C', marginBottom: 20 }}>
            {editing ? '✏️ Modifica' : '➕ Nuova'} Impresa
          </div>
          <form onSubmit={salva}>
            <div className="section-divider">Dati societari</div>
            <div className="form-grid">
              <Field form={form} set={set} label="Ragione Sociale *" field="ragione_sociale" />
              <Field form={form} set={set} label="P.IVA *"           field="piva" />
              <Field form={form} set={set} label="Codice Fiscale"    field="codice_fiscale" />
              <Field form={form} set={set} label="Indirizzo Sede"    field="indirizzo" />
              <Field form={form} set={set} label="Città"             field="citta" />
              <Field form={form} set={set} label="Provincia"         field="provincia" />
              <Field form={form} set={set} label="Telefono"          field="telefono" />
              <Field form={form} set={set} label="Email / PEC"       field="email" type="email" />
              <Field form={form} set={set} label="CCIAA"             field="cciaa" />
              <Field form={form} set={set} label="N. iscrizione CCIAA"   field="numero_cciaa" />
              <Field form={form} set={set} label="Posizione INAIL (PAT)" field="inail_pat" />
              <Field form={form} set={set} label="Cassa Edile"       field="cassa_edile" />
            </div>
            <div className="form-group">
              <label className="form-label">CCNL applicato</label>
              <select className="form-control" value={form.ccnl || ''} onChange={e => set('ccnl', e.target.value)}>
                <option>CCNL Edilizia Industria</option>
                <option>CCNL Edilizia Artigianato</option>
                <option>CCNL Edilizia Cooperazione</option>
                <option>CCNL Metalmeccanico</option>
              </select>
            </div>
            <div className="section-divider">Figure della sicurezza</div>
            <div className="form-grid">
              <Field form={form} set={set} label="Nome Datore di Lavoro"     field="nome_dl" />
              <Field form={form} set={set} label="Cognome Datore di Lavoro"  field="cognome_dl" />
              <Field form={form} set={set} label="Nome RSPP"                 field="nome_rspp" />
              <Field form={form} set={set} label="Cognome RSPP"              field="cognome_rspp" />
              <Field form={form} set={set} label="Nome Medico Competente"    field="nome_mc" />
              <Field form={form} set={set} label="Cognome Medico Competente" field="cognome_mc" />
              <Field form={form} set={set} label="Nome RLS / RLST"           field="nome_rls" />
              <Field form={form} set={set} label="Cognome RLS / RLST"        field="cognome_rls" />
            </div>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
              <button type="button" className="btn btn-ghost" onClick={() => setShow(false)}>Annulla</button>
              <button type="submit" className="btn btn-primary">💾 Salva</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        {list.length === 0 ? (
          <div className="empty-state"><div className="empty-icon">🏢</div><p>Nessuna impresa registrata</p></div>
        ) : (
          <div className="table-wrapper">
            <table>
              <thead><tr><th>Ragione Sociale</th><th>P.IVA</th><th>Datore di Lavoro</th><th>RSPP</th><th>Azioni</th></tr></thead>
              <tbody>
                {list.map(i => (
                  <tr key={i.id}>
                    <td><strong>{i.ragione_sociale}</strong><br /><span style={{ fontSize: '0.75rem', color: '#8A9BB0' }}>{i.citta}</span></td>
                    <td style={{ fontSize: '0.82rem' }}>{i.piva}</td>
                    <td style={{ fontSize: '0.82rem' }}>{i.nome_dl ? `${i.nome_dl} ${i.cognome_dl}` : '—'}</td>
                    <td style={{ fontSize: '0.82rem' }}>{i.nome_rspp ? `${i.nome_rspp} ${i.cognome_rspp}` : '—'}</td>
                    <td style={{ display: 'flex', gap: 8 }}>
                      <button className="btn btn-ghost btn-sm" onClick={() => apri(i)}>✏️</button>
                      <button className="btn btn-danger btn-sm" onClick={() => elimina(i.id)}>🗑</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}