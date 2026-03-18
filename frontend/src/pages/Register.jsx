import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useNotify } from '../App';

const BASE_URL = process.env.NODE_ENV === 'production' ? '' : 'http://localhost:8000';

export default function Register({ onLogin }) {
  const notify = useNotify();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', email: '', nome_cognome: '', password: '', conferma: '' });
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const validate = () => {
    const e = {};
    if (form.nome_cognome.trim().length < 2) e.nome_cognome = 'Inserisci nome e cognome';
    if (form.username.trim().length < 3)     e.username = 'Almeno 3 caratteri';
    if (!/^[a-zA-Z0-9_]+$/.test(form.username)) e.username = 'Solo lettere, numeri e underscore';
    if (!form.email.includes('@'))           e.email = 'Email non valida';
    if (form.password.length < 6)           e.password = 'Almeno 6 caratteri';
    if (form.password !== form.conferma)    e.conferma = 'Le password non coincidono';
    setErrors(e);
    return Object.keys(e).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: form.username.toLowerCase().trim(),
          email: form.email.trim(),
          nome_cognome: form.nome_cognome.trim(),
          password: form.password,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Errore registrazione');

      // Salva token e accedi direttamente
      localStorage.setItem('sce_token', data.access_token);
      localStorage.setItem('sce_user', JSON.stringify({ username: data.username, nome_cognome: data.nome_cognome }));
      onLogin(data);
      notify('Benvenuto in SafetyDocs! 🎉', 'success');
    } catch (err) {
      notify(err.message, 'error');
    } finally {
      setLoading(false);
    }
  };

  const field = (key, label, type = 'text', placeholder = '') => (
    <div className="form-group" style={{ marginBottom: 16 }}>
      <label style={{ display: 'block', marginBottom: 6, fontWeight: 600, fontSize: '0.85rem', color: '#1A3A5C' }}>
        {label}
      </label>
      <input
        type={type}
        value={form[key]}
        onChange={e => set(key, e.target.value)}
        onKeyDown={e => e.key === 'Enter' && handleSubmit()}
        placeholder={placeholder}
        style={{
          width: '100%', padding: '10px 12px', borderRadius: 8, border: errors[key] ? '1.5px solid #e74c3c' : '1.5px solid #dce3ed',
          fontSize: '0.95rem', boxSizing: 'border-box', outline: 'none',
        }}
      />
      {errors[key] && <div style={{ color: '#e74c3c', fontSize: '0.78rem', marginTop: 4 }}>{errors[key]}</div>}
    </div>
  );

  return (
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f0f4f9' }}>
      <div style={{ background: '#fff', borderRadius: 16, padding: '40px 36px', width: '100%', maxWidth: 420, boxShadow: '0 4px 24px rgba(26,58,92,0.10)' }}>

        {/* Logo / Titolo */}
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{ fontSize: 36, marginBottom: 8 }}>🏗️</div>
          <h1 style={{ color: '#1A3A5C', fontSize: '1.5rem', fontWeight: 800, margin: 0 }}>SafetyDocs</h1>
          <p style={{ color: '#5A6B7D', fontSize: '0.88rem', margin: '6px 0 0' }}>Crea il tuo account gratuito</p>
        </div>

        {field('nome_cognome', 'Nome e Cognome', 'text', 'Mario Rossi')}
        {field('username', 'Username', 'text', 'mario_rossi')}
        {field('email', 'Email', 'email', 'mario@studio.it')}
        {field('password', 'Password', 'password', 'Almeno 6 caratteri')}
        {field('conferma', 'Conferma Password', 'password', 'Ripeti la password')}

        <button
          onClick={handleSubmit}
          disabled={loading}
          style={{
            width: '100%', padding: '12px', borderRadius: 8, border: 'none',
            background: loading ? '#8A9BB0' : '#1A3A5C', color: '#fff',
            fontWeight: 700, fontSize: '1rem', cursor: loading ? 'not-allowed' : 'pointer',
            marginTop: 4,
          }}
        >
          {loading ? 'Registrazione in corso…' : 'Crea account'}
        </button>

        <p style={{ textAlign: 'center', marginTop: 20, fontSize: '0.88rem', color: '#5A6B7D' }}>
          Hai già un account?{' '}
          <Link to="/login" style={{ color: '#1A3A5C', fontWeight: 700, textDecoration: 'none' }}>
            Accedi
          </Link>
        </p>
      </div>
    </div>
  );
}
