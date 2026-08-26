/**
 * EmergencyLiveTracker — Phase 2 Orchestrator
 *
 * Responsibilities (slim):
 *  - Receives requestData + onSimulateDonor props
 *  - Delegates ALL WebSocket/state logic to useTrackingSession
 *  - Composes: TrackingMap / TrackingCard / ArrivalOverlay / SummaryCard
 *  - Keeps SearchProgressStream + LiveTimeline from Phase 1 intact
 *
 * No state management here. No WS subscriptions here.
 * This component is purely presentational — it assembles sub-components.
 */
import React, { useMemo, useCallback, useState } from 'react';
import { AnimatePresence } from 'framer-motion';
import { Wifi, WifiOff, XCircle, AlertTriangle, Home, Loader2, Ban } from 'lucide-react';
import { motion } from 'framer-motion';
import { cancelRequest, getRequestStatus } from '../services/api';
import { useToast } from './NotificationToast';

import useTrackingSession from '../hooks/useTrackingSession';
import TrackingMap        from './tracking/TrackingMap';
import TrackingCard       from './tracking/TrackingCard';
import ArrivalOverlay     from './tracking/ArrivalOverlay';
import SummaryCard        from './tracking/SummaryCard';
import LiveTimeline       from './LiveTimeline';
import SearchProgressStream from './SearchProgressStream';

// ── Reconnecting banner ──────────────────────────────────────────────────
const ReconnectingBanner = React.memo(function ReconnectingBanner({ visible }) {
  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0  }}
          exit={  { opacity: 0, y: -20 }}
          className="absolute top-2 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2
                     bg-amber-900/80 px-3 py-1.5 rounded-full backdrop-blur-md pointer-events-none"
        >
          <WifiOff className="w-3 h-3 text-amber-400 animate-pulse" />
          <span className="text-xs font-bold text-amber-300">Reconnecting…</span>
        </motion.div>
      )}
    </AnimatePresence>
  );
});

// ── Connection indicator pill ────────────────────────────────────────────
const ConnectionPill = React.memo(function ConnectionPill({ connectionState }) {
  const isLive = connectionState === 'connected';
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-[#111111]/80 border border-white/5">
      {isLive
        ? <><Wifi    className="w-3 h-3 text-emerald-500" /><span className="text-[9px] text-emerald-400 font-bold">LIVE</span></>
        : <><WifiOff className="w-3 h-3 text-amber-500"   /><span className="text-[9px] text-amber-400   font-bold">{connectionState.toUpperCase()}</span></>
      }
    </div>
  );
});

// ── Confirmation Modal ───────────────────────────────────────────────────
const ConfirmCancelModal = React.memo(function ConfirmCancelModal({
  visible, onConfirm, onDismiss, isLoading
}) {
  if (!visible) return null;
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 z-40 flex items-center justify-center
                 bg-black/70 backdrop-blur-sm"
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
            <h3 className="text-lg font-black text-white">Cancel Emergency?</h3>
            <p className="text-sm text-white/40 mt-2 leading-relaxed">
              Are you sure you want to cancel this emergency blood request?
              Donors may already have been notified.
            </p>
          </div>
          <div className="w-full flex gap-3">
            <button
              onClick={onDismiss}
              disabled={isLoading}
              className="flex-1 py-3 rounded-xl bg-white/8 text-white/70 text-sm font-bold
                         hover:bg-white/12 transition-colors disabled:opacity-40"
            >
              Keep Active
            </button>
            <button
              onClick={onConfirm}
              disabled={isLoading}
              className="flex-1 py-3 rounded-xl bg-red-600 text-white text-sm font-bold
                         hover:bg-red-500 transition-colors disabled:opacity-60
                         flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <><Loader2 className="w-4 h-4 animate-spin" /> Cancelling…</>
              ) : (
                <><Ban className="w-4 h-4" /> Cancel Request</>
              )}
            </button>
          </div>
        </div>
      </motion.div>
    </motion.div>
  );
});

// ── Cancelled Overlay ────────────────────────────────────────────────────
const CancelledOverlay = React.memo(function CancelledOverlay({ events, onClose }) {
  const stateCount = useMemo(() => events.length, [events]);
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9, y: 40 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className="absolute inset-0 z-20 flex items-center justify-center
                 bg-[#050505]/85 backdrop-blur-md"
    >
      <div className="max-w-sm w-full mx-4 rounded-[32px] overflow-hidden
                      bg-[#0A0A0C]/96 border border-white/8 shadow-2xl">
        <div className="h-1.5 bg-gradient-to-r from-amber-600 via-red-500 to-amber-600" />
        <div className="p-7 flex flex-col items-center gap-6">
          <motion.div
            initial={{ scale: 0, rotate: -20 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: 'spring', stiffness: 200, delay: 0.15 }}
            className="w-20 h-20 rounded-full bg-red-500/15 border-2 border-red-400/40
                       flex items-center justify-center"
          >
            <XCircle className="w-10 h-10 text-red-400" />
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="text-center"
          >
            <h2 className="text-2xl font-black text-white">Request Cancelled</h2>
            <p className="text-sm text-white/40 mt-1.5">
              This emergency request has been cancelled.
              No further donor matching will occur.
            </p>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="w-full flex items-center gap-3 p-3 rounded-xl bg-white/3 border border-white/5"
          >
            <XCircle className="w-4 h-4 text-red-400 shrink-0" />
            <div>
              <div className="text-[11px] font-bold text-red-400">Cancelled</div>
              <div className="text-[9px] text-white/30 uppercase tracking-wide">{stateCount} events recorded</div>
            </div>
          </motion.div>
          <motion.button
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45 }}
            onClick={onClose}
            className="w-full flex items-center justify-center gap-2 py-3.5 px-6
                       rounded-2xl bg-white text-black font-black text-sm
                       hover:bg-white/90 active:scale-[0.98] transition-all"
          >
            <Home className="w-4 h-4" />
            Return to Home
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
});

// ── Main Component ───────────────────────────────────────────────────────
export default function EmergencyLiveTracker({ requestData, onSimulateDonor }) {
  // All WS logic lives in the hook
  const session = useTrackingSession(requestData);

  const {
    requestState,
    events,
    donorLocation,
    initialDonorPos,
    routeHistory,
    etaSeconds,
    distance,
    progress,
    acceptedDonor,
    searchProgress,
    ringCountdown,
    connectionState,
    hospitalLoc,
    isSearching,
    isTracking,
    isArrived,
    isDonationPhase,
    isClosed,
    isCancelled,
    isDonorAccepted,
  } = session;

  // ── Cancellation state ──────────────────────────────────────────
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const toast = useToast();
  const reqId = requestData?.request?.id;

  const canCancel = isSearching && !isCancelled && !isClosed;

  const handleCancelRequest = useCallback(async () => {
    if (!reqId || isCancelling) return;
    setIsCancelling(true);
    try {
      await cancelRequest(reqId);
      setShowCancelConfirm(false);
      toast.addToast({
        title: 'Request Cancelled',
        message: 'The emergency request has been cancelled.',
        type: 'alert',
        duration: 5000
      });
    } catch (err) {
      toast.addToast({
        title: 'Cancellation Failed',
        message: err.message || 'Could not cancel the request. Please try again.',
        type: 'alert',
        duration: 5000
      });
    } finally {
      setIsCancelling(false);
    }
  }, [reqId, isCancelling, toast]);

  // Nearby donor markers come from searchProgress events via SearchProgressStream
  // (unchanged from Phase 1 — SearchProgressStream handles its own marker state)
  const nearbyMarkers = useMemo(() => [], []); // SearchProgressStream renders its own dots via Leaflet-less approach

  // Stable callback for simulate button
  const handleSimulate = useCallback(async () => {
    const reqId = requestData?.request?.id || requestData?.matching_summary?.request_id;
    if (!reqId) {
      onSimulateDonor?.();
      return;
    }

    try {
      // Fetch latest status to get populated matches generated by background AI engine
      const latestData = await getRequestStatus(reqId);
      const firstMatchId = latestData?.matches?.[0]?.match_id;
      
      if (!firstMatchId) {
        toast.addToast({
          title: 'Matching in Progress',
          message: 'The AI engine is still generating matches. Please wait until Ring 1 begins.',
          type: 'alert',
          duration: 4000
        });
        return;
      }
      
      onSimulateDonor?.(firstMatchId);
    } catch (e) {
      console.error("[Demo] Failed to get latest matches:", e);
      const fallbackMatchId = requestData?.matches?.[0]?.match_id;
      if (fallbackMatchId) {
        onSimulateDonor?.(fallbackMatchId);
      } else {
        toast.addToast({
          title: 'Error',
          message: 'Could not fetch matches. Please wait or try again.',
          type: 'alert',
          duration: 3000
        });
      }
    }
  }, [onSimulateDonor, requestData, toast]);

  // Handle SummaryCard close — navigate home
  const handleClose = useCallback(() => {
    window.location.href = '/';
  }, []);

  // Show ArrivalOverlay for ARRIVED, DONATION_STARTED, DONATION_COMPLETED
  const showArrivalOverlay = isArrived || isDonationPhase;

  return (
    <div className="absolute inset-0 z-0 overflow-hidden bg-[#050505] animate-cinematic-in">
      {/* Reconnecting banner */}
      <ReconnectingBanner visible={connectionState === 'reconnecting'} />

      {/* ── MAP (full-bleed background) ─────────────────────────── */}
      <div className="absolute inset-0">
        <TrackingMap
          hospitalLoc={hospitalLoc}
          donorLocation={donorLocation}
          initialDonorPos={initialDonorPos}
          routeHistory={routeHistory}
          nearbyMarkers={nearbyMarkers}
          isSearching={isSearching}
          isTracking={isTracking}
          isDonorAccepted={isDonorAccepted}
          requestState={requestState}
          acceptedDonor={acceptedDonor}
          etaSeconds={etaSeconds}
          distance={distance}
          hospitalName={requestData?.request?.hospital_name}
        />
      </div>

      {/* Map top gradient */}
      <div className="absolute top-0 left-0 right-0 h-24 map-overlay-gradient-top z-[5] pointer-events-none" />

      {/* ── ARRIVAL / DONATION overlays ─────────────────────────── */}
      <ArrivalOverlay
        requestState={showArrivalOverlay ? requestState : null}
        acceptedDonor={acceptedDonor}
      />

      {/* ── CLOSED — summary card ───────────────────────────────── */}
      <AnimatePresence>
        {isClosed && (
          <SummaryCard
            acceptedDonor={acceptedDonor}
            events={events}
            onClose={handleClose}
          />
        )}
      </AnimatePresence>

      {/* ── CANCELLED — cancelled overlay ────────────────────────── */}
      <AnimatePresence>
        {isCancelled && (
          <CancelledOverlay events={events} onClose={handleClose} />
        )}
      </AnimatePresence>

      {/* ── Cancel confirmation modal ────────────────────────────── */}
      <AnimatePresence>
        <ConfirmCancelModal
          visible={showCancelConfirm}
          onConfirm={handleCancelRequest}
          onDismiss={() => setShowCancelConfirm(false)}
          isLoading={isCancelling}
        />
      </AnimatePresence>

      {/* ── OVERLAYS (timeline + tracking card) ─────────────────── */}
      {!isClosed && !isCancelled && (
        <div className="absolute inset-0 pointer-events-none z-10 flex p-4 pb-20 lg:p-6 gap-6">
          {/* Left — timeline */}
          <div className="w-[350px] hidden lg:block pointer-events-auto h-full overflow-y-auto no-scrollbar">
            <LiveTimeline events={events} currentState={requestState} />
          </div>

          {/* Right — search stream + tracking card */}
          <div className="flex-1 flex flex-col justify-between items-end h-full">
            {/* Top-right: Search Progress Stream */}
            <div className="w-full max-w-sm pointer-events-auto">
              <SearchProgressStream
                searchProgress={searchProgress}
                ringCountdown={ringCountdown}
                currentState={requestState}
              />
            </div>

            {/* Bottom: Tracking card (TRACKING / ARRIVING) */}
            <AnimatePresence mode="wait">
              {(isTracking || isArrived) && !showArrivalOverlay && (
                <TrackingCard
                  key="tracking-card"
                  requestState={requestState}
                  acceptedDonor={acceptedDonor}
                  etaSeconds={etaSeconds}
                  distance={distance}
                  progress={progress}
                />
              )}
            </AnimatePresence>

            {/* Bottom bar: Cancel + Simulator + Connection */}
            <div className="pointer-events-auto mt-4 self-end flex items-center gap-3">
              {canCancel && (
                <button
                  onClick={() => setShowCancelConfirm(true)}
                  disabled={isCancelling}
                  className="px-4 py-2 bg-red-900/60 backdrop-blur-md text-xs text-red-300
                             rounded-full hover:bg-red-800/70 border border-red-600/40 transition-colors
                             flex items-center gap-1.5 disabled:opacity-50"
                >
                  <XCircle className="w-3.5 h-3.5" />
                  Cancel Request
                </button>
              )}
              <ConnectionPill connectionState={connectionState} />
              <button
                onClick={handleSimulate}
                className="px-4 py-2 bg-slate-800/80 backdrop-blur-md text-xs text-white
                           rounded-full hover:bg-slate-700 border border-slate-600/50 transition-colors"
              >
                Open Donor Simulator
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
