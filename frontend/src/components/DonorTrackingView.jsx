/**
 * DonorTrackingView — Full-screen Uber-style live tracking view for the donor.
 *
 * Reuses the exact same infrastructure as the requester view:
 *  - useTrackingSession (WebSocket + state management)
 *  - TrackingMap (Leaflet map with smooth donor marker)
 *  - useSmoothPosition (rAF interpolation)
 *
 * Responsibilities:
 *  - Connect to the WebSocket for the active request
 *  - Display live tracking map with donor + hospital markers
 *  - Show ETA, distance, progress from the donor's perspective
 *  - Show simulation controls (Pause/Resume/Speed) in collapsible panel
 *  - Handle ARRIVED → DONATION lifecycle
 *  - Provide Withdraw button during tracking
 */
import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Navigation, MapPin, Clock, Activity, User, Droplets,
  ChevronDown, ChevronUp, X, AlertTriangle, CheckCircle,
  Wifi, WifiOff, Loader2
} from 'lucide-react';

import useTrackingSession from '../hooks/useTrackingSession';
import TrackingMap from './tracking/TrackingMap';
import ArrivalOverlay from './tracking/ArrivalOverlay';
import { updateDonorLocation, startDonation, completeDonation } from '../services/api';

// ── ETA formatter ──────────────────────────────────────────────────────────
const formatEta = (seconds) => {
  if (seconds === null || seconds === undefined) return '--:--';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
};

// ── Status label ───────────────────────────────────────────────────────────
const getStatusInfo = (state) => {
  switch (state) {
    case 'DONOR_ACCEPTED': return { label: 'Connecting...', color: 'text-blue-400', bg: 'bg-blue-500/15', border: 'border-blue-500/30' };
    case 'TRACKING':       return { label: 'En Route',      color: 'text-emerald-400', bg: 'bg-emerald-500/15', border: 'border-emerald-500/30' };
    case 'ARRIVING':       return { label: 'Almost There',  color: 'text-amber-400', bg: 'bg-amber-500/15', border: 'border-amber-500/30' };
    case 'ARRIVED':        return { label: 'Arrived',       color: 'text-emerald-300', bg: 'bg-emerald-500/15', border: 'border-emerald-500/30' };
    case 'DONATION_STARTED':    return { label: 'Donating',      color: 'text-rose-400', bg: 'bg-rose-500/15', border: 'border-rose-500/30' };
    case 'DONATION_COMPLETED':  return { label: 'Complete',      color: 'text-emerald-300', bg: 'bg-emerald-500/15', border: 'border-emerald-500/30' };
    case 'CLOSED':         return { label: 'Completed',     color: 'text-white/60', bg: 'bg-white/5', border: 'border-white/10' };
    case 'CANCELLED':      return { label: 'Cancelled',     color: 'text-red-400', bg: 'bg-red-500/15', border: 'border-red-500/30' };
    default:               return { label: state || '...', color: 'text-gray-400', bg: 'bg-white/5', border: 'border-white/10' };
  }
};

// ── Connection indicator ───────────────────────────────────────────────────
const ConnectionDot = React.memo(function ConnectionDot({ state }) {
  const isLive = state === 'connected';
  return (
    <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-black/50 backdrop-blur-md border border-white/5">
      {isLive
        ? <><Wifi className="w-3 h-3 text-emerald-500" /><span className="text-[9px] text-emerald-400 font-bold">LIVE</span></>
        : <><WifiOff className="w-3 h-3 text-amber-500" /><span className="text-[9px] text-amber-400 font-bold">{state?.toUpperCase()}</span></>
      }
    </div>
  );
});

// ── Withdraw confirmation ──────────────────────────────────────────────────
const WithdrawConfirm = React.memo(function WithdrawConfirm({
  visible, onConfirm, onDismiss, isLoading
}) {
  if (!visible) return null;
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
    >
      <motion.div
        initial={{ scale: 0.9, y: 20 }}
        animate={{ scale: 1, y: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 25 }}
        className="max-w-sm w-full mx-4 rounded-[24px] bg-[#0A0A0C]/96
                   border border-white/10 shadow-2xl overflow-hidden"
      >
        <div className="h-1.5 bg-gradient-to-r from-amber-600 via-red-500 to-amber-600" />
        <div className="p-6 flex flex-col items-center gap-5">
          <div className="w-16 h-16 rounded-full bg-red-500/15 border-2 border-red-400/40
                          flex items-center justify-center">
            <AlertTriangle className="w-8 h-8 text-red-400" />
          </div>
          <div className="text-center">
            <h3 className="text-lg font-black text-white">Withdraw?</h3>
            <p className="text-sm text-white/40 mt-2 leading-relaxed">
              Are you sure you want to withdraw? The system will need to find another donor.
            </p>
          </div>
          <div className="w-full flex gap-3">
            <button
              onClick={onDismiss}
              disabled={isLoading}
              className="flex-1 py-3 rounded-xl bg-white/8 text-white/70 text-sm font-bold
                         hover:bg-white/12 transition-colors disabled:opacity-40"
            >
              Stay
            </button>
            <button
              onClick={onConfirm}
              disabled={isLoading}
              className="flex-1 py-3 rounded-xl bg-red-600 text-white text-sm font-bold
                         hover:bg-red-500 transition-colors disabled:opacity-60
                         flex items-center justify-center gap-2"
            >
              {isLoading
                ? <><Loader2 className="w-4 h-4 animate-spin" /> Withdrawing…</>
                : 'Confirm Withdraw'}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
});

// ── Completed overlay ──────────────────────────────────────────────────────
const CompletedOverlay = React.memo(function CompletedOverlay({ onClose }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      className="absolute inset-0 z-30 flex items-center justify-center bg-[#050505]/90 backdrop-blur-md"
    >
      <div className="max-w-sm w-full mx-4 rounded-[32px] bg-[#0A0A0C]/96
                      border border-emerald-500/20 shadow-2xl overflow-hidden text-center">
        <div className="h-1.5 bg-gradient-to-r from-emerald-600 via-emerald-400 to-emerald-600" />
        <div className="p-8 flex flex-col items-center gap-6">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ type: 'spring', stiffness: 200, delay: 0.15 }}
            className="w-20 h-20 rounded-full bg-emerald-500/20 border-2 border-emerald-500/40
                       flex items-center justify-center"
          >
            <CheckCircle className="w-10 h-10 text-emerald-400" />
          </motion.div>
          <div>
            <h2 className="text-2xl font-black text-white">Thank You!</h2>
            <p className="text-sm text-white/40 mt-2">
              Your donation has been completed successfully. You helped save a life today.
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-full py-3.5 px-6 rounded-2xl bg-white text-black font-black text-sm
                       hover:bg-white/90 active:scale-[0.98] transition-all uppercase tracking-wider"
          >
            Done
          </button>
        </div>
      </div>
    </motion.div>
  );
});

// ── Main DonorTrackingView Component ───────────────────────────────────────
export default function DonorTrackingView({
  requestDetails,
  activeMatchId,
  onWithdraw,
  isWithdrawing,
  withdrawError,
  onClose,
}) {
  // Build requestData shape that useTrackingSession expects
  const requestData = useMemo(() => {
    if (!requestDetails) return null;
    return {
      request: {
        id: requestDetails.id,
        status: 'TRACKING', // We know we're post-acceptance
        latitude: requestDetails.latitude,
        longitude: requestDetails.longitude,
        hospital_name: requestDetails.hospital_name,
        blood_type: requestDetails.blood_type,
      }
    };
  }, [requestDetails]);

  // Connect to the same WebSocket as the requester
  const session = useTrackingSession(requestData);

  const {
    requestState,
    donorLocation,
    initialDonorPos,
    routeHistory,
    etaSeconds,
    distance,
    progress,
    acceptedDonor,
    connectionState,
    hospitalLoc,
    isTracking,
    isArrived,
    isDonationPhase,
    isClosed,
    isCancelled,
  } = session;

  // ── Withdraw state ───────────────────────────────────────────────
  const [showWithdrawConfirm, setShowWithdrawConfirm] = useState(false);
  
  const canWithdraw = ['TRACKING', 'ARRIVING', 'DONOR_ACCEPTED'].includes(requestState);

  const handleWithdrawConfirm = useCallback(() => {
    onWithdraw?.();
    setShowWithdrawConfirm(false);
  }, [onWithdraw]);

  // ── Dev controls ─────────────────────────────────────────────────
  const [showDevPanel, setShowDevPanel] = useState(false);
  const [gpsError, setGpsError] = useState(null);

  // ── Real Device GPS Tracking ────────────────────────────────────
  // When the donor is actively tracking, use navigator.geolocation.watchPosition
  // to send real coordinates to the backend.
  const watchIdRef = useRef(null);
  const lastSentRef = useRef(0); // Throttle: timestamp of last sent update
  const GPS_SEND_INTERVAL_MS = 3000; // Send at most every 3 seconds

  useEffect(() => {
    if (!isTracking || !requestDetails?.id) return;

    // Retrieve donor ID from match or profile
    const donorId = acceptedDonor?.donor_id || requestDetails?.donor_id;
    if (!donorId) return;

    if (!navigator.geolocation) {
      setGpsError('Geolocation is not supported by your browser.');
      return;
    }

    const onSuccess = (position) => {
      const now = Date.now();
      if (now - lastSentRef.current < GPS_SEND_INTERVAL_MS) return; // Throttle
      lastSentRef.current = now;

      const { latitude, longitude, accuracy, speed } = position.coords;
      setGpsError(null);

      // Send to backend (fire-and-forget, non-blocking)
      updateDonorLocation(
        donorId,
        latitude,
        longitude,
        requestDetails.id,
        speed ? (speed * 3.6) : 35.0, // m/s to km/h, fallback 35
        accuracy
      ).catch(err => console.warn('[DonorTracking] Location send failed:', err));
    };

    const onError = (err) => {
      switch (err.code) {
        case err.PERMISSION_DENIED:
          setGpsError('Location permission denied. Please enable location access.');
          break;
        case err.POSITION_UNAVAILABLE:
          setGpsError('Location unavailable. Check device settings.');
          break;
        case err.TIMEOUT:
          setGpsError('Location request timed out.');
          break;
        default:
          setGpsError('Unable to get location.');
      }
    };

    const id = navigator.geolocation.watchPosition(onSuccess, onError, {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 2000,
    });
    watchIdRef.current = id;

    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, [isTracking, requestDetails?.id, acceptedDonor?.donor_id, requestDetails?.donor_id]);

  const [isActionLoading, setIsActionLoading] = useState(false);

  const handleStartDonation = async () => {
    try {
      setIsActionLoading(true);
      const donorId = acceptedDonor?.donor_id || requestDetails?.donor_id;
      await startDonation(donorId, requestDetails.id);
    } catch (err) {
      console.error(err);
      alert(err.message || 'Failed to start donation');
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleCompleteDonation = async () => {
    try {
      setIsActionLoading(true);
      const donorId = acceptedDonor?.donor_id || requestDetails?.donor_id;
      await completeDonation(donorId, requestDetails.id);
    } catch (err) {
      console.error(err);
      alert(err.message || 'Failed to complete donation');
    } finally {
      setIsActionLoading(false);
    }
  };

  // Status info
  const statusInfo = useMemo(() => getStatusInfo(requestState), [requestState]);
  const etaDisplay = useMemo(() => formatEta(etaSeconds), [etaSeconds]);
  const progressPct = Math.min(100, Math.max(0, Math.round(progress * 100)));

  // Show completed overlay
  const showCompleted = isClosed;
  const showArrivalOverlay = isArrived || isDonationPhase;

  const hasValidLocation = hospitalLoc && 
                           hospitalLoc[0] != null && 
                           hospitalLoc[1] != null && 
                           !isNaN(parseFloat(hospitalLoc[0])) && 
                           !isNaN(parseFloat(hospitalLoc[1]));

  return (
    <div className="fixed inset-0 z-[100] bg-[#050505] flex flex-col">
      {/* ── TOP BAR ─────────────────────────────────────────────────── */}
      <div className="absolute top-0 left-0 right-0 z-20 p-4 flex items-center justify-between pointer-events-none">
        <div className="pointer-events-auto flex items-center gap-3">
          <button
            onClick={onClose}
            className="w-9 h-9 rounded-full bg-black/60 backdrop-blur-md border border-white/10
                       flex items-center justify-center hover:bg-white/10 transition-colors"
          >
            <X className="w-4 h-4 text-white" />
          </button>
          <div className={`px-3 py-1.5 rounded-full ${statusInfo.bg} border ${statusInfo.border} backdrop-blur-md
                          flex items-center gap-2`}>
            <Activity className={`w-3 h-3 ${statusInfo.color} animate-pulse`} />
            <span className={`text-[10px] font-black tracking-[0.15em] uppercase ${statusInfo.color}`}>
              {statusInfo.label}
            </span>
          </div>
        </div>
        <div className="pointer-events-auto">
          <ConnectionDot state={connectionState} />
        </div>
      </div>

      {/* ── MAP (full-bleed) ────────────────────────────────────────── */}
      <div className="flex-1 relative">
        {hasValidLocation ? (
          <TrackingMap
            hospitalLoc={hospitalLoc}
            donorLocation={donorLocation}
            initialDonorPos={initialDonorPos}
            routeHistory={routeHistory}
            nearbyMarkers={[]}
            isSearching={false}
            isTracking={isTracking}
            isDonorAccepted={true}
            requestState={requestState}
            acceptedDonor={acceptedDonor}
            etaSeconds={etaSeconds}
            distance={distance}
            hospitalName={requestDetails?.hospital_name}
          />
        ) : (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#111] z-[1]">
            <div className="text-center p-6 border border-white/10 rounded-2xl bg-white/5 backdrop-blur-md max-w-[280px]">
              <MapPin className="w-10 h-10 text-white/20 mx-auto mb-3" />
              <h3 className="text-white font-bold text-sm mb-1">Location Unavailable</h3>
              <p className="text-xs text-white/50 leading-relaxed">Map coordinates are temporarily unavailable. We are trying to reconnect.</p>
            </div>
          </div>
        )}

        {/* Map gradient overlays */}
        <div className="absolute top-0 left-0 right-0 h-28 bg-gradient-to-b from-[#050505] to-transparent pointer-events-none z-[5]" />
        <div className="absolute bottom-0 left-0 right-0 h-64 bg-gradient-to-t from-[#050505] via-[#050505]/80 to-transparent pointer-events-none z-[5]" />
      </div>

      {/* ── ARRIVAL OVERLAY ─────────────────────────────────────────── */}
      <ArrivalOverlay
        requestState={showArrivalOverlay ? requestState : null}
        acceptedDonor={acceptedDonor}
        onStartDonation={handleStartDonation}
        onCompleteDonation={handleCompleteDonation}
        isActionLoading={isActionLoading}
      />

      {/* ── COMPLETED OVERLAY ───────────────────────────────────────── */}
      <AnimatePresence>
        {showCompleted && <CompletedOverlay onClose={onClose} />}
      </AnimatePresence>

      {/* ── CANCELLED OVERLAY ───────────────────────────────────────── */}
      <AnimatePresence>
        {isCancelled && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="absolute inset-0 z-30 flex items-center justify-center bg-[#050505]/90 backdrop-blur-md"
          >
            <div className="text-center px-6">
              <AlertTriangle className="w-12 h-12 text-amber-500 mx-auto mb-4" />
              <h2 className="text-2xl font-black text-white mb-2">Request Cancelled</h2>
              <p className="text-sm text-white/40 mb-6">This emergency request has been cancelled.</p>
              <button onClick={onClose} className="px-8 py-3 bg-white text-black font-black rounded-2xl text-sm">
                Close
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── WITHDRAW CONFIRM ────────────────────────────────────────── */}
      <AnimatePresence>
        <WithdrawConfirm
          visible={showWithdrawConfirm}
          onConfirm={handleWithdrawConfirm}
          onDismiss={() => setShowWithdrawConfirm(false)}
          isLoading={isWithdrawing}
        />
      </AnimatePresence>

      {/* ── BOTTOM TRACKING SHEET ───────────────────────────────────── */}
      {!showCompleted && !isCancelled && !showArrivalOverlay && (
        <motion.div
          initial={{ y: 200, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="relative z-10 px-4 pb-6 pt-2"
        >
          <div className="max-w-md mx-auto rounded-[28px] bg-[#0A0A0C]/96 backdrop-blur-xl
                          border border-emerald-500/20 shadow-[0_0_48px_rgba(16,185,129,0.1)]
                          overflow-hidden">
            {/* Progress bar */}
            <div className="h-[3px] bg-white/5 overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-300"
                animate={{ width: `${progressPct}%` }}
                transition={{ duration: 1.2, ease: 'easeOut' }}
              />
            </div>

            <div className="p-5">
              {/* Header row: destination + ETA */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-10 h-10 rounded-full bg-red-500/15 border border-red-500/30
                                  flex items-center justify-center shrink-0">
                    <MapPin className="w-5 h-5 text-red-400" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-black text-white truncate">
                      {requestDetails?.hospital_name || 'Hospital'}
                    </h3>
                    <span className="text-[10px] text-white/30 uppercase tracking-widest">Destination</span>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className={`text-3xl font-black tabular-nums ${
                    etaSeconds !== null && etaSeconds <= 60 ? 'text-amber-400' : 'text-emerald-400'
                  }`}>
                    {etaDisplay}
                  </div>
                  <div className="text-[9px] text-white/30 uppercase tracking-widest mt-0.5">ETA</div>
                </div>
              </div>

              {/* Stats row */}
              <div className="grid grid-cols-3 gap-3 mb-4">
                <div className="bg-white/3 rounded-xl p-2.5 text-center border border-white/5">
                  <div className="text-[10px] text-white/30 uppercase tracking-widest mb-1">Distance</div>
                  <div className="text-sm font-black text-white tabular-nums">
                    {distance !== null ? `${distance} km` : '—'}
                  </div>
                </div>
                <div className="bg-white/3 rounded-xl p-2.5 text-center border border-white/5">
                  <div className="text-[10px] text-white/30 uppercase tracking-widest mb-1">Blood</div>
                  <div className="text-sm font-black text-red-400">
                    {requestDetails?.blood_type || '—'}
                  </div>
                </div>
                <div className="bg-white/3 rounded-xl p-2.5 text-center border border-white/5">
                  <div className="text-[10px] text-white/30 uppercase tracking-widest mb-1">Progress</div>
                  <div className="text-sm font-black text-emerald-400 tabular-nums">
                    {progressPct}%
                  </div>
                </div>
              </div>

              {/* Route schematic */}
              <div className="mb-4">
                <div className="flex items-center gap-2 text-[9px] text-white/25 uppercase tracking-widest mb-1.5">
                  <span>You</span>
                  <div className="flex-1" />
                  <span>{requestDetails?.hospital_name || 'Hospital'}</span>
                </div>
                <div className="relative h-[3px] bg-white/8 rounded-full overflow-visible">
                  <motion.div
                    className="absolute left-0 top-0 h-full bg-emerald-500/60 rounded-full"
                    animate={{ width: `${progressPct}%` }}
                    transition={{ duration: 1.2, ease: 'easeOut' }}
                  />
                  <motion.div
                    className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 
                               w-3 h-3 rounded-full bg-emerald-400 border-2 border-[#0A0A0C]
                               shadow-[0_0_8px_rgba(16,185,129,0.8)]"
                    animate={{ left: `${progressPct}%` }}
                    transition={{ duration: 1.2, ease: 'easeOut' }}
                  />
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2
                                  w-2.5 h-2.5 rounded-full bg-red-500 border-2 border-[#0A0A0C]" />
                </div>
              </div>

              {/* Action buttons */}
              <div className="flex gap-2">
                {canWithdraw && (
                  <button
                    onClick={() => setShowWithdrawConfirm(true)}
                    disabled={isWithdrawing}
                    className="flex-1 py-3 rounded-xl bg-red-900/40 border border-red-500/30
                               text-red-400 text-xs font-bold hover:bg-red-900/60 transition-colors
                               disabled:opacity-50"
                  >
                    Withdraw
                  </button>
                )}
                <button
                  onClick={() => setShowDevPanel(!showDevPanel)}
                  className="px-4 py-3 rounded-xl bg-white/5 border border-white/5
                             text-white/40 text-xs font-bold hover:bg-white/10 transition-colors
                             flex items-center gap-1.5"
                >
                  {showDevPanel ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />}
                  Dev
                </button>
              </div>

              {/* Dev panel */}
              <AnimatePresence>
                {showDevPanel && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    <div className="mt-3 p-3 bg-white/3 border border-white/5 rounded-xl space-y-2">
                      <div className="text-[9px] text-white/30 uppercase tracking-widest font-bold">Simulation Info</div>
                      <div className="grid grid-cols-2 gap-2 text-[10px]">
                        <div className="text-white/40">State: <span className="text-white font-bold">{requestState}</span></div>
                        <div className="text-white/40">WS: <span className="text-white font-bold">{connectionState}</span></div>
                        <div className="text-white/40">Match: <span className="text-white font-bold">{activeMatchId || '—'}</span></div>
                        <div className="text-white/40">Donor Pos: <span className="text-white font-bold">
                          {donorLocation ? `${donorLocation[0]?.toFixed(4)}, ${donorLocation[1]?.toFixed(4)}` : '—'}
                        </span></div>
                        <div className="text-white/40">Hospital: <span className="text-white font-bold">
                          {hospitalLoc?.[0]?.toFixed(4)}, {hospitalLoc?.[1]?.toFixed(4)}
                        </span></div>
                        <div className="text-white/40">Steps: <span className="text-white font-bold">{progressPct}%</span></div>
                      </div>
                      {withdrawError && (
                        <div className="text-red-400 text-[10px] font-bold mt-1">{withdrawError}</div>
                      )}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}
