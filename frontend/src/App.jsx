import React, { useState, useCallback, createContext, useContext } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
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
export const useNotify = () => useContext(NotifyCtx);

export default function App() {
  const [notif, setNotif] = useState(null);
  const notify = useCallback((message, type = 'success') => setNotif({ message, type }), []);

  return (
    <BrowserRouter>
      <NotifyCtx.Provider value={notify}>
        <div className="layout">
          <Sidebar />
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
            </Routes>
          </main>
        </div>
        {notif && (
          <Notification message={notif.message} type={notif.type} onClose={() => setNotif(null)} />
        )}
      </NotifyCtx.Provider>
    </BrowserRouter>
  );
}