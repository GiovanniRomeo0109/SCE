import { useState, useContext, createContext } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Login from './pages/Login';
import Sidebar from './components/Sidebar';
import Notification from './components/Notification';
import Dashboard from './pages/Dashboard';
import NuovoDocumento from './pages/NuovoDocumento';
import NuovoProgetto from './pages/NuovoProgetto';
import Storico from './pages/Storico';
import AnagraficaCommittenti from './pages/AnagraficaCommittenti';
import AnagraficaImprese from './pages/AnagraficaImprese';
import AnagraficaCoordinatori from './pages/AnagraficaCoordinatori';
import WizardNotifica from './components/WizardNotifica';
import WizardPSC from './components/WizardPSC';
import WizardPOS from './components/WizardPOS';
import VerificaDocumenti from './pages/VerificaDocumenti';

export const NotifyCtx = createContext(null);

const NotifyContext = createContext(() => {});
export const useNotify = () => useContext(NotifyContext);

export default function App() {
  const [notify, setNotify] = useState(null);
  const [token, setToken] = useState(() => localStorage.getItem('sce_token'));

  const showNotify = (msg, type = 'info') => {
    setNotify({ msg, type });
    setTimeout(() => setNotify(null), 3500);
  };

  const handleLogin = (data) => {
    setToken(data.access_token);
  };

  const handleLogout = () => {
    localStorage.removeItem('sce_token');
    localStorage.removeItem('sce_user');
    setToken(null);
  };

  // Se non autenticato → mostra solo Login
  if (!token) {
    return (
      <NotifyContext.Provider value={showNotify}>
        <Login onLogin={handleLogin} />
      </NotifyContext.Provider>
    );
  }

  return (
      <NotifyContext.Provider value={showNotify}>
  <BrowserRouter>
    
         {notify && (
          <div className={`toast toast-${notify.type}`}>{notify.msg}</div>
        )}
        <div className="app-layout">
          <Sidebar onLogout={handleLogout} />
          <main className="main-content">

            <Routes>
              <Route path="/"                    element={<Dashboard />} />
              <Route path="/nuovo"               element={<NuovoDocumento />} />
              <Route path="/nuovo-progetto"      element={<NuovoProgetto />} />
              <Route path="/nuovo/notifica"      element={<WizardNotifica />} />
              <Route path="/nuovo/psc"           element={<WizardPSC />} />
              <Route path="/nuovo/pos"           element={<WizardPOS />} />
              <Route path="/storico"             element={<Storico />} />
              <Route path="/committenti"         element={<AnagraficaCommittenti />} />
              <Route path="/imprese"             element={<AnagraficaImprese />} />
              <Route path="/coordinatori"        element={<AnagraficaCoordinatori />} />
              <Route path="/verifica" element={<VerificaDocumenti />} />
               <Route path="/" element={<Navigate to="/wizard" />} />
              {/* ... */}

            </Routes>
          </main>
        </div>
        {notify && (
          <Notification message={notify.msg} type={notify.type} onClose={() => setNotify(null)} />
        )}
      </BrowserRouter>
    </NotifyContext.Provider>
  );
}