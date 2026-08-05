import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Loader2, Radio, Timer, Users, Eye } from 'lucide-react';

/**
 * SearchProgressStream — Live typewriter event stream overlay.
 * Floats over the map in the top-right corner showing real-time search progress:
 * 
 *   Searching...
 *   ✔ Found 432 donors
 *   Filtering medical eligibility... 328 remain
 *   Checking 56-day rule... 261 remain
 *   Calculating distance...
 *   Ranking...
 *   Broadcasting Ring 1...
 *   Waiting for response...
 *   ⏱ 42s remaining
 *   1 donor viewed request...
 *   1 donor accepted!
 */
export default function SearchProgressStream({ searchProgress, ringCountdown, currentState }) {
  const [streamItems, setStreamItems] = useState([]);
  const scrollRef = useRef(null);

  // Build stream items from incoming progress data
  useEffect(() => {
    if (!searchProgress) return;
    
    const { phase, label, total, after_blood_filter, after_56day, after_distance, matched } = searchProgress;
    
    const existingPhases = streamItems.map(i => i.phase);
    if (existingPhases.includes(phase)) return; // Don't duplicate

    let icon = 'loading';
    let text = label || phase;
    
    switch (phase) {
      case 'donors_found':
        icon = 'check';
        text = `Found ${total} donors in network`;
        break;
      case 'blood_filter':
        icon = 'check';
        text = `Blood type compatible: ${after_blood_filter}`;
        break;
      case '56day_filter':
        icon = 'check';
        text = `56-day recovery check: ${after_56day}`;
        break;
      case 'distance_filter':
        icon = 'check';
        text = `Within travel radius: ${after_distance}`;
        break;
      case 'ranking':
        icon = 'loading';
        text = 'Ranking by ETA, reliability & scarcity...';
        break;
      case 'broadcasting':
        icon = 'radio';
        text = label || `Broadcasting Ring 1...`;
        break;
      default:
        text = label || phase;
    }

    setStreamItems(prev => [...prev, { phase, icon, text, timestamp: Date.now() }]);
  }, [searchProgress]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [streamItems]);

  const renderIcon = (type, isLatest) => {
    switch (type) {
      case 'check':
        return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />;
      case 'radio':
        return <Radio className="w-3.5 h-3.5 text-blue-400 shrink-0 animate-pulse" />;
      case 'loading':
      default:
        return isLatest 
          ? <Loader2 className="w-3.5 h-3.5 text-blue-400 shrink-0 animate-spin" />
          : <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />;
    }
  };

  const showCountdown = ringCountdown && ['RING1', 'RING2'].includes(currentState);
  const isSearching = ['CREATED', 'AI_PROCESSING', 'VALIDATING', 'SEARCHING', 'MATCHING', 'RING1', 'RING2', 'WAITING'].includes(currentState);

  if (!isSearching && streamItems.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="bg-[#0A0A0C]/90 backdrop-blur-xl border border-white/8 rounded-2xl p-4 w-full max-w-sm shadow-[0_8px_32px_rgba(0,0,0,0.6)] overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
          <span className="text-[10px] font-black text-[#86868B] uppercase tracking-widest">
            Live Search
          </span>
        </div>
        {showCountdown && (
          <div className="flex items-center gap-1.5 bg-amber-500/10 px-2 py-0.5 rounded-full">
            <Timer className="w-3 h-3 text-amber-400" />
            <span className="text-xs font-black text-amber-400 tabular-nums">
              {ringCountdown.seconds_remaining}s
            </span>
          </div>
        )}
      </div>

      {/* Stream Items */}
      <div ref={scrollRef} className="space-y-2 max-h-[200px] overflow-y-auto no-scrollbar">
        <AnimatePresence>
          {streamItems.map((item, idx) => (
            <motion.div
              key={item.phase}
              initial={{ opacity: 0, x: -12, height: 0 }}
              animate={{ opacity: 1, x: 0, height: 'auto' }}
              transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1], delay: 0.05 }}
              className="flex items-start gap-2 event-stream-item"
            >
              <div className="mt-0.5">
                {renderIcon(item.icon, idx === streamItems.length - 1)}
              </div>
              <span className={`text-xs font-medium leading-tight ${
                idx === streamItems.length - 1 ? 'text-white' : 'text-[#86868B]'
              }`}>
                {item.text}
              </span>
            </motion.div>
          ))}
        </AnimatePresence>

        {/* Countdown details */}
        {showCountdown && ringCountdown.donors_viewing > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2 pt-1 border-t border-white/5 mt-2"
          >
            <Eye className="w-3.5 h-3.5 text-blue-400 shrink-0" />
            <span className="text-xs text-blue-400 font-medium">
              {ringCountdown.donors_viewing} donor{ringCountdown.donors_viewing !== 1 ? 's' : ''} viewing request
            </span>
          </motion.div>
        )}

        {/* Current state indicator */}
        {currentState === 'DONOR_ACCEPTED' && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            className="flex items-center gap-2 pt-2 border-t border-emerald-500/20 mt-2"
          >
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            <span className="text-sm font-black text-emerald-400">Donor accepted!</span>
          </motion.div>
        )}
      </div>

      {/* Progress bar */}
      {showCountdown && (
        <div className="mt-3 h-1 bg-white/5 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-amber-500 to-amber-600 rounded-full"
            initial={{ width: '0%' }}
            animate={{ width: `${ringCountdown.progress_pct || 0}%` }}
            transition={{ duration: 0.5, ease: 'linear' }}
          />
        </div>
      )}
    </motion.div>
  );
}
