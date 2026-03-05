const CATEGORIE = [
  {
    key: 'committente', label: '👤 Committente',
    fields: ['nome','cognome','ragione_sociale','codice_fiscale','piva','indirizzo','citta','provincia','telefono','email','pec']
  },
  {
    key: 'impresa', label: '🏢 Impresa Esecutrice',
    fields: ['ragione_sociale','piva','codice_fiscale','indirizzo','citta','provincia','telefono','cciaa','inail_pat','nome_dl','cognome_dl','nome_rspp','cognome_rspp','nome_mc','cognome_mc','nome_rls','cognome_rls']
  },
  {
    key: 'cantiere', label: '🏗️ Cantiere',
    fields: ['indirizzo_cantiere','citta_cantiere','provincia_cantiere']
  },
  {
    key: 'opera', label: '📐 Opera',
    fields: ['natura_opera','descrizione_opera','destinazione_uso']
  },
  {
    key: 'lavori', label: '⚙️ Lavori',
    fields: ['data_inizio','data_fine','durata_lavori','importo_lavori','importo_sicurezza','num_lavoratori','uomini_giorno','max_lavoratori','fasi_descrizione']
  },
  {
    key: 'coordinatori', label: '📋 Coordinatori',
    fields: ['csp_nome','csp_cognome','csp_ordine','csp_numero_ordine','cse_nome','cse_cognome','cse_ordine','cse_numero_ordine']
  },
];

const LABEL = {
  nome: 'Nome', cognome: 'Cognome', ragione_sociale: 'Ragione Sociale',
  codice_fiscale: 'Codice Fiscale', piva: 'P.IVA', indirizzo: 'Indirizzo',
  citta: 'Città', provincia: 'Provincia', telefono: 'Telefono', email: 'Email', pec: 'PEC',
  cciaa: 'CCIAA', inail_pat: 'INAIL PAT', nome_dl: 'Nome DL', cognome_dl: 'Cognome DL',
  nome_rspp: 'Nome RSPP', cognome_rspp: 'Cognome RSPP', nome_mc: 'Nome MC', cognome_mc: 'Cognome MC',
  nome_rls: 'Nome RLS', cognome_rls: 'Cognome RLS',
  indirizzo_cantiere: 'Indirizzo', citta_cantiere: 'Comune', provincia_cantiere: 'Provincia',
  natura_opera: 'Natura Opera', descrizione_opera: 'Descrizione', destinazione_uso: 'Destinazione',
  data_inizio: 'Data Inizio', data_fine: 'Data Fine', durata_lavori: 'Durata',
  importo_lavori: 'Importo Lavori', importo_sicurezza: 'Costi Sicurezza',
  num_lavoratori: 'N. Lavoratori', uomini_giorno: 'Uomini/Giorno', max_lavoratori: 'Max Contemporanei',
  fasi_descrizione: 'Fasi Lavorative', asl_destinataria: 'ASL',
  csp_nome: 'CSP Nome', csp_cognome: 'CSP Cognome', csp_ordine: 'CSP Ordine', csp_numero_ordine: 'CSP N. Iscrizione',
  cse_nome: 'CSE Nome', cse_cognome: 'CSE Cognome', cse_ordine: 'CSE Ordine', cse_numero_ordine: 'CSE N. Iscrizione',
};

export default function ReviewDati({ risultato, datiFinali, risolti, onRisolvi, onProcedi, onBack, tipoDoc }) {
  const { riepilogo, conflitti = [], errori = [], dati, documenti_analizzati = [] } = risultato;

  const conflittiRisoltiCount = Object.keys(risolti).length;
  const tuttiRisolti = conflittiRisoltiCount >= conflitti.length;

  return (
    <div style={{ maxWidth: 860 }}>

      {/* Sommario */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 16, marginBottom: 24 }}>
        <div className="stat-card" style={{ borderLeftColor: '#27AE60' }}>
          <div className="stat-num" style={{ color: '#27AE60', fontSize: '1.6rem' }}>
            {riepilogo?.dati_estratti || 0}
          </div>
          <div className="stat-label">Campi estratti automaticamente</div>
        </div>
        <div className="stat-card" style={{ borderLeftColor: conflitti.length > 0 ? '#C88B2A' : '#27AE60' }}>
          <div className="stat-num" style={{ color: conflitti.length > 0 ? '#C88B2A' : '#27AE60', fontSize: '1.6rem' }}>
            {conflitti.length}
          </div>
          <div className="stat-label">
            Conflitti {conflitti.length > 0 ? `(${conflittiRisoltiCount}/${conflitti.length} risolti)` : 'rilevati'}
          </div>
        </div>
        <div className="stat-card" style={{ borderLeftColor: '#1A3A5C' }}>
          <div className="stat-num" style={{ color: '#1A3A5C', fontSize: '1.6rem' }}>
            {documenti_analizzati.length}
          </div>
          <div className="stat-label">Documenti analizzati</div>
        </div>
      </div>

      {/* Documenti analizzati */}
      {documenti_analizzati.length > 0 && (
        <div className="info-box" style={{ marginBottom: 20 }}>
          ✅ Analizzati: {documenti_analizzati.join(' · ')}
        </div>
      )}

      {/* Errori di lettura */}
      {errori.length > 0 && (
        <div className="warn-box" style={{ marginBottom: 20 }}>
          ⚠️ Impossibile analizzare: {errori.map(e => e.file).join(', ')}
        </div>
      )}

      {/* Conflitti */}
      {conflitti.length > 0 && (
        <div className="card" style={{ marginBottom: 20, borderColor: '#FDE68A', borderWidth: 2 }}>
          <div style={{ fontWeight: 700, color: '#92400E', marginBottom: 16 }}>
            ⚠️ Conflitti — stesso dato trovato con valori diversi in documenti differenti
          </div>
          {conflitti.map(c => {
            const isRisolto = !!risolti[c.campo];
            return (
              <div key={c.campo} style={{
                background: isRisolto ? '#F0FDF4' : '#FFFBEB',
                border: `1.5px solid ${isRisolto ? '#BBF7D0' : '#FDE68A'}`,
                borderRadius: 8, padding: 16, marginBottom: 12
              }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#5A6B7D', marginBottom: 12 }}>
                  Campo: <span style={{ color: '#1A3A5C' }}>
                    {LABEL[c.campo.split('.')[1]] || c.campo}
                  </span>
                  {isRisolto && <span style={{ color: '#27AE60', marginLeft: 10 }}>✓ Risolto</span>}
                </div>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {[{ v: c.valore_a, f: c.fonte_a }, { v: c.valore_b, f: c.fonte_b }].map((opt, i) => (
                    <button key={i} onClick={() => onRisolvi(c.campo, opt.v)}
                      style={{
                        flex: 1, minWidth: 200, padding: '10px 14px',
                        borderRadius: 6, border: '1.5px solid', cursor: 'pointer', textAlign: 'left',
                        borderColor: risolti[c.campo] === opt.v ? '#1A3A5C' : 'var(--border)',
                        background: risolti[c.campo] === opt.v ? '#EEF4FA' : 'white',
                      }}>
                      <div style={{ fontWeight: 600, fontSize: '0.875rem', color: '#1A3A5C', marginBottom: 3 }}>
                        {opt.v}
                      </div>
                      <div style={{ fontSize: '0.7rem', color: '#8A9BB0' }}>📎 {opt.f}</div>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Dati estratti per categoria */}
      {CATEGORIE.map(cat => {
        const datiCat = dati[cat.key];
        if (!datiCat || Object.keys(datiCat).length === 0) return null;
        return (
          <div key={cat.key} className="card" style={{ marginBottom: 16 }}>
            <div style={{ fontWeight: 700, color: '#1A3A5C', marginBottom: 14, fontSize: '0.95rem' }}>
              {cat.label}
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              {Object.entries(datiCat).map(([chiave, info]) => {
                const haConflitto = info.conflitti?.length > 0;
                return (
                  <div key={chiave} style={{
                    padding: '8px 12px', background: '#F8F5F0', borderRadius: 6,
                    borderLeft: `3px solid ${haConflitto ? '#C88B2A' : '#27AE60'}`
                  }}>
                    <div style={{ fontSize: '0.68rem', color: '#8A9BB0', marginBottom: 2 }}>
                      {LABEL[chiave] || chiave}
                      {haConflitto && <span style={{ color: '#C88B2A', marginLeft: 6 }}>⚠ conflitto</span>}
                    </div>
                    <div style={{ fontSize: '0.875rem', color: '#1A3A5C', fontWeight: 500 }}>
                      {datiFinali[chiave] || info.valore}
                    </div>
                    <div style={{ fontSize: '0.65rem', color: '#8A9BB0', marginTop: 2 }}>
                      📎 {info.fonte}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Navigazione */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 28 }}>
        <button className="btn btn-ghost" onClick={onBack}>← Ricarica documenti</button>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
          {conflitti.length > 0 && !tuttiRisolti && (
            <div style={{ fontSize: '0.78rem', color: '#C88B2A' }}>
              ⚠️ {conflitti.length - conflittiRisoltiCount} conflitti non risolti — verrà usato il primo valore trovato
            </div>
          )}
          <button className="btn btn-gold" onClick={onProcedi}
            style={{ fontSize: '1rem', padding: '11px 28px' }}>
            ✅ Conferma e compila {tipoDoc} →
          </button>
        </div>
      </div>
    </div>
  );
}