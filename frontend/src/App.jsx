import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { HashRouter, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import Navbar from './components/Navbar';
import ActionHubHome from './components/ActionHubHome';
import EmergencyRequestForm from './components/EmergencyRequestForm';
import RequesterDashboard from './components/RequesterDashboard';
import DonorPortalHub from './components/DonorPortalHub';
import HospitalInventoryView from './components/HospitalInventoryView';
import AuditLogViewer from './components/AuditLogViewer';
import DonorPortalModal from './components/DonorPortalModal';
import AuthModal from './components/AuthModal';
import { ToastProvider, useToast } from './components/NotificationToast';
import { AuthProvider, useAuth } from './context/AuthContext';
import { getCurrentPosition } from './services/geolocation';

// ── GPS Context ─────────────────────────────────────────────────
const GPSContext = createContext(null);
export function useGPS() {
  return useContext(GPSContext);
}

function GPSProvider({ children }) {
  const [location, setLocation] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const { addToast } = useToast();

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const pos = await getCurrentPosition();
      setLocation(pos);
      setError(null);
    } catch (err) {
      const msg = err.message || 'Location unavailable';
      setError(msg);
      setLocation({ latitude: 37.7631, longitude: -122.4578 }); // FIXED: Silently fallback to SF for local testing
      addToast({ title: 'GPS Fallback Enabled', message: 'Browser location failed. Using San Francisco for testing.', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <GPSContext.Provider value={{ location, error, loading, refresh }}>
      {children}
    </GPSContext.Provider>
  );
}

// ── Main App ────────────────────────────────────────────────────
function AppContent() {
  const { showAuthModal, setShowAuthModal } = useAuth();
  const [activeRequestData, setActiveRequestData] = useState(null);
  const [isDonorPortalOpen, setIsDonorPortalOpen] = useState(false);
  const [simulatedMatchId, setSimulatedMatchId] = useState(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  
  const navigate = useNavigate();
  const location = useLocation();

  // Derive active tab from pathname for backwards compatibility with Navbar
  const pathPart = location.pathname.split('/')[1];
  const activeTab = pathPart || 'home';

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);
    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleSetActiveTab = (tab) => {
    if (tab === 'home') navigate('/');
    else navigate(`/${tab}`);
  };

  const handleRequestSubmitted = (response) => {
    setActiveRequestData(response);
    navigate(`/tracker/${response.request.id}`);
  };

  const handleSimulateDonorAction = (matchId) => {
    setSimulatedMatchId(matchId);
    setIsDonorPortalOpen(true);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#050505] text-[#F5F5F7] font-sans selection:bg-blood-500 selection:text-white">
      <AnimatePresence>
        {!isOnline && (
          <motion.div 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="bg-red-900/80 text-red-200 text-xs font-bold text-center py-2 px-4 backdrop-blur-md"
          >
            ⚡ You're offline — data may not be current. The app will continue working with cached data.
          </motion.div>
        )}
      </AnimatePresence>

      <Navbar
        activeTab={activeTab}
        setActiveTab={handleSetActiveTab}
        activeRequest={activeRequestData?.request}
        onOpenDonorPortal={() => setIsDonorPortalOpen(true)}
      />

      <main className="flex-1 w-full mx-auto pb-24 lg:pb-8 relative">
        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6"
              >
                <ActionHubHome
                  onNavigateTab={handleSetActiveTab}
                  onRequestSubmitted={handleRequestSubmitted}
                />
              </motion.div>
            } />
            
            <Route path="/request" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6"
              >
                <EmergencyRequestForm onRequestSubmitted={handleRequestSubmitted} />
              </motion.div>
            } />
            
            <Route path="/tracker/:id?" element={
              <motion.div
                initial={{ opacity: 0, filter: 'blur(12px)', scale: 1.02 }}
                animate={{ opacity: 1, filter: 'blur(0px)', scale: 1 }}
                exit={{ opacity: 0, filter: 'blur(8px)', scale: 0.98 }}
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="absolute inset-0 z-50 bg-[#050505]"
              >
                <RequesterDashboard
                  requestId={activeRequestData?.request?.id}
                  requestData={activeRequestData}
                  onSimulateDonorAction={handleSimulateDonorAction}
                />
              </motion.div>
            } />
            
            <Route path="/donor-portal" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6"
              >
                <DonorPortalHub
                  onSimulateAlert={() => setIsDonorPortalOpen(true)}
                />
              </motion.div>
            } />
            
            <Route path="/banks" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6"
              >
                <HospitalInventoryView />
              </motion.div>
            } />
            
            <Route path="/audit/:id?" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6"
              >
                <AuditLogViewer activeRequestId={activeRequestData?.request?.id} />
              </motion.div>
            } />
          </Routes>
        </AnimatePresence>
      </main>

      <DonorPortalModal
        isOpen={isDonorPortalOpen}
        onClose={() => setIsDonorPortalOpen(false)}
        activeMatchId={simulatedMatchId}
        requestDetails={activeRequestData?.request}
      />

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
      />

      <footer className="hidden lg:block py-6 text-center text-xs text-[#86868B] bg-transparent">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-1.5 h-1.5 rounded-full bg-blood-500 animate-pulse-fast"></div>
            LifePulse Network &copy; 2026
          </div>
          <div className="flex gap-6 tracking-wide">
            <span className="hover:text-white transition-colors cursor-pointer">AI Match Engine</span>
            <span className="hover:text-white transition-colors cursor-pointer">Global Network</span>
            <span className="hover:text-white transition-colors cursor-pointer">Live Routing</span>
          </div>
        </div>
      </footer>

      <MobileBottomNav
        activeTab={activeTab}
        setActiveTab={handleSetActiveTab}
        hasActiveRequest={!!activeRequestData}
      />
    </div>
  );
}

function MobileBottomNav({ activeTab, setActiveTab, hasActiveRequest }) {
  const tabs = [
    { id: 'home', label: 'Home', emoji: '🏠' },
    { id: 'request', label: 'Request', emoji: '🚨' },
    { id: 'tracker', label: 'Live', emoji: '📡', badge: hasActiveRequest },
    { id: 'donor-portal', label: 'Donate', emoji: '❤️' },
    { id: 'banks', label: 'Banks', emoji: '🏥' },
  ];

  return (
    <nav className="bottom-nav lg:hidden flex items-stretch justify-around px-2 pt-2 pb-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => setActiveTab(tab.id)}
          className={`flex flex-col items-center justify-center gap-0.5 py-1.5 px-3 rounded-xl transition-all relative ${
            activeTab === tab.id || (activeTab === '' && tab.id === 'home')
              ? 'text-white'
              : 'text-slate-500'
          }`}
        >
          {(activeTab === tab.id || (activeTab === '' && tab.id === 'home')) && (
            <div className="absolute -top-1 w-6 h-0.5 bg-blood-500 rounded-full" />
          )}
          <span className="text-lg">{tab.emoji}</span>
          <span className="text-[9px] font-bold tracking-wider">{tab.label}</span>
          {tab.badge && (
            <span className="absolute top-0.5 right-1 w-2 h-2 bg-red-500 rounded-full animate-ping" />
          )}
        </button>
      ))}
    </nav>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <HashRouter>
        <GPSProvider>
          <AuthProvider>
            <AppContent />
          </AuthProvider>
        </GPSProvider>
      </HashRouter>
    </ToastProvider>
  );
}
