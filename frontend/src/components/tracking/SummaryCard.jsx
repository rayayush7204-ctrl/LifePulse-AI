/**
 * SummaryCard — Shown when the emergency reaches the CLOSED state.
 *
 * Displays:
 *  - "Emergency Resolved" headline
 *  - Donor name + blood type
 *  - Total elapsed time
 *  - State timeline count
 *  - "Return to Home" button
 *
 * Professional medical tone — no confetti, clean data summary.
 */
import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle2, Droplets, Clock, BarChart2, Home } from 'lucide-react';

const SummaryCard = React.memo(function SummaryCard({
  acceptedDonor,
  events,
  onClose,
}) {
  const stateCount = useMemo(() => events.length, [events]);

  // Find elapsed time from first to last event
  const elapsedLabel = useMemo(() => {
    if (events.length < 2) return null;
    const last  = events[0];   // events are newest-first
    const first = events[events.length - 1];
    // We only have locale time strings so we show count as proxy
    return `${stateCount} events`;
  }, [events, stateCount]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9, y: 40 }}
      animate={{ opacity: 1, scale: 1,   y: 0  }}
      transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
      className="absolute inset-0 z-20 flex items-center justify-center
                 bg-[#050505]/85 backdrop-blur-md"
    >
      <div className="max-w-sm w-full mx-4 rounded-[32px] overflow-hidden
                      bg-[#0A0A0C]/96 border border-white/8 shadow-2xl">
        {/* Header strip */}
        <div className="h-1.5 bg-gradient-to-r from-emerald-600 via-emerald-400 to-emerald-600" />

        <div className="p-7 flex flex-col items-center gap-6">
          {/* Icon */}
          <motion.div
            initial={{ scale: 0, rotate: -20 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: 'spring', stiffness: 200, delay: 0.15 }}
            className="w-20 h-20 rounded-full bg-emerald-500/15 border-2 border-emerald-400/40
                       flex items-center justify-center animate-accepted-glow"
          >
            <CheckCircle2 className="w-10 h-10 text-emerald-400" />
          </motion.div>

          {/* Headline */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.25 }}
            className="text-center"
          >
            <h2 className="text-2xl font-black text-white">Emergency Resolved</h2>
            <p className="text-sm text-white/40 mt-1.5">
              Blood delivered successfully to the hospital.
            </p>
          </motion.div>

          {/* Stats grid */}
          <motion.div
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            className="w-full grid grid-cols-2 gap-3"
          >
            {/* Donor */}
            <div className="col-span-2 flex items-center gap-3 p-3 rounded-2xl
                            bg-white/4 border border-white/6">
              <div className="w-9 h-9 rounded-full bg-red-500/15 border border-red-500/30
                              flex items-center justify-center shrink-0">
                <Droplets className="w-4 h-4 text-red-400" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-bold text-white truncate">
                  {acceptedDonor?.donor_name || 'Donor'}
                </div>
                <div className="text-[10px] text-white/35">
                  {acceptedDonor?.donor_blood_type || '—'} blood type
                </div>
              </div>
            </div>

            {/* Events */}
            <div className="flex items-center gap-2 p-3 rounded-xl bg-white/3 border border-white/5">
              <BarChart2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <div>
                <div className="text-sm font-bold text-white">{stateCount}</div>
                <div className="text-[9px] text-white/30 uppercase tracking-wide">Events</div>
              </div>
            </div>

            {/* Status */}
            <div className="flex items-center gap-2 p-3 rounded-xl bg-white/3 border border-white/5">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <div>
                <div className="text-[11px] font-bold text-emerald-400">Success</div>
                <div className="text-[9px] text-white/30 uppercase tracking-wide">Outcome</div>
              </div>
            </div>
          </motion.div>

          {/* CTA */}
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

export default SummaryCard;
