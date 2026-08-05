import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Navigation, ShieldCheck, HeartPulse, Activity } from 'lucide-react';

export default function SearchingHUD({ currentState, hudData }) {
  if (['DONOR_ACCEPTED', 'TRACKING', 'ARRIVING', 'ARRIVED', 'DONATION_COMPLETED'].includes(currentState)) {
    return null;
  }

  const stepIcon = () => {
    switch(hudData.step) {
      case 'initialization': return <Activity className="w-8 h-8 text-blood-500 animate-pulse" />;
      case 'donors_found': return <Navigation className="w-8 h-8 text-blue-500 animate-pulse" />;
      case 'filtering_blood': return <HeartPulse className="w-8 h-8 text-emerald-500 animate-pulse" />;
      case 'filtered': return <ShieldCheck className="w-8 h-8 text-emerald-500 animate-pulse" />;
      default: return <Navigation className="w-8 h-8 text-blood-500 animate-pulse" />;
    }
  };

  return (
    <motion.div 
      initial={{ y: 50, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      className="bg-[#0A0A0C] border border-white/10 rounded-[32px] p-6 shadow-[0_-10px_40px_rgba(0,0,0,0.5)] overflow-hidden relative w-full"
    >
      <div className="absolute top-0 left-0 right-0 h-1 bg-blood-500/20 overflow-hidden">
        <motion.div 
          className="h-full bg-blood-500" 
          initial={{ x: '-100%' }} 
          animate={{ x: '100%' }} 
          transition={{ repeat: Infinity, duration: 1.5, ease: "linear" }} 
        />
      </div>
      
      <div className="flex flex-col items-center text-center space-y-4">
        <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center border border-white/10">
          {stepIcon()}
        </div>
        
        <div>
          <h2 className="text-xl font-black text-white tracking-tight uppercase">
            {currentState === 'CREATED' ? 'Initializing...' : 
             currentState === 'SEARCHING' ? 'Running Analytics...' : 
             currentState === 'MATCHING' ? 'Ranking Matches...' : 
             `Broadcasting Ring ${hudData.ring || 1}`}
          </h2>
          
          <AnimatePresence mode="wait">
            <motion.p 
              key={hudData.step}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="text-sm text-[#86868B] mt-2 font-mono"
            >
              {hudData.count !== undefined ? (
                 <span className="text-white text-lg font-black mr-2">{hudData.count}</span>
              ) : null}
              {hudData.step === 'initialization' && "Calibrating radar coordinates..."}
              {hudData.step === 'donors_found' && "Active donors found in region."}
              {hudData.step === 'filtering_blood' && "Filtering by medical rules & 56-day recovery..."}
              {hudData.step === 'filtered' && "Eligible donors passed clinical checks."}
              {hudData.step === 'ranking' && "Scoring by ETA and reliability..."}
              {hudData.step === 'ring_escalation' && "Waiting for donor acceptance (45s timeout)..."}
            </motion.p>
          </AnimatePresence>
        </div>
      </div>
    </motion.div>
  );
}
