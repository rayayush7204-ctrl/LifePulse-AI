import React, { useState, useEffect, useRef } from 'react';
import { motion, useScroll, useTransform, useInView } from 'framer-motion';
import { Activity, Droplet, ShieldCheck, Heart, Building2, Sparkles, MapPin, Send, Zap, Clock, Award, PhoneCall, ArrowRight, Navigation, Users, Timer } from 'lucide-react';
import { submitEmergencyRequest } from '../services/api';
import { useGPS } from '../App';

// ── Cinematic Counter ────────────────────────────────────────────
function AnimatedCounter({ target, suffix = '', className = '' }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, margin: "-50px" });

  useEffect(() => {
    if (!isInView) return;
    const duration = 1500;
    const steps = 60;
    const increment = target / steps;
    let current = 0;
    const timer = setInterval(() => {
      current += increment;
      if (current >= target) {
        setCount(target);
        clearInterval(timer);
      } else {
        setCount(Math.round(current));
      }
    }, duration / steps);
    return () => clearInterval(timer);
  }, [isInView, target]);

  return (
    <span ref={ref} className={className}>
      {typeof target === 'number' && target < 1 ? count.toFixed(1) : count}{suffix}
    </span>
  );
}

// ── Cinematic Floating Orb ───────────────────────────────────────────
function CinematicOrb() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none flex items-center justify-center -z-10">
      <motion.div
        animate={{
          scale: [1, 1.05, 1],
          rotate: [0, 90, 180, 270, 360],
        }}
        transition={{
          duration: 20,
          ease: "linear",
          repeat: Infinity,
        }}
        className="relative w-[600px] h-[600px] opacity-40 blur-[80px]"
      >
        <div className="absolute inset-0 bg-gradient-to-tr from-blood-800 to-blood-500 rounded-full mix-blend-screen" />
        <div className="absolute inset-10 bg-gradient-to-bl from-red-600 to-[#111111] rounded-full mix-blend-overlay" />
      </motion.div>
      
      {/* Particles */}
      {[...Array(15)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-1 h-1 bg-blood-500 rounded-full"
          animate={{
            y: ["0vh", "-100vh"],
            opacity: [0, 1, 0],
            x: Math.random() * 400 - 200,
          }}
          transition={{
            duration: Math.random() * 5 + 5,
            repeat: Infinity,
            ease: "linear",
            delay: Math.random() * 5,
          }}
          style={{
            left: `${Math.random() * 100}%`,
            top: `${Math.random() * 100}%`,
          }}
        />
      ))}
    </div>
  );
}

export default function ActionHubHome({ onNavigateTab, onRequestSubmitted }) {
  const gps = useGPS();
  const { scrollYProgress } = useScroll();
  const yHero = useTransform(scrollYProgress, [0, 1], [0, 300]);
  const opacityHero = useTransform(scrollYProgress, [0, 0.2], [1, 0]);

  const handleQuickDemo = async (city) => {
    let demoPayload = {
      patient_name: "Emergency Patient",
      requester_phone: "+14155550999",
      hospital_name: "UCSF Medical Center",
      blood_type: "O-",
      donation_type: "WHOLE_BLOOD",
      units_needed: 2,
      urgency_level: "CRITICAL",
      latitude: 37.7631,
      longitude: -122.4578,
      notes: `Instant ${city} emergency demo request.`
    };

    if (city === "SF") {
      demoPayload.hospital_name = "UCSF Medical Center";
      demoPayload.latitude = 37.7631;
      demoPayload.longitude = -122.4578;
    } else if (city === "BLR") {
      demoPayload.hospital_name = "Manipal Hospital";
      demoPayload.latitude = 12.9585;
      demoPayload.longitude = 77.6483;
    } else if (city === "MUM") {
      demoPayload.hospital_name = "Lilavati Hospital";
      demoPayload.latitude = 19.0515;
      demoPayload.longitude = 72.8286;
    } else if (city === "GPS") {
      const loc = gps?.location;
      if (loc) {
        demoPayload.hospital_name = "My Current GPS Location";
        demoPayload.latitude = loc.latitude;
        demoPayload.longitude = loc.longitude;
      } else {
        demoPayload.hospital_name = "Local Emergency Center";
        demoPayload.latitude = 37.7749;
        demoPayload.longitude = -122.4194;
      }
    }

    try {
      const res = await submitEmergencyRequest(demoPayload);
      onRequestSubmitted(res);
    } catch (e) {
      console.error(e);
    }
  };

  const containerVariants = {
    hidden: { opacity: 0 },
    show: {
      opacity: 1,
      transition: { staggerChildren: 0.1 }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    show: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 300, damping: 24 } }
  };

  return (
    <div className="space-y-16 max-w-6xl mx-auto pb-16 relative">
      
      {/* Cinematic Hero */}
      <motion.div 
        style={{ y: yHero, opacity: opacityHero }}
        className="relative min-h-[60vh] flex flex-col justify-center pt-10 pb-20"
      >
        <CinematicOrb />
        
        <motion.div 
          variants={containerVariants}
          initial="hidden"
          animate="show"
          className="max-w-4xl space-y-8 relative z-10 mx-auto text-center"
        >
          <motion.div variants={itemVariants} className="flex justify-center">
            <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-bold tracking-[0.2em] text-[#86868B] uppercase backdrop-blur-md">
              <Sparkles className="w-3.5 h-3.5 text-blood-500" />
              AI-Powered Emergency Dispatch
            </div>
          </motion.div>

          <motion.h1 variants={itemVariants} className="text-5xl sm:text-7xl lg:text-8xl font-black text-[#F5F5F7] tracking-tight leading-[1.1]">
            Every second <br />
            <span className="gradient-text-blood">matters.</span>
          </motion.h1>

          <motion.p variants={itemVariants} className="text-lg sm:text-xl text-[#86868B] leading-relaxed max-w-2xl mx-auto font-medium">
            AI connects the right donor to the right patient — when every minute counts. Real-time proximity, clinical compatibility, instant alerts.
          </motion.p>

          <motion.div variants={itemVariants} className="flex flex-col sm:flex-row items-center justify-center gap-4 pt-4">
            <button
              onClick={() => onNavigateTab('request')}
              className="w-full sm:w-auto px-8 py-4 rounded-full bg-blood-500 text-white font-bold text-lg hover:bg-blood-600 transition-all hover-lift flex items-center justify-center gap-2 shadow-[0_0_40px_rgba(229,9,20,0.4)]"
            >
              REQUEST BLOOD
              <ArrowRight className="w-5 h-5" />
            </button>
            <button
              onClick={() => onNavigateTab('donor-portal')}
              className="w-full sm:w-auto px-8 py-4 rounded-full bg-white/5 text-white font-bold text-lg hover:bg-white/10 transition-all border border-white/10 hover-lift"
            >
              BECOME A DONOR
            </button>
          </motion.div>

          {/* Quick 1-Click Demo Buttons (Minimized visual impact) */}
          <motion.div variants={itemVariants} className="pt-12">
             <div className="text-[10px] font-bold text-[#86868B] uppercase tracking-[0.2em] mb-4">
              Developer Quick Demos
            </div>
            <div className="flex flex-wrap justify-center gap-3">
              <button
                onClick={() => handleQuickDemo("GPS")}
                className="px-4 py-2 rounded-full bg-[#111111] text-[#86868B] border border-white/5 hover:text-white hover:border-white/10 transition-colors text-xs font-semibold flex items-center gap-2"
              >
                <Navigation className="w-3.5 h-3.5" /> GPS
              </button>
              {["SF", "BLR", "MUM"].map((city) => (
                <button
                  key={city}
                  onClick={() => handleQuickDemo(city)}
                  className="px-4 py-2 rounded-full bg-[#111111] text-[#86868B] border border-white/5 hover:text-white hover:border-white/10 transition-colors text-xs font-semibold"
                >
                  {city}
                </button>
              ))}
            </div>
          </motion.div>
        </motion.div>
      </motion.div>

      {/* Feature Action Grid */}
      <motion.div 
        initial={{ opacity: 0, y: 40 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-100px" }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
      >
        {[
          { id: 'request', title: 'Emergency', desc: 'Instant AI dispatch & GPS positioning.', icon: Activity, color: 'text-blood-500' },
          { id: 'donor-portal', title: 'Donor Hub', desc: 'Register, track timer, view requests.', icon: Heart, color: 'text-pink-500' },
          { id: 'banks', title: 'Blood Banks', desc: 'Live stock inventory & routing.', icon: Building2, color: 'text-amber-500' },
          { id: 'audit', title: 'Audit Log', desc: 'Medical compliance audit trail.', icon: ShieldCheck, color: 'text-emerald-500' },
        ].map(({ id, title, desc, icon: Icon, color }) => (
          <div
            key={id}
            onClick={() => onNavigateTab(id)}
            className="group cursor-pointer p-8 rounded-3xl bg-[#111111]/40 border border-white/5 hover:border-white/10 hover:bg-[#111111]/80 backdrop-blur-xl transition-all duration-500 hover-lift flex flex-col"
          >
            <div className={`w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center mb-6 group-hover:scale-110 transition-transform duration-500 ${color}`}>
              <Icon className="w-6 h-6" />
            </div>
            <h3 className="font-bold text-white text-xl mb-2">{title}</h3>
            <p className="text-[#86868B] text-sm leading-relaxed flex-1">{desc}</p>
            <div className={`mt-6 text-xs font-bold uppercase tracking-wider flex items-center gap-2 ${color} opacity-0 group-hover:opacity-100 transition-opacity duration-300 transform -translate-x-2 group-hover:translate-x-0`}>
              Explore <ArrowRight className="w-3.5 h-3.5" />
            </div>
          </div>
        ))}
      </motion.div>

      {/* Cinematic Statistics */}
      <motion.div 
        initial={{ opacity: 0 }}
        whileInView={{ opacity: 1 }}
        viewport={{ once: true }}
        transition={{ duration: 1 }}
        className="py-12 border-t border-white/5"
      >
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
          <div>
            <div className="text-4xl sm:text-5xl font-black text-white tracking-tighter">
              <AnimatedCounter target={1284} />
            </div>
            <div className="text-xs text-[#86868B] font-bold mt-2 uppercase tracking-widest">
              Lives Connected
            </div>
          </div>
          <div>
            <div className="text-4xl sm:text-5xl font-black text-white tracking-tighter">
              <AnimatedCounter target={328} />
            </div>
            <div className="text-xs text-[#86868B] font-bold mt-2 uppercase tracking-widest">
              Donors Available
            </div>
          </div>
          <div>
            <div className="text-4xl sm:text-5xl font-black text-blood-500 tracking-tighter">
              <AnimatedCounter target={12} suffix="m" />
            </div>
            <div className="text-xs text-[#86868B] font-bold mt-2 uppercase tracking-widest">
              Avg Match Time
            </div>
          </div>
          <div>
            <div className="text-4xl sm:text-5xl font-black text-white tracking-tighter">
              <AnimatedCounter target={100} suffix="%" />
            </div>
            <div className="text-xs text-[#86868B] font-bold mt-2 uppercase tracking-widest">
              ABO/Rh Safety
            </div>
          </div>
        </div>
      </motion.div>

    </div>
  );
}
