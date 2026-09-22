import { NavLink } from 'react-router-dom';
import UsageBar from './UsageBar';

const links = [
  { section: 'Documenti' },
  { to: '/',               icon: '🏠', label: 'Dashboard' },
  { to: '/verifica', icon: '🔍', label: 'Verifica Documenti' },
  { to: '/nuovo-progetto', icon: '🤖', label: 'Nuovo con AI', highlight: true },
  { to: '/nuovo',          icon: '➕', label: 'Nuovo manuale' },
  { to: '/storico',        icon: '📁', label: 'Storico' },
  { section: 'Anagrafica' },
  { to: '/committenti',    icon: '👤', label: 'Committenti' },
  { to: '/imprese',        icon: '🏢', label: 'Imprese' },
  { to: '/coordinatori',   icon: '📐', label: 'Coordinatori' },
  { to: '/elenchi-prezzi', icon: '💶', label: 'Elenchi prezzi' },
];

export default function Sidebar({ onLogout }) {
  let utente = {};
  try { utente = JSON.parse(localStorage.getItem('sce_user') || '{}'); } catch {}
  const nome = utente.nome_cognome || utente.username || 'Utente';

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h2>🦺 SafetyDocs</h2>
        <p>Sicurezza Cantieri D.Lgs 81/08</p>
      </div>
      <nav className="sidebar-nav">
        {links.map((l, i) =>
          l.section ? (
            <div key={i} className="sidebar-section">{l.section}</div>
          ) : (
            <NavLink key={l.to} to={l.to} end={l.to === '/'}
              className={({ isActive }) => isActive ? 'active' : ''}
              style={l.highlight ? { color: '#C88B2A', fontWeight: 600 } : {}}>
              <span>{l.icon}</span>{l.label}
              {l.highlight && <span style={{
                marginLeft: 'auto', fontSize: '0.6rem', background: '#C88B2A',
                color: 'white', padding: '2px 6px', borderRadius: 99, fontWeight: 700
              }}>AI</span>}
            </NavLink>
          )
        )}
      </nav>
      {/* Budget demo + utente + logout, spinti in fondo alla barra */}
      <div style={{ marginTop: 'auto', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
        <UsageBar />
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
          fontSize: '0.78rem', color: '#C9D3DE',
        }}>
          <span>👤</span>
          <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                title={utente.username}>
            {nome}
          </span>
          {onLogout && (
            <button onClick={onLogout} title="Esci" style={{
              background: 'none', border: '1px solid rgba(255,255,255,0.2)', borderRadius: 6,
              color: '#C9D3DE', cursor: 'pointer', fontSize: '0.75rem', padding: '3px 8px',
            }}>
              Esci
            </button>
          )}
        </div>
      </div>
      <div className="sidebar-footer">D.Lgs. 81/2008 — v1.0</div>
    </aside>
  );
}