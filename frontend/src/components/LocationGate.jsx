/**
 * LocationGate — Gates GPS-dependent features with proper state-aware UI.
 *
 * Usage:
 *   <LocationGate>
 *     <EmergencyRequestForm ... />
 *   </LocationGate>
 *
 * When GPS is available, renders children normally.
 * When GPS is unavailable, shows the appropriate error state with retry.
 */
import React from 'react';
import { motion } from 'framer-motion';
import { MapPin, ShieldAlert, WifiOff, Clock, AlertTriangle, RefreshCw, Navigation } from 'lucide-react';
import { useGPS, GPS_STATES } from '../App';

const STATE_CONFIG = {
  [GPS_STATES.REQUESTING]: {
    icon: Navigation,
    title: 'Locating You…',
    message: 'Requesting your device location to find nearby blood donors.',
    color: 'text-blue-400',
    bgRing: 'border-blue-400/40',
    bgIcon: 'bg-blue-500/15',
    showRetry: false,
    showSpinner: true,
  },
  [GPS_STATES.DENIED]: {
    icon: ShieldAlert,
    title: 'Location Access Denied',
    message: 'Location permission is required to find nearby blood donors. Please enable location access in your browser settings and try again.',
    color: 'text-amber-400',
    bgRing: 'border-amber-400/40',
    bgIcon: 'bg-amber-500/15',
    showRetry: true,
    showSpinner: false,
  },
  [GPS_STATES.UNAVAILABLE]: {
    icon: WifiOff,
    title: 'Position Unavailable',
    message: 'Your device could not determine its position. Check that location services are enabled and try again.',
    color: 'text-orange-400',
    bgRing: 'border-orange-400/40',
    bgIcon: 'bg-orange-500/15',
    showRetry: true,
    showSpinner: false,
  },
  [GPS_STATES.TIMEOUT]: {
    icon: Clock,
    title: 'Location Request Timed Out',
    message: 'The location request took too long. This may be due to weak GPS signal. Try moving to an open area and retrying.',
    color: 'text-yellow-400',
    bgRing: 'border-yellow-400/40',
    bgIcon: 'bg-yellow-500/15',
    showRetry: true,
    showSpinner: false,
  },
  [GPS_STATES.ERROR]: {
    icon: AlertTriangle,
    title: 'Location Error',
    message: 'An unexpected error occurred while accessing your location. Please try again.',
    color: 'text-red-400',
    bgRing: 'border-red-400/40',
    bgIcon: 'bg-red-500/15',
    showRetry: true,
    showSpinner: false,
  },
};

export default function LocationGate({ children }) {
  const gps = useGPS();
  const { gpsState, errorMessage, refresh } = gps || {};

  // GPS available — render children normally
  if (gpsState === GPS_STATES.AVAILABLE) {
    return children;
  }

  // IDLE means we haven't started yet — treat like requesting
  const effectiveState = gpsState === GPS_STATES.IDLE ? GPS_STATES.REQUESTING : gpsState;
  const config = STATE_CONFIG[effectiveState];

  if (!config) return children; // Safety fallback

  const Icon = config.icon;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
      className="flex items-center justify-center min-h-[60vh] px-4"
    >
      <div className="max-w-md w-full rounded-[28px] bg-[#0A0A0C]/80 border border-white/8
                      shadow-2xl overflow-hidden backdrop-blur-xl">
        {/* Accent bar */}
        <div className={`h-1.5 bg-gradient-to-r from-transparent via-current to-transparent ${config.color}`} />

        <div className="p-8 flex flex-col items-center gap-6 text-center">
          {/* Icon */}
          <motion.div
            initial={{ scale: 0, rotate: -15 }}
            animate={{ scale: 1, rotate: 0 }}
            transition={{ type: 'spring', stiffness: 200, delay: 0.1 }}
            className={`w-20 h-20 rounded-full ${config.bgIcon} border-2 ${config.bgRing}
                        flex items-center justify-center relative`}
          >
            <Icon className={`w-9 h-9 ${config.color}`} />
            {config.showSpinner && (
              <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-blue-400 animate-spin" />
            )}
          </motion.div>

          {/* Title & Message */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            <h2 className="text-xl font-black text-white mb-2">{config.title}</h2>
            <p className="text-sm text-white/45 leading-relaxed">{config.message}</p>
          </motion.div>

          {/* Why location matters */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.35 }}
            className="w-full flex items-start gap-3 p-3.5 rounded-xl bg-white/3 border border-white/5"
          >
            <MapPin className="w-4 h-4 text-blood-500 shrink-0 mt-0.5" />
            <p className="text-[11px] text-white/35 leading-relaxed text-left">
              Your location helps us find compatible blood donors near you.
              We only use your location for matching — it is never stored or shared.
            </p>
          </motion.div>

          {/* Retry button */}
          {config.showRetry && (
            <motion.button
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.45 }}
              onClick={refresh}
              className="w-full flex items-center justify-center gap-2.5 py-3.5 px-6
                         rounded-2xl bg-white text-black font-black text-sm
                         hover:bg-white/90 active:scale-[0.98] transition-all"
            >
              <RefreshCw className="w-4 h-4" />
              Try Again
            </motion.button>
          )}

          {/* Browser hint for denied state */}
          {effectiveState === GPS_STATES.DENIED && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.55 }}
              className="text-[10px] text-white/25 leading-relaxed"
            >
              Tip: Click the lock/location icon in your browser's address bar to update permissions, then tap "Try Again".
            </motion.p>
          )}
        </div>
      </div>
    </motion.div>
  );
}
