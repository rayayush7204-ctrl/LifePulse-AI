import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, AlertTriangle, Building2, MapPin, Send, CheckCircle2, RefreshCw, User, Phone, Mic, Navigation, ChevronDown, ChevronUp } from 'lucide-react';
import { submitEmergencyRequest, parseVoiceSOS } from '../services/api';
import { useGPS } from '../App';
import { useToast } from './NotificationToast';
import { reverseGeocode, haversineDistance } from '../services/geolocation';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import L from 'leaflet';

const BLOOD_TYPES = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"];

const PRESET_HOSPITALS = [
  { name: "UCSF Medical Center", city: "San Francisco", lat: 37.7631, lon: -122.4578 },
  { name: "Zuckerberg SF Gen Hospital", city: "San Francisco", lat: 37.7554, lon: -122.4057 },
  { name: "Manipal Hospital", city: "Bangalore", lat: 12.9585, lon: 77.6483 },
  { name: "Lilavati Hospital", city: "Mumbai", lat: 19.0515, lon: 72.8286 }
];

const VOICE_DICTATION_PRESETS = [
  "Urgent! Need 3 bags of O negative blood at UCSF hospital immediately for trauma patient in ICU!",
  "Emergency surgery at Zuckerberg SF General! Need 2 units A positive blood asap."
];

// Minimal pin
const pinIcon = L.divIcon({
  className: 'custom-leaflet-marker',
  html: `<div style="background: #e50914; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 20px rgba(229,9,20,0.8);"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 8]
});

function LocationPicker({ position, onPositionChange }) {
  useMapEvents({ 
    click(e) { 
      onPositionChange([e.latlng.lat, e.latlng.lng]); 
    } 
  });
  return position ? <Marker position={position} icon={pinIcon} /> : null;
}

export default function EmergencyRequestForm({ onRequestSubmitted }) {
  const gps = useGPS();
  const { addToast } = useToast();

  const [selectedBloodType, setSelectedBloodType] = useState("O-");
  const [unitsNeeded, setUnitsNeeded] = useState(2);
  const [selectedHospital, setSelectedHospital] = useState(PRESET_HOSPITALS[0]);
  const [customMapPos, setCustomMapPos] = useState(null);
  
  // Advanced Details
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [patientName, setPatientName] = useState("");
  const [requesterPhone, setRequesterPhone] = useState("");
  const [urgencyLevel, setUrgencyLevel] = useState("CRITICAL");
  const [notes, setNotes] = useState("");

  const [isListening, setIsListening] = useState(false);
  const [isParsingAI, setIsParsingAI] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [sortedHospitals, setSortedHospitals] = useState(PRESET_HOSPITALS);

  useEffect(() => {
    if (gps?.location) {
      const { latitude, longitude } = gps.location;
      const withDist = PRESET_HOSPITALS.map(h => ({
        ...h,
        _dist: haversineDistance(latitude, longitude, h.lat, h.lon)
      }));
      withDist.sort((a, b) => a._dist - b._dist);
      setSortedHospitals(withDist);
      
      // Auto-select nearest hospital if no custom pos
      if (!customMapPos) {
        setSelectedHospital(withDist[0]);
      }
    }
  }, [gps?.location]);

  useEffect(() => {
    if (customMapPos) {
      const [lat, lon] = customMapPos;
      reverseGeocode(lat, lon).then(addr => {
        setSelectedHospital({
          name: addr.short || "Custom Location",
          city: addr.city || `GPS (${lat.toFixed(4)}, ${lon.toFixed(4)})`,
          lat,
          lon
        });
      });
    }
  }, [customMapPos]);

  const applyParsedFields = (parsed, sourceText) => {
    if (parsed.blood_type && BLOOD_TYPES.includes(parsed.blood_type)) setSelectedBloodType(parsed.blood_type);
    if (parsed.units_needed) setUnitsNeeded(parsed.units_needed);
    if (parsed.urgency_level) setUrgencyLevel(parsed.urgency_level);
    if (parsed.hospital_name && parsed.hospital_name !== "Hospital (Extracted from Notes)") {
      const matchedHosp = PRESET_HOSPITALS.find(h => h.name.toLowerCase().includes(parsed.hospital_name.toLowerCase()));
      if (matchedHosp) setSelectedHospital(matchedHosp);
    }
    setNotes(`[AI Extracted: "${sourceText}"]`);
  };

  const handleVoiceSOSDictation = async (presetText = null) => {
    if (presetText) {
      setIsParsingAI(true);
      try {
        const parsed = await parseVoiceSOS(presetText);
        applyParsedFields(parsed, presetText);
        addToast({ title: 'Voice Parsed', message: `Extracted: ${parsed.blood_type}, ${parsed.units_needed} units`, type: 'success' });
      } catch (err) {} finally { setIsParsingAI(false); }
      return;
    }
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      handleVoiceSOSDictation(VOICE_DICTATION_PRESETS[0]);
      return;
    }
    try {
      const recognition = new SpeechRecognition();
      recognition.onstart = () => setIsListening(true);
      recognition.onresult = async (event) => {
        setIsListening(false);
        setIsParsingAI(true);
        try {
          const transcript = event.results[0][0].transcript;
          const parsed = await parseVoiceSOS(transcript);
          applyParsedFields(parsed, transcript);
        } catch (err) {} finally { setIsParsingAI(false); }
      };
      recognition.onerror = () => { setIsListening(false); handleVoiceSOSDictation(VOICE_DICTATION_PRESETS[0]); };
      recognition.start();
    } catch {
      setIsListening(false); handleVoiceSOSDictation(VOICE_DICTATION_PRESETS[0]);
    }
  };

  const handleUseCurrentLocation = () => {
    const loc = gps?.location;
    if (loc) {
      setCustomMapPos([loc.latitude, loc.longitude]);
    } else {
      addToast({ title: 'GPS Unavailable', message: 'Please allow location access in your browser or select on map.', type: 'alert' });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      const hosp = selectedHospital || PRESET_HOSPITALS[0];
      const payload = {
        patient_name: patientName.trim() || "Emergency Patient",
        requester_phone: requesterPhone.trim() || "+10000000000",
        hospital_name: hosp.name || "Unknown Hospital",
        blood_type: selectedBloodType || "O-",
        donation_type: "WHOLE_BLOOD",
        units_needed: parseInt(unitsNeeded) || 2,
        urgency_level: urgencyLevel || "CRITICAL",
        latitude: parseFloat(hosp.lat) || 37.7631,
        longitude: parseFloat(hosp.lon) || -122.4578,
        notes: notes.trim() || "Urgent emergency request."
      };

      const response = await submitEmergencyRequest(payload);
      
      // Navigate to live tracker with 0.3s timeout for cinematic transition effect
      setTimeout(() => {
        onRequestSubmitted(response);
      }, 300);

    } catch (err) {
      console.error("[Submit Error]", err);
      setIsSubmitting(false);
    }
  };

  const mapCenter = customMapPos || [selectedHospital.lat, selectedHospital.lon];

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 top-[64px] z-0 overflow-hidden bg-[#050505] flex flex-col"
    >
      {/* Full-Screen Map Background */}
      <div className="absolute inset-0 z-0">
        <MapContainer center={mapCenter} zoom={14} zoomControl={false} scrollWheelZoom={true} className="w-full h-full opacity-60">
          <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
          <LocationPicker position={mapCenter} onPositionChange={setCustomMapPos} />
        </MapContainer>
        {/* Gradients to fade map into UI */}
        <div className="absolute inset-0 bg-gradient-to-b from-[#050505]/40 via-transparent to-[#050505] pointer-events-none" />
      </div>

      {/* Floating Voice AI FAB */}
      <div className="absolute top-6 right-6 z-20">
        <button 
          type="button" 
          onClick={() => handleVoiceSOSDictation()}
          className={`flex items-center gap-3 px-4 py-3 rounded-full backdrop-blur-xl border border-white/10 shadow-2xl transition-all ${
            isListening || isParsingAI 
              ? 'bg-blood-500/20 border-blood-500 text-blood-500 animate-pulse' 
              : 'bg-[#0A0A0C]/80 text-white hover:bg-white/10'
          }`}
        >
          {isParsingAI ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Mic className="w-5 h-5" />}
          <span className="text-sm font-bold tracking-widest uppercase">
            {isListening ? "Listening..." : isParsingAI ? "Parsing AI..." : "Voice SOS"}
          </span>
        </button>
      </div>

      {/* Bottom Sheet UI */}
      <div className="relative z-10 mt-auto w-full max-w-2xl mx-auto p-4 pb-8 sm:pb-12">
        <form onSubmit={handleSubmit} className="bg-[#0A0A0C]/90 backdrop-blur-2xl border border-white/10 rounded-3xl p-6 sm:p-8 shadow-[0_-20px_60px_rgba(0,0,0,0.6)]">
          
          <div className="text-center mb-6">
            <h1 className="text-2xl font-black text-white tracking-tight uppercase">Emergency Dispatch</h1>
            <p className="text-[#86868B] text-sm mt-1">Tap map to set hospital location</p>
          </div>

          <div className="space-y-6">
            {/* Blood Type & Units */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="md:col-span-2">
                <label className="block text-[10px] font-bold text-[#86868B] mb-2 uppercase tracking-widest text-center">Patient Blood Group</label>
                <div className="grid grid-cols-4 gap-2">
                  {BLOOD_TYPES.map((bt) => (
                    <button 
                      key={bt} type="button" onClick={() => setSelectedBloodType(bt)}
                      className={`relative py-3 rounded-xl font-black text-lg transition-all duration-300 ${
                        selectedBloodType === bt
                          ? 'bg-blood-500 text-white shadow-[0_0_20px_rgba(229,9,20,0.4)] scale-105 border-none'
                          : 'bg-white/5 text-[#86868B] border border-white/5 hover:border-white/20 hover:bg-white/10'
                      }`}
                    >
                      {bt}
                    </button>
                  ))}
                </div>
              </div>

              <div className="md:col-span-1">
                <label className="block text-[10px] font-bold text-[#86868B] mb-2 uppercase tracking-widest text-center">Units Needed</label>
                <div className="flex items-center justify-center gap-4 bg-white/5 border border-white/5 rounded-2xl py-3">
                  <button type="button" onClick={() => setUnitsNeeded(Math.max(1, unitsNeeded-1))} className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold hover:bg-white/10 text-xl">-</button>
                  <span className="text-3xl font-black text-white w-8 text-center">{unitsNeeded}</span>
                  <button type="button" onClick={() => setUnitsNeeded(unitsNeeded+1)} className="w-10 h-10 rounded-full flex items-center justify-center text-white font-bold hover:bg-white/10 text-xl">+</button>
                </div>
              </div>
            </div>

            {/* Location Display */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center shrink-0">
                  <MapPin className="w-5 h-5 text-blue-400" />
                </div>
                <div>
                  <div className="text-[10px] font-bold text-[#86868B] uppercase tracking-wider mb-0.5">Hospital Location</div>
                  <div className="font-bold text-white text-sm sm:text-base line-clamp-1">{selectedHospital.name}</div>
                </div>
              </div>
              <button 
                type="button" 
                onClick={handleUseCurrentLocation}
                className="px-3 py-1.5 bg-white/10 hover:bg-white/20 rounded-full text-[10px] font-bold tracking-widest transition-colors flex items-center gap-1 shrink-0"
              >
                <Navigation className="w-3 h-3" /> GPS
              </button>
            </div>

            {/* Advanced Details Toggle */}
            <div>
              <button 
                type="button" 
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="w-full py-2 flex items-center justify-center gap-2 text-[#86868B] hover:text-white transition-colors text-xs font-bold uppercase tracking-widest"
              >
                {showAdvanced ? 'Hide Details' : 'Advanced Details'} 
                {showAdvanced ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              
              <AnimatePresence>
                {showAdvanced && (
                  <motion.div 
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    className="overflow-hidden mt-4 space-y-4"
                  >
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                        <label className="block text-[10px] font-bold text-[#86868B] uppercase mb-1">Patient Name</label>
                        <input type="text" placeholder="Optional" value={patientName} onChange={(e) => setPatientName(e.target.value)} className="w-full bg-transparent text-white font-bold text-sm focus:outline-none" />
                      </div>
                      <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                        <label className="block text-[10px] font-bold text-[#86868B] uppercase mb-1">Contact Phone</label>
                        <input type="text" placeholder="Optional" value={requesterPhone} onChange={(e) => setRequesterPhone(e.target.value)} className="w-full bg-transparent text-white font-bold text-sm focus:outline-none" />
                      </div>
                    </div>
                    
                    <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                      <label className="block text-[10px] font-bold text-[#86868B] uppercase mb-1">Medical Notes</label>
                      <input type="text" placeholder="Additional details..." value={notes} onChange={(e) => setNotes(e.target.value)} className="w-full bg-transparent text-white font-bold text-sm focus:outline-none" />
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Giant Submit Button */}
            <button 
              type="submit" 
              disabled={isSubmitting}
              className="w-full py-5 rounded-2xl bg-blood-500 text-white font-black text-xl tracking-widest hover:bg-blood-600 transition-all disabled:opacity-50 hover-lift shadow-[0_0_40px_rgba(229,9,20,0.3)] mt-2 flex items-center justify-center gap-3"
            >
              {isSubmitting ? (
                <RefreshCw className="w-6 h-6 animate-spin" />
              ) : (
                <AlertTriangle className="w-6 h-6" />
              )}
              BROADCAST EMERGENCY
            </button>
          </div>
        </form>
      </div>
    </motion.div>
  );
}
