import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldAlert, CheckCircle, Navigation, MapPin, Clock } from 'lucide-react';
import { respondDonorAction, withdrawDonorMatch } from '../services/api';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import L from 'leaflet';
import DonorTrackingView from './DonorTrackingView';

const hospitalIcon = L.divIcon({
  className: 'custom-leaflet-marker',
  html: `<div style="background-color: #e50914; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #050505; box-shadow: 0 0 16px #e50914;"></div>`,
  iconSize: [14, 14],
  iconAnchor: [7, 7]
});

export default function IncomingEmergencyOverlay({ matchId, requestDetails, onClose }) {
  const [status, setStatus] = useState('IDLE'); // IDLE, ACCEPTED, WITHDRAWN
  const [countdown, setCountdown] = useState(60);

  const [isAccepting, setIsAccepting] = useState(false);
  const [isDeclining, setIsDeclining] = useState(false);
  const [isWithdrawing, setIsWithdrawing] = useState(false);
  const [showWithdrawConfirm, setShowWithdrawConfirm] = useState(false);
  const [withdrawError, setWithdrawError] = useState(null);

  useEffect(() => {
    let timer;
    if (status === 'IDLE') {
      setCountdown(60);
      timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(timer);
            handleDecline();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [status]);

  const handleAccept = async () => {
    if (isAccepting || isDeclining || isWithdrawing) return;
    setIsAccepting(true);
    try {
      if (!matchId) throw new Error("Invalid match ID.");
      await respondDonorAction(matchId, 'ACCEPTED');
      setStatus('ACCEPTED');
    } catch (e) {
      console.error("Accept failed on backend:", e);
      alert(e.message || "Failed to accept the request. It may have already been fulfilled or cancelled.");
      onClose();
    } finally {
      setIsAccepting(false);
    }
  };

  const handleWithdraw = async () => {
    if (isWithdrawing) return;
    setIsWithdrawing(true);
    setWithdrawError(null);
    try {
      if (!matchId) throw new Error("Invalid match ID.");
      await withdrawDonorMatch(matchId);
      setStatus('WITHDRAWN');
      setTimeout(() => {
        onClose();
      }, 3000);
    } catch (e) {
      console.error("Withdraw failed:", e);
      setWithdrawError(e.message || "Failed to withdraw.");
    } finally {
      setIsWithdrawing(false);
    }
  };

  const handleDecline = async () => {
    if (isAccepting || isDeclining || isWithdrawing) return;
    setIsDeclining(true);
    try {
      if (matchId) {
        await respondDonorAction(matchId, 'DECLINED');
      }
      onClose();
    } catch (e) {
      console.error("Decline failed on backend:", e);
      onClose();
    } finally {
      setIsDeclining(false);
    }
  };

  const lat = requestDetails?.latitude || requestDetails?.location?.lat;
  const lon = requestDetails?.longitude || requestDetails?.location?.lng;
  const hasValidLocation = lat != null && lon != null && isFinite(lat) && isFinite(lon);
  const position = hasValidLocation ? [lat, lon] : null;

  return (
    <AnimatePresence>
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

              {hasValidLocation ? (
                <div className="h-40 w-full relative bg-[#111] overflow-hidden">
                  <MapContainer center={position} zoom={13} zoomControl={false} scrollWheelZoom={false} dragging={false} className="w-full h-full">
                    <TileLayer
                      url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
                      attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                    />
                    <Marker position={position} icon={hospitalIcon} />
                  </MapContainer>
                  <div className="absolute inset-0 bg-gradient-to-t from-[#0A0A0C] via-transparent to-transparent pointer-events-none z-[400]" />
                  <div className="absolute inset-0 border-b border-white/5 pointer-events-none z-[400]" />
                  <div className="absolute top-4 left-4 z-[400] bg-[#0A0A0C]/80 backdrop-blur border border-white/10 rounded-full px-3 py-1 flex items-center gap-1.5 shadow-lg">
                    <ShieldAlert className="w-3.5 h-3.5 text-blood-500" />
                    <span className="text-xs font-bold text-white tracking-widest uppercase">URGENT REQUEST</span>
                  </div>
                </div>
              ) : (
                <div className="h-24 w-full bg-[#111] flex items-center justify-center border-b border-white/5 relative">
                  <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-blood-500/10 via-transparent to-transparent" />
                  <ShieldAlert className="w-8 h-8 text-blood-500/50" />
                </div>
              )}

              <div className="p-6 relative">
                <div className="absolute -top-6 right-6 w-12 h-12 bg-[#0A0A0C] border border-white/10 rounded-full flex items-center justify-center shadow-lg z-10">
                  <div className="text-sm font-black text-white">{countdown}s</div>
                </div>

                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-2xl font-black text-white leading-none">
                      {requestDetails?.blood_type || 'Unknown'} Required
                    </h2>
                    <p className="text-blood-400 font-medium text-sm mt-1">{requestDetails?.units || 1} Units • Urgent</p>
                  </div>
                </div>

                <div className="space-y-4 mb-8">
                  <div className="flex gap-3">
                    <div className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center shrink-0">
                      <MapPin className="w-4 h-4 text-white" />
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 font-medium uppercase tracking-wider mb-0.5">Location</p>
                      <p className="text-sm text-gray-200 leading-tight">
                        {requestDetails?.location_name || requestDetails?.location || 'Unknown Location'}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={handleDecline}
                    disabled={isDeclining || isAccepting}
                    className="w-full px-4 py-3.5 rounded-xl border-2 border-white/10 text-white font-bold text-sm
                             hover:bg-white/5 transition active:scale-[0.98] disabled:opacity-50"
                  >
                    {isDeclining ? 'Declining...' : 'Decline'}
                  </button>
                  <button
                    onClick={handleAccept}
                    disabled={isDeclining || isAccepting}
                    className="w-full px-4 py-3.5 rounded-xl bg-blood-500 text-white font-bold text-sm
                             hover:bg-blood-600 transition shadow-[0_0_20px_rgba(229,9,20,0.3)] active:scale-[0.98] disabled:opacity-50
                             flex items-center justify-center gap-2"
                  >
                    {isAccepting ? (
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    ) : (
                      <>Accept Mission <Navigation className="w-4 h-4" /></>
                    )}
                  </button>
                </div>
                <p className="text-center text-[10px] text-gray-500 mt-4 leading-relaxed">
                  By accepting, you commit to travelling to the location within the requested time.
                  The requester will be notified immediately.
                </p>
              </div>
            </>
          ) : status === 'WITHDRAWN' ? (
             <div className="p-8 text-center bg-[#050505]">
                <ShieldAlert className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
                <h2 className="text-2xl font-black text-white mb-2">Match Withdrawn</h2>
                <p className="text-sm text-gray-400 mb-6">You have successfully withdrawn from this emergency request.</p>
             </div>
          ) : (
            <div className="flex flex-col h-[80vh] max-h-[800px] w-full bg-[#050505] relative overflow-hidden">
               {showWithdrawConfirm && (
                <div className="absolute inset-0 z-50 bg-black/80 backdrop-blur-md flex flex-col items-center justify-center p-6 text-center">
                  <ShieldAlert className="w-12 h-12 text-yellow-500 mb-4" />
                  <h3 className="text-xl font-bold text-white mb-2">Confirm Withdrawal</h3>
                  <p className="text-gray-400 text-sm mb-8 max-w-[280px]">
                    Are you sure you need to withdraw? The requester is currently waiting for you.
                  </p>

                  {withdrawError && (
                    <div className="w-full bg-red-900/40 border border-red-500/50 p-3 rounded-xl mb-4">
                      <p className="text-red-200 text-xs text-left">{withdrawError}</p>
                    </div>
                  )}

                  <div className="flex flex-col gap-3 w-full max-w-[280px]">
                    <button
                      onClick={handleWithdraw}
                      disabled={isWithdrawing}
                      className="w-full py-3.5 bg-yellow-500 hover:bg-yellow-600 text-black font-bold rounded-xl disabled:opacity-50"
                    >
                      {isWithdrawing ? 'Withdrawing...' : 'Yes, Withdraw'}
                    </button>
                    <button
                      onClick={() => { setShowWithdrawConfirm(false); setWithdrawError(null); }}
                      disabled={isWithdrawing}
                      className="w-full py-3.5 bg-white/10 hover:bg-white/20 text-white font-bold rounded-xl transition"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              <div className="p-4 border-b border-white/10 bg-[#0A0A0C] flex items-center justify-between z-10 relative">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-emerald-500/20 flex items-center justify-center shrink-0 border border-emerald-500/30">
                    <CheckCircle className="w-5 h-5 text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="font-bold text-white leading-tight">Mission Accepted</h3>
                    <p className="text-xs text-emerald-400">Navigating to hospital</p>
                  </div>
                </div>
                <button
                  onClick={() => setShowWithdrawConfirm(true)}
                  className="px-3 py-1.5 rounded-lg border border-white/10 text-xs font-bold text-gray-400 hover:text-white hover:bg-white/5 transition"
                >
                  Withdraw
                </button>
              </div>
              <div className="flex-1 relative w-full h-full">
                <DonorTrackingView
                   matchId={matchId}
                   requestDetails={requestDetails}
                />
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
