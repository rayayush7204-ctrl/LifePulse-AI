import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Heart, Award, Clock, CheckCircle2, UserPlus, Smartphone, MapPin, Navigation, Eye, EyeOff, Droplet, ArrowRight, ArrowLeft } from 'lucide-react';
import { fetchAllDonors, registerDonor } from '../services/api';
import { useGPS } from '../App';
import { useToast } from './NotificationToast';
import { reverseGeocode } from '../services/geolocation';
import NearbyRequestsFeed from './NearbyRequestsFeed';

const isSimulatorEnabled = import.meta.env.VITE_APP_ENV !== 'production';
const BLOOD_TYPES = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"];

// Blood type compatibility chart
const COMPATIBILITY = {
  "O-": { canDonateTo: ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"], label: "Universal Donor 👑" },
  "O+": { canDonateTo: ["O+", "A+", "B+", "AB+"], label: "High Demand" },
  "A-": { canDonateTo: ["A-", "A+", "AB-", "AB+"], label: "Versatile" },
  "A+": { canDonateTo: ["A+", "AB+"], label: "Common Type" },
  "B-": { canDonateTo: ["B-", "B+", "AB-", "AB+"], label: "Rare & Valuable" },
  "B+": { canDonateTo: ["B+", "AB+"], label: "Useful" },
  "AB-": { canDonateTo: ["AB-", "AB+"], label: "Rare" },
  "AB+": { canDonateTo: ["AB+"], label: "Universal Receiver" },
};

// ── Success Particle Animation ────────────────────────────────
function SuccessParticles() {
  return (
    <div className="absolute inset-0 pointer-events-none flex items-center justify-center overflow-hidden z-50">
      {[...Array(30)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-2 h-2 bg-pink-500 rounded-full"
          initial={{ opacity: 1, scale: 0, x: 0, y: 0 }}
          animate={{
            opacity: 0,
            scale: Math.random() * 2 + 1,
            x: (Math.random() - 0.5) * 400,
            y: (Math.random() - 0.5) * 400,
          }}
          transition={{ duration: Math.random() * 1 + 1, ease: "easeOut" }}
        />
      ))}
      <motion.div
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: [0, 1.2, 1], opacity: [0, 1, 0] }}
        transition={{ duration: 1.5, times: [0, 0.2, 1] }}
        className="w-48 h-48 bg-pink-500/20 rounded-full blur-2xl"
      />
    </div>
  );
}

export default function DonorPortalHub({ onSimulateAlert }) {
  const gps = useGPS();
  const { addToast } = useToast();
  const [donors, setDonors] = useState([]);
  
  // Form State
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [bloodType, setBloodType] = useState("O-");
  const [city, setCity] = useState("");
  const [lastDonationDate, setLastDonationDate] = useState("");
  const [isAvailable, setIsAvailable] = useState(true);
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);
  const [gpsAddress, setGpsAddress] = useState(null);

  useEffect(() => {
    fetchAllDonors().then(setDonors).catch(console.error);
  }, []);

  useEffect(() => {
    if (gps?.location) {
      reverseGeocode(gps.location.latitude, gps.location.longitude)
        .then(addr => {
          setGpsAddress(addr);
          if (!city) setCity(addr.city || addr.short || '');
        });
    }
  }, [gps?.location]);

  const handleRegister = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const loc = gps?.location;
      await registerDonor({
        name, phone, blood_type: bloodType,
        city: city || gpsAddress?.city || "San Francisco",
        latitude: loc?.latitude || 37.7749,
        longitude: loc?.longitude || -122.4194,
        last_donation_date: lastDonationDate || null,
        is_active: true, is_available: isAvailable
      });
      setShowSuccess(true);
      addToast({ title: 'Registration Complete!', message: `Welcome ${name}!`, type: 'success' });
      fetchAllDonors().then(setDonors);
      
      // Reset form after a delay to show success animation
      setTimeout(() => {
        setShowSuccess(false);
        setStep(1);
        setName(""); setPhone("");
      }, 3000);

    } catch (e) {
      addToast({ title: 'Registration Error', message: e.message, type: 'alert' });
    } finally {
      setIsSubmitting(false);
    }
  };

  const nextStep = () => setStep(prev => Math.min(prev + 1, 4));
  const prevStep = () => setStep(prev => Math.max(prev - 1, 1));

  const formVariants = {
    hidden: { opacity: 0, x: 20 },
    visible: { opacity: 1, x: 0, transition: { type: 'spring', stiffness: 300, damping: 30 } },
    exit: { opacity: 0, x: -20, transition: { duration: 0.2 } }
  };

  const getRecoveryDays = (lastDate) => {
    if (!lastDate) return null;
    const diff = Math.floor((Date.now() - new Date(lastDate).getTime()) / (1000 * 60 * 60 * 24));
    return { days: diff, eligible: diff >= 56 };
  };

  const compat = COMPATIBILITY[bloodType];

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-8 max-w-6xl mx-auto"
    >
      {showSuccess && <SuccessParticles />}

      {/* Header */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-6 pb-6 border-b border-white/5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-pink-500/10 flex items-center justify-center border border-pink-500/20">
            <Heart className="w-6 h-6 text-pink-500 fill-pink-500 animate-pulse" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-tight">Donor Hub</h1>
            <p className="text-xs text-[#86868B]">Register, view compatibility, and track nearby emergencies.</p>
          </div>
        </div>
        <div className="flex items-center gap-3 w-full md:w-auto">
          <button
            onClick={() => setIsAvailable(!isAvailable)}
            className={`flex-1 md:flex-none px-4 py-2 rounded-full text-xs font-bold flex items-center justify-center gap-2 transition-colors border ${
              isAvailable
                ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                : 'bg-[#111111] text-[#86868B] border-white/10'
            }`}
          >
            {isAvailable ? <><Eye className="w-4 h-4" /> Available</> : <><EyeOff className="w-4 h-4" /> Hidden</>}
          </button>
          {isSimulatorEnabled && (
            <button onClick={onSimulateAlert}
              className="flex-1 md:flex-none px-4 py-2 bg-pink-500 hover:bg-pink-600 text-white font-bold text-xs rounded-full flex items-center justify-center gap-2 transition hover-lift">
              <Smartphone className="w-4 h-4" /> Simulate Alert
            </button>
          )}
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Left Column: Progressive Registration */}
        <div className="lg:col-span-5 space-y-6">
          <div className="glass-panel p-6 sm:p-8 rounded-3xl relative overflow-hidden border border-pink-500/20">
            {/* Step Indicators */}
            <div className="flex justify-between mb-8 relative z-10">
              {[1, 2, 3, 4].map(s => (
                <div key={s} className={`h-1 flex-1 mx-1 rounded-full transition-colors duration-500 ${s <= step ? 'bg-pink-500' : 'bg-white/10'}`} />
              ))}
            </div>

            <div className="relative min-h-[300px]">
              <AnimatePresence mode="wait">
                {/* STEP 1: Identity */}
                {step === 1 && (
                  <motion.div key="step1" variants={formVariants} initial="hidden" animate="visible" exit="exit" className="space-y-6">
                    <h3 className="text-xl font-black text-white">Join the Network</h3>
                    <p className="text-sm text-[#86868B]">Enter your details to receive targeted life-saving alerts.</p>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-xs font-bold text-[#86868B] mb-2 uppercase tracking-widest">Full Name</label>
                        <input type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Alex Johnson"
                          className="w-full bg-transparent text-lg text-white font-bold border-b border-white/20 focus:border-pink-500 focus:outline-none pb-2 transition-colors" />
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-[#86868B] mb-2 uppercase tracking-widest">Phone Number</label>
                        <input type="text" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+1 415 555 0199"
                          className="w-full bg-transparent text-lg text-white font-bold border-b border-white/20 focus:border-pink-500 focus:outline-none pb-2 transition-colors" />
                      </div>
                    </div>
                    <button onClick={nextStep} disabled={!name || !phone}
                      className="mt-8 w-full py-4 bg-white text-black font-bold text-sm rounded-full flex justify-center items-center gap-2 hover:bg-gray-200 transition disabled:opacity-50">
                      Continue <ArrowRight className="w-4 h-4" />
                    </button>
                  </motion.div>
                )}

                {/* STEP 2: Blood Group */}
                {step === 2 && (
                  <motion.div key="step2" variants={formVariants} initial="hidden" animate="visible" exit="exit" className="space-y-6">
                    <h3 className="text-xl font-black text-white">Your Blood Group</h3>
                    <div className="grid grid-cols-4 gap-3">
                      {BLOOD_TYPES.map(bt => (
                        <button key={bt} onClick={() => setBloodType(bt)}
                          className={`py-4 rounded-2xl font-black text-lg transition-all ${
                            bloodType === bt ? 'bg-pink-500 text-white shadow-[0_0_20px_rgba(236,72,153,0.4)]' : 'bg-[#111111] text-[#86868B] border border-white/10 hover:bg-white/5'
                          }`}>
                          {bt}
                        </button>
                      ))}
                    </div>
                    <div className="flex gap-3 pt-6">
                      <button onClick={prevStep} className="p-4 rounded-full bg-[#111111] text-white hover:bg-white/10 border border-white/10"><ArrowLeft className="w-5 h-5"/></button>
                      <button onClick={nextStep} className="flex-1 py-4 bg-white text-black font-bold text-sm rounded-full flex justify-center items-center gap-2 hover:bg-gray-200">
                        Continue <ArrowRight className="w-4 h-4" />
                      </button>
                    </div>
                  </motion.div>
                )}

                {/* STEP 3: Location & Recovery */}
                {step === 3 && (
                  <motion.div key="step3" variants={formVariants} initial="hidden" animate="visible" exit="exit" className="space-y-6">
                    <h3 className="text-xl font-black text-white">Location & Eligibility</h3>
                    <div className="space-y-4">
                      <div>
                        <label className="block text-xs font-bold text-[#86868B] mb-2 uppercase tracking-widest">City Base</label>
                        <div className="relative">
                          <Navigation className="absolute left-0 top-1 w-5 h-5 text-[#86868B]" />
                          <input type="text" value={city} onChange={(e) => setCity(e.target.value)} placeholder={gpsAddress?.city || "San Francisco"}
                            className="w-full bg-transparent pl-8 text-lg text-white font-bold border-b border-white/20 focus:border-pink-500 focus:outline-none pb-2 transition-colors" />
                        </div>
                      </div>
                      <div>
                        <label className="block text-xs font-bold text-[#86868B] mb-2 uppercase tracking-widest">Last Donation (Optional)</label>
                        <input type="date" value={lastDonationDate} onChange={(e) => setLastDonationDate(e.target.value)}
                          className="w-full bg-transparent text-lg text-[#86868B] font-bold border-b border-white/20 focus:border-pink-500 focus:outline-none pb-2" />
                        
                        {lastDonationDate && (() => {
                          const recovery = getRecoveryDays(lastDonationDate);
                          if (!recovery) return null;
                          return (
                            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className={`mt-3 p-3 rounded-xl text-xs font-bold flex items-center gap-2 border ${
                              recovery.eligible ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border-amber-500/30'
                            }`}>
                              <Clock className="w-4 h-4" />
                              {recovery.eligible ? `Eligible (${recovery.days} days)` : `Ineligible (${56 - recovery.days} days left)`}
                            </motion.div>
                          );
                        })()}
                      </div>
                    </div>
                    <div className="flex gap-3 pt-6">
                      <button onClick={prevStep} className="p-4 rounded-full bg-[#111111] text-white hover:bg-white/10 border border-white/10"><ArrowLeft className="w-5 h-5"/></button>
                      <button onClick={nextStep} className="flex-1 py-4 bg-white text-black font-bold text-sm rounded-full flex justify-center items-center gap-2 hover:bg-gray-200">
                        Review <ArrowRight className="w-4 h-4" />
                      </button>
                    </div>
                  </motion.div>
                )}

                {/* STEP 4: Review & Submit */}
                {step === 4 && (
                  <motion.div key="step4" variants={formVariants} initial="hidden" animate="visible" exit="exit" className="space-y-6 text-center">
                    <div className="w-20 h-20 mx-auto rounded-full bg-pink-500/20 flex items-center justify-center border border-pink-500/40 mb-4">
                      <span className="text-3xl font-black text-pink-500">{bloodType}</span>
                    </div>
                    <h3 className="text-2xl font-black text-white">Ready to save lives, {name.split(' ')[0]}?</h3>
                    <p className="text-sm text-[#86868B]">You will receive targeted push alerts when {bloodType} or compatible blood is needed in {city || gpsAddress?.city || 'your area'}.</p>
                    
                    <div className="flex gap-3 pt-6">
                      <button onClick={prevStep} disabled={isSubmitting} className="p-4 rounded-full bg-[#111111] text-white hover:bg-white/10 border border-white/10"><ArrowLeft className="w-5 h-5"/></button>
                      <button onClick={handleRegister} disabled={isSubmitting} className="flex-1 py-4 bg-pink-500 hover:bg-pink-600 text-white font-black text-sm tracking-widest rounded-full flex justify-center items-center shadow-[0_0_30px_rgba(236,72,153,0.4)] disabled:opacity-50">
                        {isSubmitting ? 'REGISTERING...' : 'JOIN NOW'}
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>

          {/* Blood Type Compatibility Card */}
          <div className="glass-panel p-6 rounded-3xl space-y-4 border border-white/5">
            <h4 className="text-xs font-bold text-[#86868B] uppercase tracking-widest flex items-center gap-2">
              <Droplet className="w-4 h-4 text-blood-500" />
              Compatibility Matrix
            </h4>
            <div className="flex items-center gap-3 mb-4">
              <span className="text-4xl font-black text-white">{bloodType}</span>
              <span className="text-xs text-pink-400 font-bold bg-pink-500/10 px-3 py-1 rounded-full border border-pink-500/20">{compat?.label}</span>
            </div>
            <div>
              <div className="text-[10px] text-[#86868B] font-bold uppercase tracking-widest mb-2">Can donate to</div>
              <div className="flex flex-wrap gap-2">
                {compat?.canDonateTo.map(bt => (
                  <span key={bt} className="px-3 py-1.5 text-xs font-black rounded-full bg-[#111111] text-white border border-white/10">
                    {bt}
                  </span>
                ))}
              </div>
            </div>
          </div>

        </div>

        {/* Right Column: Feed & Directory */}
        <div className="lg:col-span-7 space-y-6">
          <NearbyRequestsFeed
            userLat={gps?.location?.latitude}
            userLon={gps?.location?.longitude}
            onHelpRequest={(req) => {
              addToast({ title: 'Alert Accepted', message: `Routing to ${req.hospital_name}`, type: 'success' });
              onSimulateAlert?.(req);
            }}
          />

          <div className="glass-panel p-6 rounded-3xl border border-white/5">
            <h3 className="font-black text-white text-lg mb-6 flex justify-between items-center">
              Active Network 
              <span className="text-xs font-bold text-[#86868B] bg-[#111111] px-3 py-1 rounded-full">{donors.length} Verified</span>
            </h3>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 max-h-[400px] overflow-y-auto pr-2">
              {donors.map((d, idx) => (
                <div key={idx} className="p-4 rounded-2xl bg-[#111111] border border-white/5 hover:border-white/10 transition flex flex-col justify-between group">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <div className="font-bold text-white mb-1">{d.name}</div>
                      <div className="text-[10px] text-[#86868B] flex items-center gap-1"><MapPin className="w-3 h-3"/> {d.city}</div>
                    </div>
                    <span className="w-10 h-10 rounded-full bg-blood-500/10 flex items-center justify-center font-black text-blood-500 border border-blood-500/20">
                      {d.blood_type}
                    </span>
                  </div>
                  <div className="flex items-center justify-between mt-auto">
                    <span className="text-[10px] font-bold text-emerald-400 bg-emerald-500/10 px-2 py-1 rounded-full flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> Eligible
                    </span>
                    <button onClick={onSimulateAlert} className="opacity-0 group-hover:opacity-100 text-[10px] font-bold text-pink-400 hover:text-pink-300 transition uppercase tracking-widest">
                      Alert Donor
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}
