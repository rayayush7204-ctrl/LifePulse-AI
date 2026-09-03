/**
 * ArrivalOverlay — Cinematic full-screen overlays for terminal GPS states.
 *
 * States handled:
 *  - ARRIVED:            Donor has reached the hospital — heartbeat confirmation
 *  - DONATION_STARTED:   Procedure underway — medical pulse animation
 *  - DONATION_COMPLETED: Life saved — professional medical acknowledgment (no confetti)
 *
 * Design: subtle medical-themed animations. No celebration confetti.
 * The tone is professional and reverential — a life was saved.
 */
import React, { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Heart, CheckCircle2, Activity, Droplets, Shield } from 'lucide-react';

// ── Heartbeat SVG animation ──────────────────────────────────────────────
function HeartbeatLine() {
  return (
    <svg viewBox="0 0 200 60" className="w-40 h-12" fill="none">
      <motion.polyline
        points="0,30 30,30 40,10 50,50 60,30 80,30 90,15 100,45 110,30 160,30 175,20 185,40 200,30"
        stroke="#10b981"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 1 }}
        transition={{ duration: 1.5, ease: 'easeInOut' }}
      />
    </svg>
  );
}

// ── Donation phase content ────────────────────────────────────────────────
const PHASE_CONFIG = {
  ARRIVED: {
    icon:       <CheckCircle2 className="w-12 h-12 text-emerald-400" />,
    iconBg:     'bg-emerald-500/15 border-emerald-400/40',
    headline:   'Donor Arrived',
    subline:    'Preparing donation procedure...',
    accent:     'text-emerald-400',
    showECG:    true,
  },
  DONATION_STARTED: {
    icon:       <Activity className="w-12 h-12 text-blue-400 animate-pulse" />,
    iconBg:     'bg-blue-500/15 border-blue-400/40',
    headline:   'Donation In Progress',
    subline:    'Please ensure a sterile environment is maintained.',
    accent:     'text-blue-400',
    showECG:    false,
  },
  DONATION_COMPLETED: {
    icon:       <Heart className="w-12 h-12 text-red-400" />,
    iconBg:     'bg-red-500/15 border-red-400/40',
    headline:   'Life Saved',
    subline:    'Donation completed successfully. Thank you.',
    accent:     'text-red-400',
    showECG:    true,
  },
};

const ArrivalOverlay = React.memo(function ArrivalOverlay({
  requestState,
  acceptedDonor,
  onStartDonation,
  onCompleteDonation,
  isActionLoading,
}) {
  const config = useMemo(() => PHASE_CONFIG[requestState], [requestState]);
  const visible = !!config;

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key={requestState}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.6 }}
          className="absolute inset-0 z-20 flex flex-col items-center justify-center
                     bg-[#050505]/80 backdrop-blur-md pointer-events-none"
        >
          <motion.div
            initial={{ scale: 0.85, y: 20, opacity: 0 }}
            animate={{ scale: 1,    y: 0,  opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
            className="flex flex-col items-center gap-5 px-8 py-10 rounded-[32px]
                       bg-[#0A0A0C]/90 border border-white/8 backdrop-blur-xl
                       shadow-2xl max-w-sm w-full mx-4"
          >
            {/* Icon */}
            <motion.div
              initial={{ scale: 0.5, opacity: 0 }}
              animate={{ scale: 1,   opacity: 1 }}
              transition={{ duration: 0.5, delay: 0.2, type: 'spring', stiffness: 200 }}
              className={`w-24 h-24 rounded-full border-2 flex items-center justify-center
                          animate-accepted-glow ${config.iconBg}`}
            >
              {config.icon}
            </motion.div>

            {/* Headline */}
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="text-center"
            >
              <h2 className={`text-3xl font-black ${config.accent}`}>
                {config.headline}
              </h2>
              <p className="text-sm text-white/50 mt-2 leading-relaxed">
                {config.subline}
              </p>
            </motion.div>

            {/* ECG line (for arrival + completion) */}
            {config.showECG && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ delay: 0.5 }}
              >
                <HeartbeatLine />
              </motion.div>
            )}

            {/* Donor info strip */}
            {acceptedDonor && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.55 }}
                className="flex items-center gap-3 w-full px-4 py-3 rounded-2xl
                           bg-white/4 border border-white/6"
              >
                <div className="w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/40
                                flex items-center justify-center shrink-0">
                  <Droplets className="w-4 h-4 text-emerald-400" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-bold text-white truncate">
                    {acceptedDonor.donor_name}
                  </div>
                  <div className="text-[10px] text-white/40">
                    {acceptedDonor.donor_blood_type} blood type
                  </div>
                </div>
                {requestState === 'DONATION_COMPLETED' && (
                  <Shield className="w-5 h-5 text-emerald-400 ml-auto shrink-0" />
                )}
              </motion.div>
            )}

            {/* Action Buttons (Only shown for Donor) */}
            {(onStartDonation || onCompleteDonation) && (
              <motion.div
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.6 }}
                className="w-full mt-2 pointer-events-auto"
              >
                {requestState === 'ARRIVED' && onStartDonation && (
                  <button
                    onClick={onStartDonation}
                    disabled={isActionLoading}
                    className="w-full py-4 rounded-2xl bg-white text-black font-black text-sm uppercase tracking-wider
                               hover:bg-white/90 active:scale-[0.98] transition-all disabled:opacity-50"
                  >
                    {isActionLoading ? 'Starting...' : 'Start Donation'}
                  </button>
                )}
                {requestState === 'DONATION_STARTED' && onCompleteDonation && (
                  <button
                    onClick={onCompleteDonation}
                    disabled={isActionLoading}
                    className="w-full py-4 rounded-2xl bg-white text-black font-black text-sm uppercase tracking-wider
                               hover:bg-white/90 active:scale-[0.98] transition-all disabled:opacity-50"
                  >
                    {isActionLoading ? 'Completing...' : 'Complete Donation'}
                  </button>
                )}
              </motion.div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
});

export default ArrivalOverlay;
