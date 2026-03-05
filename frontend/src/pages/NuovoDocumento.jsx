import { useNavigate } from 'react-router-dom';

const tipi = [
  {
    path: '/nuovo/notifica', icon: '📋',
    titolo: 'Notifica Preliminare', norma: 'Art. 99 — D.Lgs. 81/2008',
    desc: 'Da inviare ad ASL e ITL prima dell\'inizio lavori.',
  },
  {
    path: '/nuovo/psc', icon: '📗',
    titolo: 'Piano di Sicurezza e Coordinamento', norma: 'Art. 100 — D.Lgs. 81/2008',
    desc: 'Obbligatorio quando operano più imprese in cantiere.',
  },
  {
    path: '/nuovo/pos', icon: '📘',
    titolo: 'Piano Operativo di Sicurezza', norma: 'Art. 101 — D.Lgs. 81/2008',
    desc: 'Obbligatorio per ogni impresa esecutrice.',
  },
];

export default function NuovoDocumento() {
  const nav = useNavigate();
  return (
    <div>
      <div className="page-header">
        <h1>Nuovo Documento — Compilazione Manuale</h1>
        <p>Compila il documento inserendo i dati a mano step per step.</p>
      </div>
      <div className="info-box" style={{ marginBottom: 24 }}>
        💡 Vuoi risparmiare tempo? Usa <strong
          onClick={() => nav('/nuovo-progetto')}
          style={{ cursor: 'pointer', textDecoration: 'underline', color: '#1A3A5C' }}>
          Nuovo con AI
        </strong> — carica i tuoi documenti e l'agente compila tutto automaticamente.
      </div>
      <div className="doc-types">
        {tipi.map(t => (
          <div key={t.path} className="doc-type-card" onClick={() => nav(t.path, { state: { initialData: {} } })}>
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