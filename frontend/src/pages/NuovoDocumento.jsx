import { useNavigate } from 'react-router-dom';

const tipi = [
  {
    path: '/nuovo/notifica',
    icon: '📋',
    titolo: 'Notifica Preliminare',
    norma: 'Art. 99 — D.Lgs. 81/2008',
    desc: 'Obbligatoria quando il cantiere supera 200 uomini-giorno o 20 lavoratori contemporanei. Da inviare ad ASL e ITL prima dell\'inizio lavori.',
  },
  {
    path: '/nuovo/psc',
    icon: '📗',
    titolo: 'Piano di Sicurezza e Coordinamento',
    norma: 'Art. 100 — D.Lgs. 81/2008',
    desc: 'Obbligatorio quando operano più imprese nel cantiere. Redatto dal Coordinatore per la Progettazione (CSP).',
  },
  {
    path: '/nuovo/pos',
    icon: '📘',
    titolo: 'Piano Operativo di Sicurezza',
    norma: 'Art. 101 — D.Lgs. 81/2008',
    desc: 'Obbligatorio per ogni impresa esecutrice, indipendentemente dalla dimensione del cantiere. Redatto dal Datore di Lavoro.',
  },
];

export default function NuovoDocumento() {
  const nav = useNavigate();
  return (
    <div>
      <div className="page-header">
        <h1>Nuovo Documento</h1>
        <p>Seleziona il tipo di documento. L'agente verificherà l'obbligatorietà e guiderà la compilazione.</p>
      </div>
      <div className="doc-types">
        {tipi.map(t => (
          <div key={t.path} className="doc-type-card" onClick={() => nav(t.path)}>
            <div className="doc-icon">{t.icon}</div>
            <h3>{t.titolo}</h3>
            <p style={{ fontSize: '0.7rem', color: '#C88B2A', fontWeight: 600, marginBottom: 8 }}>{t.norma}</p>
            <p>{t.desc}</p>
          </div>
        ))}
      </div>
    </div>
  );
}