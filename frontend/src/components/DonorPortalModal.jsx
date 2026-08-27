import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert, CheckCircle, Navigation, MapPin, Clock } from 'lucide-react';
import { respondDonorAction, withdrawDonorMatch, getRequestMatches } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import DonorTrackingView from './DonorTrackingView';

const hospitalIcon = L.divIcon({
  className: 'custom-leaflet-marker',
  html: `<div style="background-color: #e50914; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #050505; box-shadow: 0 0 16px #e50914;"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7]
});

export default function DonorPortalModal({ isOpen, onClose, activeMatchId, requestDetails }) {
  const [status, setStatus] = useState('IDLE'); // IDLE, ACCEPTED
  const [countdown, setCountdown] = useState(45);
  const { user } = useAuth();
  
  useEffect(() => {
    if (isOpen && status === 'IDLE') {
      setCountdown(45);
      const timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(timer);
            handleDecline(); // Auto-decline on timeout
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [isOpen, status]);

  const [isWithdrawing, setIsWithdrawing] = useState(false);
  const [showWithdrawConfirm, setShowWithdrawConfirm] = useState(false);
  const [withdrawError, setWithdrawError] = useState(null);

  const handleAccept = async () => {
    try {
      let matchIdToAccept = activeMatchId;

      if (!matchIdToAccept && requestDetails?.id) {
        // We need to fetch the match for this donor
        const matches = await getRequestMatches(requestDetails.id);
        const myMatch = matches.find(m => m.donor_name === user?.name);
        if (myMatch && myMatch.match_id) {
          matchIdToAccept = myMatch.match_id;
        }
      }

      if (matchIdToAccept && matchIdToAccept.startsWith('match-')) {
        await respondDonorAction(matchIdToAccept, 'ACCEPTED');
      } else {
        await new Promise(r => setTimeout(r, 400)); // Simulate network for demo if no match found
      }
      setStatus('ACCEPTED');
      // Intentionally keeping modal open so donor can withdraw or see tracking.
    } catch (e) {
      console.error("Accept failed on backend:", e);
      alert(e.message || "Failed to accept the request. It may have already been fulfilled or cancelled.");
      // Do not transition to ACCEPTED state locally if backend failed
      onClose();
    }
  };

  const handleWithdraw = async () => {
    if (isWithdrawing) return;
    setIsWithdrawing(true);
    setWithdrawError(null);
    try {
      if (activeMatchId && activeMatchId.startsWith('match-')) {
        await withdrawDonorMatch(activeMatchId);
      } else {
        await new Promise(r => setTimeout(r, 800));
      }
      setStatus('WITHDRAWN');
      setTimeout(() => {
        onClose();
        setStatus('IDLE');
        setShowWithdrawConfirm(false);
      }, 3000);
    } catch (e) {
      console.error("Withdraw failed:", e);
      setWithdrawError(e.message || "Failed to withdraw.");
    } finally {
      setIsWithdrawing(false);
    }
  };

  const handleDecline = async () => {
    try {
      if (activeMatchId && activeMatchId.startsWith('match-')) {
        await respondDonorAction(activeMatchId, 'DECLINED');
      }
      onClose();
      setStatus('IDLE');
    } catch (e) {
      console.error("[Demo Resilience] Decline failed on backend:", e);
      onClose();
      setStatus('IDLE');
    }
  };

  // Only use real coordinates — never fake fallback
  const lat = requestDetails?.latitude;
  const lon = requestDetails?.longitude;
  const hasValidLocation = lat != null && lon != null && isFinite(lat) && isFinite(lon);
  const position = hasValidLocation ? [lat, lon] : null;
  
  // Approximate distance (in reality would be passed from backend match data, simulate here as ~3km)
  const estDistance = "3.2"; 

  return (
    <AnimatePresence>
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-[#050505]/90 backdrop-blur-md">
          <motion.div
            initial={{ scale: 0.9, opacity: 0, y: 20 }}
            animate={{ scale: 1, opacity: 1, y: 0 }}
            exit={{ scale: 0.9, opacity: 0, y: 20 }}
            transition={{ type: "spring", damping: 25, stiffness: 300 }}
            className="w-full max-w-md bg-[#0A0A0C] border border-white/10 rounded-3xl overflow-hidden shadow-[0_20px_60px_rgba(0,0,0,0.8)] relative"
          >
            {status === 'IDLE' ? (
              <>
                {/* Red pulsing header line */}
                <div className="absolute top-0 left-0 right-0 h-1 bg-blood-500/20 overflow-hidden z-10">
                    <motion.div className="h-full bg-blood-500" initial={{ x: '-100%' }} animate={{ x: '100%' }} transition={{ repeat: Infinity, duration: 1, ease: "linear" }} />
                </div>
                
                {/* Mini Map Header — only shown when coordinates are available */}
                {hasValidLocation ? (
                  <div className="h-40 w-full relative z-0">
                    <MapContainer center={position} zoom={13} zoomControl={false} scrollWheelZoom={false} dragging={false} className="w-full h-full">
                      <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
                      <Marker position={position} icon={hospitalIcon} />
                    </MapContainer>
                    {/* Gradient overlay to fade map into content */}
                    <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0C] via-[#0A0A0C]/40 to-transparent pointer-events-none z-10" />
                    
                    {/* Floating Timer */}
                    <div className="absolute top-4 right-4 z-20 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-3 py-1 flex items-center gap-2">
                      <Clock className={`w-3.5 h-3.5 ${countdown <= 10 ? 'text-blood-500 animate-pulse' : 'text-amber-400'}`} />
                      <span className={`text-xs font-black tabular-nums ${countdown <= 10 ? 'text-blood-500' : 'text-amber-400'}`}>
                        00:{countdown.toString().padStart(2, '0')}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div className="h-32 w-full relative z-0 flex items-center justify-center bg-white/3">
                    <div className="text-center">
                      <div className="text-white/20 text-xs font-bold">Location Unavailable</div>
                      <div className="text-white/10 text-[10px] mt-1">Map cannot be displayed</div>
                    </div>
                    {/* Floating Timer */}
                    <div className="absolute top-4 right-4 z-20 bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-3 py-1 flex items-center gap-2">
                      <Clock className={`w-3.5 h-3.5 ${countdown <= 10 ? 'text-blood-500 animate-pulse' : 'text-amber-400'}`} />
                      <span className={`text-xs font-black tabular-nums ${countdown <= 10 ? 'text-blood-500' : 'text-amber-400'}`}>
                        00:{countdown.toString().padStart(2, '0')}
                      </span>
                    </div>
                  </div>
                )}

                <div className="px-6 pb-6 pt-2 relative z-10 -mt-6">
                  <div className="flex flex-col items-center text-center">
                    <div className="w-14 h-14 rounded-full bg-blood-500/20 flex items-center justify-center mb-3 shadow-[0_0_20px_rgba(229,9,20,0.4)] border border-blood-500/30 backdrop-blur-md">
                      <ShieldAlert className="w-7 h-7 text-blood-500 animate-pulse" />
                    </div>
                    <h2 className="text-xl font-black text-white uppercase tracking-tight">Emergency Match</h2>
                    <p className="text-sm text-[#86868B] mt-1">A patient nearby urgently needs <span className="text-blood-500 font-bold">{requestDetails?.blood_type || 'O-'}</span>.</p>
                    
                    <div className="w-full grid grid-cols-2 gap-3 mt-5">
                      <div className="bg-white/5 rounded-xl p-3 border border-white/5 text-left">
                          <span className="text-[10px] text-[#86868B] uppercase font-bold tracking-wider block mb-1">Location</span>
                          <span className="text-xs font-bold text-white flex items-center gap-1 leading-tight"><MapPin className="w-3 h-3 text-blue-400 shrink-0"/> {requestDetails?.hospital_name || 'Hospital'}</span>
                      </div>
                      <div className="bg-white/5 rounded-xl p-3 border border-white/5 text-left">
                          <span className="text-[10px] text-[#86868B] uppercase font-bold tracking-wider block mb-1">Distance</span>
                          <span className="text-xs font-bold text-white flex items-center gap-1 leading-tight"><Navigation className="w-3 h-3 text-emerald-400 shrink-0"/> {estDistance} km away</span>
                      </div>
                    </div>
                    
                    <div className="flex gap-3 w-full mt-6">
                      <button onClick={handleDecline} className="flex-1 py-3.5 rounded-xl bg-white/5 hover:bg-white/10 border border-white/5 text-[#86868B] hover:text-white font-bold transition-all text-sm uppercase tracking-wider">
                        Decline
                      </button>
                      <button onClick={handleAccept} className="flex-1 py-3.5 rounded-xl bg-blood-500 text-white font-black shadow-[0_0_20px_rgba(229,9,20,0.4)] transition-all text-sm uppercase tracking-wider animate-urgency-pulse hover:bg-blood-600 hover:scale-[1.02]">
                        Accept
                      </button>
                    </div>
                  </div>
                </div>
              </>
            ) : status === 'ACCEPTED' ? (
              <DonorTrackingView
                requestDetails={requestDetails}
                activeMatchId={activeMatchId}
                onWithdraw={handleWithdraw}
                isWithdrawing={isWithdrawing}
                withdrawError={withdrawError}
                onClose={() => {
                  onClose();
                  setStatus('IDLE');
                }}
              />
            ) : (
              <div className="flex flex-col items-center text-center py-12 px-6">
                <div className="w-20 h-20 rounded-full bg-gray-500/20 border-2 border-gray-500 flex items-center justify-center mb-6">
                  <CheckCircle className="w-10 h-10 text-gray-400" />
                </div>
                <h2 className="text-2xl font-black text-gray-400 uppercase tracking-widest">Withdrawn</h2>
                <p className="text-sm text-[#86868B] mt-2 max-w-xs">You have successfully withdrawn from this emergency request.</p>
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
