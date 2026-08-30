import React, { useState, useEffect, useCallback, createContext, useContext, useRef } from 'react';
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
import { SectionErrorBoundary } from './components/ErrorBoundary';
import { requestFirebaseNotificationPermission, subscribeToForegroundMessages } from './firebase';
import { registerDeviceToken, getBaseWsUrl } from './services/api';
import IncomingEmergencyOverlay from './components/IncomingEmergencyOverlay';

// ── GPS State Model ─────────────────────────────────────────────
export const GPS_STATES = {
  IDLE: 'IDLE',
  REQUESTING: 'REQUESTING',
  AVAILABLE: 'AVAILABLE',
  DENIED: 'DENIED',
  UNAVAILABLE: 'UNAVAILABLE',
  TIMEOUT: 'TIMEOUT',
  ERROR: 'ERROR',
};

const GPSContext = createContext(null);
export function useGPS() {
  return useContext(GPSContext);
}

function isValidCoordinate(lat, lon) {
  return (
    typeof lat === 'number' && typeof lon === 'number' &&
    isFinite(lat) && isFinite(lon) &&
    lat >= -90 && lat <= 90 &&
    lon >= -180 && lon <= 180
  );
}

function GPSProvider({ children }) {
  const [location, setLocation] = useState(null);
  const [gpsState, setGpsState] = useState(GPS_STATES.IDLE);
  const [errorMessage, setErrorMessage] = useState(null);

  const refresh = useCallback(async () => {
    setGpsState(GPS_STATES.REQUESTING);
    setErrorMessage(null);
    try {
      const pos = await getCurrentPosition();
      if (isValidCoordinate(pos.latitude, pos.longitude)) {
        setLocation(pos);
        setGpsState(GPS_STATES.AVAILABLE);
        setErrorMessage(null);
      } else {
        setLocation(null);
        setGpsState(GPS_STATES.ERROR);
        setErrorMessage('Invalid coordinates received from device.');
      }
    } catch (err) {
      setLocation(null);
      if (err.code === 1) {
        // GeolocationPositionError.PERMISSION_DENIED
        setGpsState(GPS_STATES.DENIED);
        setErrorMessage('Location permission was denied.');
      } else if (err.code === 2) {
        // GeolocationPositionError.POSITION_UNAVAILABLE
        setGpsState(GPS_STATES.UNAVAILABLE);
        setErrorMessage('Position unavailable. Check your device location settings.');
      } else if (err.code === 3) {
        // GeolocationPositionError.TIMEOUT
        setGpsState(GPS_STATES.TIMEOUT);
        setErrorMessage('Location request timed out. Try again.');
      } else {
        setGpsState(GPS_STATES.ERROR);
        setErrorMessage(err.message || 'Location unavailable.');
      }
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <GPSContext.Provider value={{ location, gpsState, errorMessage, refresh }}>
      {children}
    </GPSContext.Provider>
  );
}

// ── Main App ────────────────────────────────────────────────────
function AppContent() {
  const { user, showAuthModal, setShowAuthModal } = useAuth();
  const [activeRequestData, setActiveRequestData] = useState(null);
  const [isDonorPortalOpen, setIsDonorPortalOpen] = useState(false);
  const [simulatedMatchId, setSimulatedMatchId] = useState(null);
  const [donorSelectedRequest, setDonorSelectedRequest] = useState(null);
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

  // ── FCM Token Registration ───────────────────────────────────────
  const hasRegisteredFCM = useRef(false);
  useEffect(() => {
    if (!user) {
      hasRegisteredFCM.current = false;
      return;
    }
    // Only register once per session to avoid duplicate requests
    if (hasRegisteredFCM.current) return;
    let isMounted = true;
    const registerFCM = async () => {
      try {
        const token = await requestFirebaseNotificationPermission();
        if (token && isMounted) {
          await registerDeviceToken(token, 'web');
          hasRegisteredFCM.current = true;
          console.log('[App] Successfully registered FCM device token.');
        }
      } catch (err) {
        console.warn('[App] FCM token registration failed or denied:', err);
      }
    };

    registerFCM();
    return () => { isMounted = false; };
  }, [user]);

  // ── Unified Incoming Emergency Handler ─────────────────────────────
  const [incomingEmergency, setIncomingEmergency] = useState(null);

  const handleIncomingEmergency = useCallback((payloadData) => {
    // Only show to Donors (requesters should not receive or see this)
    if (user?.role === 'REQUESTER') return;

    // Normalize payload
    if (payloadData && payloadData.type === 'EMERGENCY_REQUEST') {
      const matchId = payloadData.match_id;
      const requestId = payloadData.request_id;
      if (!matchId) return;

      const requestDetails = {
        id: requestId,
        blood_type: payloadData.blood_type || 'Unknown',
        units: payloadData.units || 1,
        location_name: payloadData.location_name || 'Hospital',
        latitude: parseFloat(payloadData.latitude),
        longitude: parseFloat(payloadData.longitude),
      };

      setIncomingEmergency({ matchId, requestDetails });
    }
  }, [user]);

  // 1. Listen for background notification clicks from Service Worker
  useEffect(() => {
    const handleServiceWorkerMessage = (event) => {
      if (event.data && event.data.type === 'NOTIFICATION_CLICKED') {
        console.log('[App] Received background notification click data:', event.data.data);
        handleIncomingEmergency(event.data.data);
      }
    };
    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.addEventListener('message', handleServiceWorkerMessage);
    }
    return () => {
      if ('serviceWorker' in navigator) {
        navigator.serviceWorker.removeEventListener('message', handleServiceWorkerMessage);
      }
    };
  }, [handleIncomingEmergency]);

  // 1b. Check URL params for background click navigation
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    const incomingReq = searchParams.get('incoming_request');
    const incomingMatch = searchParams.get('match_id');
    if (incomingReq && incomingMatch) {
      // Clean up URL
      const newUrl = window.location.pathname;
      window.history.replaceState({}, '', newUrl);
      // Construct a payload
      handleIncomingEmergency({
        type: 'EMERGENCY_REQUEST',
        request_id: incomingReq,
        match_id: incomingMatch,
      });
    }
  }, [location.search, handleIncomingEmergency]);

  // 2. Listen for FCM Foreground Messages
  useEffect(() => {
    if (!user) return;
    let unsubscribe = null;
    let isMounted = true;

    subscribeToForegroundMessages((payload) => {
      if (!isMounted) return;
      console.log("[App] Foreground FCM message received:", payload);
      if (payload.data) {
        handleIncomingEmergency(payload.data);
      }
    }).then((unsub) => {
      if (isMounted) {
        unsubscribe = unsub;
      } else if (unsub) {
        unsub();
      }
    });

    return () => {
      isMounted = false;
      if (unsubscribe) unsubscribe();
    };
  }, [user, handleIncomingEmergency]);

  // 3. Fallback Authenticated User WebSocket Connection
  useEffect(() => {
    if (!user) return;
    const token = localStorage.getItem('token');
    if (!token) return;

    let ws = null;
    let reconnectTimeout = null;
    const connectUserWebSocket = () => {
      const WS_BASE = getBaseWsUrl();
      const wsUrl = `${WS_BASE}/api/v1/ws/user?token=${token}`;
      console.log('[App] User WS connecting to:', wsUrl.replace(/token=.*/, 'token=***'));
      ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('[App] User WS connection OPENED');
      };

      ws.onerror = (err) => {
        console.error('[App] User WS connection ERROR:', err);
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          console.log('[App] User WS message received, type:', payload.type);
          if (payload.type === 'INCOMING_EMERGENCY') {
            console.log("[App] WebSocket Fallback INCOMING_EMERGENCY received:", payload.data);
            handleIncomingEmergency(payload.data);
          }
        } catch (err) {
          console.error("[App] User WS parsing error:", err);
        }
      };

      ws.onclose = (event) => {
        console.log('[App] User WS connection CLOSED, code:', event.code, 'reason:', event.reason);
        // Simple reconnect logic for fallback
        reconnectTimeout = setTimeout(connectUserWebSocket, 5000);
      };
    };

    connectUserWebSocket();
    return () => {
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      if (ws) {
        ws.onclose = null; // prevent reconnect loop on unmount
        ws.close();
      }
    };
  }, [user, handleIncomingEmergency]);

  const isNavigatingRef = useRef(false);
  const handleSetActiveTab = useCallback((tab) => {
    if (isNavigatingRef.current) return;
    isNavigatingRef.current = true;
    if (tab === 'home') navigate('/');
    else navigate(`/${tab}`);
    setTimeout(() => { isNavigatingRef.current = false; }, 300);
  }, [navigate]);

  // Auto-close the donor portal modal on any route change so it doesn't
  // block the tracker screen after navigating from a previous demo session.
  useEffect(() => {
    setIsDonorPortalOpen(false);
    setSimulatedMatchId(null);
    setDonorSelectedRequest(null);
  }, [location.pathname]);

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

      <main className="flex-1 w-full mx-auto relative min-h-0 overflow-y-auto pb-[env(safe-area-inset-bottom)]">

        <AnimatePresence mode="wait">
          <Routes location={location} key={location.pathname}>
            <Route path="/" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24 lg:pb-8"
              >
                <SectionErrorBoundary onRetry={() => window.location.reload()}>
                  <ActionHubHome
                    onNavigateTab={handleSetActiveTab}
                    onRequestSubmitted={handleRequestSubmitted}
                  />
                </SectionErrorBoundary>
              </motion.div>
            } />
            
            <Route path="/request" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24 lg:pb-8"
              >
                <SectionErrorBoundary onRetry={() => window.location.reload()}>
                  <EmergencyRequestForm onRequestSubmitted={handleRequestSubmitted} />
                </SectionErrorBoundary>
              </motion.div>
            } />
            
            <Route path="/tracker/:id?" element={
              <motion.div
                initial={{ opacity: 0, scale: 1.02 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.98 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
                className="absolute inset-0 z-50 bg-[#050505]"
              >
                <SectionErrorBoundary onRetry={() => window.location.reload()}>
                  <RequesterDashboard
                    requestId={activeRequestData?.request?.id}
                    onSimulateDonorAction={handleSimulateDonorAction}
                  />
                </SectionErrorBoundary>
              </motion.div>
            } />

            
            <Route path="/donor-portal" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24 lg:pb-8"
              >
                <SectionErrorBoundary onRetry={() => window.location.reload()}>
                  <DonorPortalHub
                    onSimulateAlert={(req) => {
                      if (req && typeof req === 'object') {
                        setDonorSelectedRequest(req);
                      }
                      setIsDonorPortalOpen(true);
                    }}
                  />
                </SectionErrorBoundary>
              </motion.div>
            } />
            
            <Route path="/banks" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24 lg:pb-8"
              >
                <SectionErrorBoundary onRetry={() => window.location.reload()}>
                  <HospitalInventoryView />
                </SectionErrorBoundary>
              </motion.div>
            } />
            
            <Route path="/audit/:id?" element={
              <motion.div
                initial={{ opacity: 0, y: 15, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -15, filter: 'blur(4px)' }}
                transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
                className="w-full h-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 pb-24 lg:pb-8"
              >
                <SectionErrorBoundary onRetry={() => window.location.reload()}>
                  <AuditLogViewer activeRequestId={activeRequestData?.request?.id} />
                </SectionErrorBoundary>
              </motion.div>
            } />
          </Routes>
        </AnimatePresence>
      </main>

      <DonorPortalModal
        isOpen={isDonorPortalOpen}
        onClose={() => {
          setIsDonorPortalOpen(false);
          setDonorSelectedRequest(null);
        }}
        activeMatchId={simulatedMatchId}
        requestDetails={donorSelectedRequest || activeRequestData?.request}
      />

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
      />

      {incomingEmergency && (
        <IncomingEmergencyOverlay
          matchId={incomingEmergency.matchId}
          requestDetails={incomingEmergency.requestDetails}
          onClose={() => setIncomingEmergency(null)}
        />
      )}

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
    <nav className="bottom-nav lg:hidden flex items-stretch justify-around px-2 pt-2 pb-1" style={{ paddingBottom: 'env(safe-area-inset-bottom, 8px)' }}>
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
