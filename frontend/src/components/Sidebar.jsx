import { NavLink } from 'react-router-dom';

const links = [
  { section: 'Documenti' },
  { to: '/',        icon: '🏠', label: 'Dashboard' },
  { to: '/nuovo',   icon: '➕', label: 'Nuovo Documento' },
  { to: '/storico', icon: '📁', label: 'Storico' },
  { section: 'Anagrafica' },
  { to: '/committenti',  icon: '👤', label: 'Committenti' },
  { to: '/imprese',      icon: '🏢', label: 'Imprese' },
  { to: '/coordinatori', icon: '📐', label: 'Coordinatori' },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h2>🦺 SafetyDocs</h2>
        <p>Sicurezza Cantieri D.Lgs 81/08</p>
      </div>
      <nav className="sidebar-nav">
        {links.map((l, i) =>
          l.section
            ? <div key={i} className="sidebar-section">{l.section}</div>
            : <NavLink key={l.to} to={l.to} end={l.to === '/'}
                className={({ isActive }) => isActive ? 'active' : ''}>
                <span>{l.icon}</span>{l.label}
              </NavLink>
        )}
      </nav>
      <div className="sidebar-footer">D.Lgs. 81/2008 — v1.0</div>
    </aside>
  );
}