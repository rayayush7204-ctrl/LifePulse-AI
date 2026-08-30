import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Sparkles, AlertTriangle, Building2, MapPin, Send, CheckCircle2, RefreshCw, User, Phone, Mic, Navigation, ChevronDown, ChevronUp, Search } from 'lucide-react';
import { submitEmergencyRequest, parseVoiceSOS } from '../services/api';
import { useGPS } from '../App';
import { useToast } from './NotificationToast';
import { reverseGeocode, forwardGeocode } from '../services/geolocation';
import { MapContainer, TileLayer, Marker, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { SectionErrorBoundary } from './ErrorBoundary';

const BLOOD_TYPES = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"];

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
      onPositionChange([e.latlng.lat, e.latlng.lng], "map_pin");
    }
  });
  return position ? <Marker position={position} icon={pinIcon} /> : null;
}

export default function EmergencyRequestForm({ onRequestSubmitted }) {
  const gps = useGPS();
  const { addToast } = useToast();

  const [selectedBloodType, setSelectedBloodType] = useState("O-");
  const [unitsNeeded, setUnitsNeeded] = useState(2);

  // Location System
  const [locationName, setLocationName] = useState("Current Location");
  const [locationAddress, setLocationAddress] = useState("Locating...");
  const [locationSource, setLocationSource] = useState("gps");
  const [mapCenter, setMapCenter] = useState([37.7749, -122.4194]);
  const [finalCoords, setFinalCoords] = useState(null);

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const searchTimeout = useRef(null);

  // Advanced Details
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [patientName, setPatientName] = useState("");
  const [requesterPhone, setRequesterPhone] = useState("");
  const [urgencyLevel, setUrgencyLevel] = useState("CRITICAL");
  const [notes, setNotes] = useState("");

  const [isListening, setIsListening] = useState(false);
  const [isParsingAI, setIsParsingAI] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Set default GPS location on mount
  useEffect(() => {
    if (gps?.location && locationSource === 'gps') {
      const lat = gps.location.latitude;
      const lon = gps.location.longitude;
      setMapCenter([lat, lon]);
      setFinalCoords([lat, lon]);
      reverseGeocode(lat, lon).then(addr => {
        setLocationName(addr.short || "Current Location");
        setLocationAddress(addr.display || `${lat.toFixed(4)}, ${lon.toFixed(4)}`);
      });
    }
  }, [gps?.location, locationSource]);

  const handleCustomMapPos = (pos, source) => {
    const [lat, lon] = pos;
    setMapCenter(pos);
    setFinalCoords(pos);
    setLocationSource(source);
    setLocationName("Selected Map Pin");
    setLocationAddress("Resolving address...");
    reverseGeocode(lat, lon).then(addr => {
      setLocationName(addr.short || "Selected Location");
      setLocationAddress(addr.display || `${lat.toFixed(4)}, ${lon.toFixed(4)}`);
    });
  };

  const handleSearchChange = (e) => {
    const query = e.target.value;
    setSearchQuery(query);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    if (query.length < 3) {
      setSearchResults([]);
      return;
    }
    setIsSearching(true);
    searchTimeout.current = setTimeout(async () => {
      const results = await forwardGeocode(query);
      setSearchResults(results);
      setIsSearching(false);
    }, 750);
  };

  const handleSelectSearchResult = (result) => {
    const pos = [result.lat, result.lon];
    setMapCenter(pos);
    setFinalCoords(pos);
    setLocationSource("search");
    setLocationName(result.name.split(',')[0]);
    setLocationAddress(result.name);
    setSearchQuery("");
    setSearchResults([]);
  };

  const handleUseCurrentLocation = () => {
    const loc = gps?.location;
    if (loc) {
      setLocationSource('gps');
      const pos = [loc.latitude, loc.longitude];
      setMapCenter(pos);
      setFinalCoords(pos);
      reverseGeocode(loc.latitude, loc.longitude).then(addr => {
        setLocationName(addr.short || "Current Location");
        setLocationAddress(addr.display || `${pos[0].toFixed(4)}, ${pos[1].toFixed(4)}`);
      });
    } else {
      addToast({ title: 'GPS Unavailable', message: 'Please allow location access in your browser or select on map.', type: 'alert' });
    }
  };

  const applyParsedFields = (parsed, sourceText) => {
    if (parsed.blood_type && BLOOD_TYPES.includes(parsed.blood_type)) setSelectedBloodType(parsed.blood_type);
    if (parsed.units_needed) setUnitsNeeded(parsed.units_needed);
    if (parsed.urgency_level) setUrgencyLevel(parsed.urgency_level);
    if (parsed.hospital_name && parsed.hospital_name !== "Hospital (Extracted from Notes)") {
      setSearchQuery(parsed.hospital_name);
      handleSearchChange({target: {value: parsed.hospital_name}});
    }
    setNotes(`[AI Extracted: "${sourceText}"]`);
  };

  const handleVoiceSOSDictation = async (presetText = null) => {
    if (presetText) {
      if (isParsingAI) return;
      setIsParsingAI(true);
      try {
        const parsed = await parseVoiceSOS(presetText);
        applyParsedFields(parsed, presetText);
        addToast({ title: 'Voice Parsed', message: `Extracted: ${parsed.blood_type}, ${parsed.units_needed} units`, type: 'success' });
      } catch (err) {
        addToast({ title: 'Parsing Failed', message: 'Could not extract details.', type: 'alert' });
      } finally { setIsParsingAI(false); }
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
        } catch (err) {
          addToast({ title: 'Parsing Failed', message: 'Could not extract details.', type: 'alert' });
        } finally { setIsParsingAI(false); }
      };
      recognition.onerror = () => { setIsListening(false); handleVoiceSOSDictation(VOICE_DICTATION_PRESETS[0]); };
      recognition.start();
    } catch {
      setIsListening(false); handleVoiceSOSDictation(VOICE_DICTATION_PRESETS[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      if (!finalCoords) {
        addToast({ title: 'Location Required', message: 'Valid location coordinates are required. Please wait for GPS or drop a pin.', type: 'alert' });
        setIsSubmitting(false);
        return;
      }

      const [lat, lon] = finalCoords;

      const payload = {
        patient_name: patientName.trim() || "Emergency Patient",
        requester_phone: requesterPhone.trim() || "+10000000000",
        location_name: locationName || "Unknown Location",
        location_address: locationAddress || "Unknown Address",
        location_source: locationSource,
        blood_type: selectedBloodType || "O-",
        donation_type: "WHOLE_BLOOD",
        units_needed: parseInt(unitsNeeded) || 2,
        urgency_level: urgencyLevel || "CRITICAL",
        latitude: lat,
        longitude: lon,
        notes: notes.trim() || "Urgent emergency request."
      };

      const response = await submitEmergencyRequest(payload);

      // Navigate to live tracker with 0.3s timeout for cinematic transition effect
      setTimeout(() => {
        onRequestSubmitted(response);
        // Reset after nav so we can submit again if user comes back
        setTimeout(() => setIsSubmitting(false), 500);
      }, 300);

    } catch (err) {
      console.error("[Submit Error]", err);
      addToast({ title: 'Broadcast Failed', message: err.message || 'Failed to submit request.', type: 'alert' });
      setIsSubmitting(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="relative w-full max-w-2xl mx-auto min-h-[calc(100dvh-140px)] z-0 flex flex-col rounded-3xl shadow-2xl"
    >
      {/* Background container without overflow-hidden on the main element */}
      <div className="absolute inset-0 rounded-3xl border border-white/10 overflow-hidden bg-[#050505] -z-10">
        {/* Full-Screen Map Background */}
        <div className="absolute inset-0 z-0">
          <SectionErrorBoundary>
            <MapContainer center={mapCenter} zoom={14} zoomControl={false} scrollWheelZoom={true} className="w-full h-full opacity-60 bg-[#050505]">
              <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
              <LocationPicker position={finalCoords} onPositionChange={handleCustomMapPos} />
            </MapContainer>
          </SectionErrorBoundary>
          {/* Gradients to fade map into UI */}
          <div className="absolute inset-0 bg-gradient-to-b from-[#050505]/40 via-transparent to-[#050505] pointer-events-none" />
        </div>
      </div>

      {/* Bottom Sheet UI */}
      <div className="relative z-10 mt-auto w-full mx-auto p-4 pb-[env(safe-area-inset-bottom)]">
        <form onSubmit={handleSubmit} className="bg-[#0A0A0C]/90 backdrop-blur-2xl border border-white/10 rounded-3xl p-5 sm:p-8 shadow-[0_-20px_60px_rgba(0,0,0,0.6)]">

          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6 text-center sm:text-left">
            <div>
              <h1 className="text-xl sm:text-2xl font-black text-white tracking-tight uppercase">Emergency Dispatch</h1>
              <p className="text-[#86868B] text-xs sm:text-sm mt-1">Select location or use GPS</p>
            </div>
            {/* Voice SOS Button integrated into header to prevent overlap */}
            <button
              type="button"
              disabled={isListening || isParsingAI}
              onClick={() => handleVoiceSOSDictation()}
              className={`flex items-center justify-center gap-2 px-4 py-2 sm:py-3 rounded-full backdrop-blur-xl border border-white/10 shadow-lg transition-all ${
                isListening || isParsingAI
                  ? 'bg-blood-500/20 border-blood-500 text-blood-500 animate-pulse'
                  : 'bg-white/10 text-white hover:bg-white/20'
              }`}
            >
              {isParsingAI ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Mic className="w-4 h-4" />}
              <span className="text-xs font-bold tracking-widest uppercase">
                {isListening ? "Listening..." : isParsingAI ? "Parsing AI..." : "Voice SOS"}
              </span>
            </button>
          </div>

          <div className="space-y-6">
            {/* Location Search / Display */}
            <div className="bg-white/5 border border-white/10 rounded-2xl p-4 flex flex-col gap-3 relative">
              <div className="flex items-center gap-2 border-b border-white/10 pb-3">
                <Search className="w-4 h-4 text-[#86868B]" />
                <input
                  type="text"
                  placeholder="Search location by name..."
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="bg-transparent w-full focus:outline-none text-white text-sm"
                />
                {isSearching && <RefreshCw className="w-4 h-4 text-[#86868B] animate-spin" />}
              </div>

              {searchResults.length > 0 && (
                <div className="absolute top-14 left-0 right-0 bg-[#1A1A1E] border border-white/10 rounded-xl mt-1 shadow-2xl z-50 max-h-48 overflow-y-auto">
                  {searchResults.map((res, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => handleSelectSearchResult(res)}
                      className="w-full text-left px-4 py-3 hover:bg-white/5 border-b border-white/5 last:border-0"
                    >
                      <div className="text-white text-sm font-bold line-clamp-1">{res.name.split(',')[0]}</div>
                      <div className="text-[#86868B] text-xs line-clamp-1">{res.name}</div>
                    </button>
                  ))}
                </div>
              )}

              <div className="flex items-center justify-between pt-1">
                <div className="flex items-center gap-3">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                    locationSource === 'gps' ? 'bg-blue-500/20' :
                    locationSource === 'search' ? 'bg-green-500/20' : 'bg-purple-500/20'
                  }`}>
                    <MapPin className={`w-5 h-5 ${
                      locationSource === 'gps' ? 'text-blue-400' :
                      locationSource === 'search' ? 'text-green-400' : 'text-purple-400'
                    }`} />
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-[#86868B] uppercase tracking-wider mb-0.5">
                      {locationSource === 'gps' ? 'Live GPS Location' :
                       locationSource === 'search' ? 'Search Result' : 'Map Pin'}
                    </div>
                    <div className="font-bold text-white text-sm sm:text-base line-clamp-1">{locationName}</div>
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
            </div>

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
              BLOOD NEEDED AT {locationName || 'LOCATION'}
            </button>
          </div>
        </form>
      </div>
    </motion.div>
  );
}
