/**
 * TrackingCard — Uber-style bottom sheet shown during TRACKING / ARRIVING states.
 *
 * Features:
 *  - M:SS live ETA countdown (driven by etaSeconds from useTrackingSession)
 *  - Route schematic progress bar (donor dot slides toward hospital icon)
 *  - Animated top progress bar (fills based on GPS step / total)
 *  - Status label: En Route → Arriving → Arrived
 *  - React.memo: only re-renders when props differ
 */
import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { User, MapPin, Droplets, Activity } from 'lucide-react';

const formatEta = (seconds) => {
  if (seconds === null || seconds === undefined) return '--:--';
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
};

const statusLabel = (state) => {
  switch (state) {
    case 'TRACKING':  return { label: 'En Route',  color: 'text-emerald-400' };
    case 'ARRIVING':  return { label: 'Arriving',  color: 'text-amber-400' };
    case 'ARRIVED':   return { label: 'Arrived',   color: 'text-emerald-300' };
    default:          return { label: state,        color: 'text-gray-400' };
  }
};

const TrackingCard = React.memo(function TrackingCard({
  requestState,
  acceptedDonor,
  etaSeconds,
  distance,
  progress,   // 0–1 from GPS step / total_steps
}) {
  const { label, color } = useMemo(() => statusLabel(requestState), [requestState]);
  const etaDisplay = useMemo(() => formatEta(etaSeconds), [etaSeconds]);
  // Clamp and invert: progress=0 → donor at start; progress=1 → donor at hospital
  const progressPct = Math.min(100, Math.max(0, Math.round(progress * 100)));

  return (
    <motion.div
      initial={{ y: 120, opacity: 0 }}
      animate={{ y: 0,   opacity: 1 }}
      exit={  { y: 120, opacity: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="w-full max-w-md pointer-events-auto relative overflow-hidden rounded-[28px]
                 bg-[#0A0A0C]/96 backdrop-blur-xl border border-emerald-500/25
                 shadow-[0_0_48px_rgba(16,185,129,0.12)]"
    >
      {/* Animated top progress fill */}
      <div className="absolute top-0 left-0 right-0 h-[3px] bg-white/5 overflow-hidden rounded-t-[28px]">
        <motion.div
          className="h-full bg-gradient-to-r from-emerald-500 via-emerald-400 to-emerald-300"
          initial={{ width: '0%' }}
          animate={{ width: `${progressPct}%` }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
        />
      </div>

      <div className="p-5 pt-6">
        {/* Status pill */}
        <div className="flex items-center justify-between mb-4">
          <span className={`text-[10px] font-black tracking-[0.15em] uppercase ${color} flex items-center gap-1.5`}>
            <Activity className="w-3 h-3 animate-pulse" />
            {label}
          </span>
          <span className="text-[10px] text-white/30 font-mono">LIVE GPS</span>
        </div>

        {/* Main row: avatar + name/blood + ETA */}
        <div className="flex items-center gap-4">
          {/* Donor avatar */}
          <div className="relative shrink-0">
            <div className="w-14 h-14 rounded-full bg-emerald-500/15 border-2 border-emerald-500/40
                            flex items-center justify-center animate-accepted-glow">
              <User className="w-6 h-6 text-emerald-400" />
            </div>
            {/* Pulse ring */}
            <div className="absolute inset-0 rounded-full border-2 border-emerald-400/30
                            animate-ping" style={{ animationDuration: '2s' }} />
          </div>

          {/* Donor info */}
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-black text-white leading-tight truncate">
              {acceptedDonor?.donor_name || 'Donor En Route'}
            </h3>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded
                               bg-red-900/30 text-red-400 text-[10px] font-black border border-red-800/30">
                <Droplets className="w-2.5 h-2.5" />
                {acceptedDonor?.donor_blood_type || 'O-'}
              </span>
              <span className="text-xs text-white/40 flex items-center gap-1">
                <MapPin className="w-2.5 h-2.5" />
                {distance !== null ? `${distance} km away` : '—'}
              </span>
            </div>
          </div>

          {/* ETA countdown */}
          <div className="shrink-0 text-right">
            <div className={`text-3xl font-black tabular-nums ${
              etaSeconds !== null && etaSeconds <= 60 ? 'text-amber-400' : 'text-emerald-400'
            }`}>
              {etaDisplay}
            </div>
            <div className="text-[9px] text-white/30 uppercase tracking-widest mt-0.5">ETA</div>
          </div>
        </div>

        {/* Route schematic */}
        <div className="mt-4 relative">
          <div className="flex items-center gap-2 text-[9px] text-white/25 uppercase tracking-widest mb-1.5">
            <span>Donor</span>
            <div className="flex-1" />
            <span>{acceptedDonor?.hospital_name || 'Hospital'}</span>
          </div>
          <div className="relative h-[3px] bg-white/8 rounded-full overflow-visible">
            {/* Filled track */}
            <motion.div
              className="absolute left-0 top-0 h-full bg-emerald-500/60 rounded-full"
              animate={{ width: `${progressPct}%` }}
              transition={{ duration: 1.2, ease: 'easeOut' }}
            />
            {/* Moving donor dot */}
            <motion.div
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 
                         w-3 h-3 rounded-full bg-emerald-400 border-2 border-[#0A0A0C]
                         shadow-[0_0_8px_rgba(16,185,129,0.8)]"
              animate={{ left: `${progressPct}%` }}
              transition={{ duration: 1.2, ease: 'easeOut' }}
            />
            {/* Hospital endpoint */}
            <div className="absolute right-0 top-1/2 -translate-y-1/2 translate-x-1/2
                            w-2.5 h-2.5 rounded-full bg-red-500 border-2 border-[#0A0A0C]" />
          </div>
        </div>
      </div>
    </motion.div>
  );
});

export default TrackingCard;
