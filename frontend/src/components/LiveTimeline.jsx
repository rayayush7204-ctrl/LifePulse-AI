import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function LiveTimeline({ events, currentState }) {
  const scrollRef = useRef(null);

  // Auto-scroll to top (since events are prepended in the parent) or bottom if appended
  // In EmergencyLiveTracker, they are prepended: setEvents(prev => [new, ...prev])
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = 0;
    }
  }, [events]);

  const getStateColor = (state) => {
    const s = state?.toUpperCase() || '';
    if (['CREATED', 'AI_PROCESSING', 'VALIDATING'].includes(s)) return 'bg-slate-400';
    if (['SEARCHING'].includes(s)) return 'bg-blue-500 shadow-[0_0_12px_rgba(59,130,246,0.6)]';
    if (['MATCHING', 'RING1', 'RING2'].includes(s)) return 'bg-amber-500 shadow-[0_0_12px_rgba(245,158,11,0.6)]';
    if (['WAITING'].includes(s)) return 'bg-red-500 shadow-[0_0_12px_rgba(239,68,68,0.6)]';
    if (['DONOR_ACCEPTED'].includes(s)) return 'bg-emerald-400 shadow-[0_0_12px_rgba(52,211,153,0.6)]';
    if (['TRACKING', 'ARRIVING', 'ARRIVED'].includes(s)) return 'bg-emerald-500 shadow-[0_0_12px_rgba(16,185,129,0.8)]';
    if (['DONATION_STARTED', 'DONATION_COMPLETED'].includes(s)) return 'bg-purple-500 shadow-[0_0_12px_rgba(168,85,247,0.6)]';
    return 'bg-slate-500';
  };

  const getTextColor = (state) => {
    const s = state?.toUpperCase() || '';
    if (['SEARCHING'].includes(s)) return 'text-blue-400';
    if (['MATCHING', 'RING1', 'RING2'].includes(s)) return 'text-amber-400';
    if (['DONOR_ACCEPTED', 'TRACKING', 'ARRIVING', 'ARRIVED'].includes(s)) return 'text-emerald-400';
    if (['WAITING'].includes(s)) return 'text-red-400';
    return 'text-white';
  };

  return (
    <div className="glass-panel p-6 h-full flex flex-col pointer-events-auto">
      <div className="flex items-center justify-between mb-6 border-b border-white/10 pb-2">
        <h2 className="text-white font-black uppercase tracking-widest text-xs">
          Event Log
        </h2>
        {/* Pulsing indicator for active state */}
        <div className="flex items-center gap-2">
          <span className="text-[9px] font-bold text-[#86868B] uppercase">Live</span>
          <div className="w-2 h-2 rounded-full bg-blood-500 animate-pulse shadow-[0_0_8px_rgba(229,9,20,0.8)]" />
        </div>
      </div>
      
      <div ref={scrollRef} className="flex-1 overflow-y-auto pr-2 no-scrollbar smooth-scroll">
        <div className="relative border-l-2 border-white/10 ml-3 space-y-6 pb-8 pt-2">
          <AnimatePresence>
            {events.map((evt, idx) => (
              <motion.div
                key={evt.id}
                initial={{ opacity: 0, x: -20, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                layout
                transition={{ duration: 0.3, ease: "easeOut" }}
                className="relative pl-6"
              >
                {/* Dot */}
                <div 
                  className={`absolute -left-[5px] top-1 w-2.5 h-2.5 rounded-full ${idx === 0 ? getStateColor(evt.state) : 'bg-[#86868B]'}`} 
                />
                
                {/* Content */}
                <div className="flex flex-col gap-1">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-[#86868B] font-mono">{evt.timestamp}</span>
                    <span className={`text-[9px] font-black uppercase tracking-wider px-2 py-0.5 rounded border ${
                        idx === 0 
                          ? `bg-white/10 border-white/20 ${getTextColor(evt.state)}` 
                          : 'bg-transparent border-white/5 text-[#86868B]'
                    }`}>
                      {evt.state}
                    </span>
                  </div>
                  <p className={`text-sm font-medium ${idx === 0 ? 'text-white' : 'text-[#86868B]'}`}>
                    {evt.message}
                  </p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
