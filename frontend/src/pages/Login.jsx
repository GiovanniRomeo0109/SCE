import { useState } from 'react';

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!username || !password) { setError('Inserisci email e password'); return; }
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || 'Credenziali non valide'); return; }
      localStorage.setItem('sce_token', data.access_token);
      localStorage.setItem('sce_user', JSON.stringify({
        username: data.username,
        nome: data.nome,
        max_calls_giorno: data.max_calls_giorno,
      }));
      onLogin(data);
    } catch {
      setError('Errore di connessione al server');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => { if (e.key === 'Enter') handleSubmit(); };

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: 'linear-gradient(135deg, #0F1E2D 0%, #1A2E42 100%)',
    }}>
      <div style={{
        background: '#1A2E42', borderRadius: 16, padding: '48px 40px',
        width: '100%', maxWidth: 400, boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>🏗️</div>
          <h1 style={{ color: '#F5C842', fontSize: '1.6rem', fontWeight: 700, margin: 0 }}>SCE</h1>
          <p style={{ color: '#8A9BB0', fontSize: '0.85rem', margin: '4px 0 0' }}>
            Sicurezza Cantieri Edili
          </p>
        </div>

        {/* Form */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ color: '#8A9BB0', fontSize: '0.8rem', display: 'block', marginBottom: 6 }}>
              EMAIL
            </label>
            <input
              type="email"
              value={username}
              onChange={e => setUsername(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="mario@studio.it"
              style={{
                width: '100%', padding: '12px 14px', borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.12)',
                background: 'rgba(255,255,255,0.06)', color: '#E8EDF2',
                fontSize: '0.95rem', boxSizing: 'border-box', outline: 'none',
              }}
            />
          </div>
          <div>
            <label style={{ color: '#8A9BB0', fontSize: '0.8rem', display: 'block', marginBottom: 6 }}>
              PASSWORD
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="••••••••"
              style={{
                width: '100%', padding: '12px 14px', borderRadius: 8,
                border: '1px solid rgba(255,255,255,0.12)',
                background: 'rgba(255,255,255,0.06)', color: '#E8EDF2',
                fontSize: '0.95rem', boxSizing: 'border-box', outline: 'none',
              }}
            />
          </div>

          {error && (
            <div style={{
              background: 'rgba(220,53,69,0.15)', border: '1px solid rgba(220,53,69,0.4)',
              borderRadius: 8, padding: '10px 14px', color: '#ff6b7a', fontSize: '0.85rem',
            }}>
              ⚠️ {error}
            </div>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading}
            style={{
              background: loading ? '#5A6B7D' : 'linear-gradient(135deg, #F5C842, #E0A800)',
              color: '#0F1E2D', border: 'none', borderRadius: 8, padding: '13px',
              fontSize: '0.95rem', fontWeight: 700, cursor: loading ? 'not-allowed' : 'pointer',
              marginTop: 4, transition: 'opacity 0.2s',
            }}
          >
            {loading ? 'Accesso in corso...' : 'Accedi →'}
          </button>
        </div>

        <p style={{ textAlign: 'center', color: '#5A6B7D', fontSize: '0.75rem', marginTop: 24 }}>
          Demo SCE · D.Lgs. 81/2008
        </p>
      </div>
    </div>
  );
}
