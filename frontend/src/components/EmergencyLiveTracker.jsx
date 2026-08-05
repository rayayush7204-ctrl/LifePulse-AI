import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle, useMap } from 'react-leaflet';
import L from 'leaflet';
import { wsClient } from '../services/WebSocketClient';
import LiveTimeline from './LiveTimeline';
import SearchProgressStream from './SearchProgressStream';
import { Activity, User, Phone, CheckCircle2, MapPin, Wifi, WifiOff, Radio } from 'lucide-react';

// ── Custom Markers ──────────────────────────────────────────────
const createCustomMarker = (color, isAnimated = false, size = 14) => {
  return L.divIcon({
    className: 'custom-leaflet-marker',
    html: `<div style="background-color: ${color}; width: ${size}px; height: ${size}px; border-radius: 50%; border: 2px solid #050505; box-shadow: 0 0 16px ${color}; ${isAnimated ? 'animation: pulse 1s infinite alternate;' : ''}"></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2]
  });
};

// Nearby donor dot (small, pulsing blue)
const createNearbyDonorMarker = (isEligible = false) => {
  const color = isEligible ? '#3b82f6' : '#64748b';
  return L.divIcon({
    className: 'custom-leaflet-marker',
    html: `<div class="animate-donor-appear" style="
      background-color: ${color}; 
      width: 8px; height: 8px; 
      border-radius: 50%; 
      box-shadow: 0 0 12px ${color}80;
      opacity: 0.7;
    "></div>`,
    iconSize: [8, 8],
    iconAnchor: [4, 4]
  });
};

// Accepted donor (larger green, glowing)
const createAcceptedDonorMarker = () => {
  return L.divIcon({
    className: 'custom-leaflet-marker',
    html: `<div class="animate-accepted-glow" style="
      background-color: #10b981; 
      width: 18px; height: 18px; 
      border-radius: 50%; 
      border: 3px solid #050505;
      box-shadow: 0 0 24px rgba(16, 185, 129, 0.8);
    "></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  });
};

const hospitalIcon = createCustomMarker('#e50914', false, 16);
const donorTrackingIcon = createCustomMarker('#10b981', true, 14);

// ── Map Auto-Center Component ───────────────────────────────────
function MapAutoCenter({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.flyTo(center, zoom || map.getZoom(), { duration: 1.5 });
    }
  }, [center, zoom]);
  return null;
}

// ── Animated Search Circles ─────────────────────────────────────
function SearchCircles({ center, isSearching }) {
  const [circles, setCircles] = useState([]);
  
  useEffect(() => {
    if (!isSearching) {
      setCircles([]);
      return;
    }
    
    // Spawn a new expanding circle every 2 seconds
    const interval = setInterval(() => {
      const id = Date.now();
      setCircles(prev => [...prev.slice(-3), { id, radius: 200 }]);
    }, 2000);
    
    // Expand existing circles
    const expandInterval = setInterval(() => {
      setCircles(prev => prev
        .map(c => ({ ...c, radius: c.radius + 150 }))
        .filter(c => c.radius < 8000)
      );
    }, 100);
    
    return () => {
      clearInterval(interval);
      clearInterval(expandInterval);
    };
  }, [isSearching]);

  return (
    <>
      {circles.map(c => (
        <Circle
          key={c.id}
          center={center}
          radius={c.radius}
          pathOptions={{
            color: '#3b82f6',
            fillColor: '#3b82f6',
            fillOpacity: Math.max(0.01, 0.15 - (c.radius / 8000) * 0.15),
            weight: Math.max(0.5, 1.5 - (c.radius / 8000) * 1.5),
            opacity: Math.max(0.1, 0.6 - (c.radius / 8000) * 0.6),
          }}
        />
      ))}
    </>
  );
}

// ── Main Component ──────────────────────────────────────────────
export default function EmergencyLiveTracker({ requestData, onSimulateDonor }) {
  const [requestState, setRequestState] = useState(requestData?.request?.status || 'CREATED');
  const [hudData, setHudData] = useState({ step: 'initialization' });
  const [events, setEvents] = useState([]);
  const [donorLocation, setDonorLocation] = useState(null);
  const [eta, setEta] = useState(null);
  const [distance, setDistance] = useState(null);
  const [acceptedDonor, setAcceptedDonor] = useState(null);
  
  // New dispatch state
  const [nearbyDonorMarkers, setNearbyDonorMarkers] = useState([]);
  const [searchProgress, setSearchProgress] = useState(null);
  const [ringCountdown, setRingCountdown] = useState(null);
  const [connectionState, setConnectionState] = useState('disconnected');
  const [mapCenter, setMapCenter] = useState(null);

  const reqId = requestData?.request?.id;
  const hospitalLoc = [requestData?.request?.latitude || 37.7631, requestData?.request?.longitude || -122.4578];

  const isSearching = ['CREATED', 'AI_PROCESSING', 'VALIDATING', 'SEARCHING', 'MATCHING', 'RING1', 'RING2', 'WAITING'].includes(requestState);
  const isTracking = ['TRACKING', 'ARRIVING', 'ARRIVED'].includes(requestState);
  const isDonorAccepted = ['DONOR_ACCEPTED', 'TRACKING', 'ARRIVING', 'ARRIVED', 'DONATION_STARTED', 'DONATION_COMPLETED'].includes(requestState);

  useEffect(() => {
    if (!reqId) return;

    wsClient.connect(reqId);

    const handleStateTransition = (data) => {
      setRequestState(data.state);
      setHudData(data.metadata || {});
      setEvents(prev => [{
        id: Date.now().toString(),
        state: data.state,
        message: data.message,
        timestamp: new Date().toLocaleTimeString()
      }, ...prev]);
    };

    const handleGpsUpdate = (data) => {
      setDonorLocation([data.lat, data.lng]);
      setEta(data.eta_minutes);
      setDistance(data.distance_km);
    };

    const handleDonorStatus = (data) => {
      if (data?.match?.status === "ACCEPTED") {
        setAcceptedDonor(data.match);
      }
    };

    // New dispatch event handlers
    const handleSearchProgress = (data) => {
      setSearchProgress(data.data || data);
    };

    const handleDonorMarkers = (data) => {
      const markersData = data.data || data;
      setNearbyDonorMarkers(markersData.markers || []);
    };

    const handleRingCountdown = (data) => {
      setRingCountdown(data.data || data);
    };

    const handleConnectionState = (data) => {
      setConnectionState(data.state);
    };

    const handleDonorLocationUpdated = (data) => {
      const loc = data.data || data;
      if (loc.latitude && loc.longitude) {
        setDonorLocation([loc.latitude, loc.longitude]);
        setEta(loc.eta_minutes);
        setDistance(loc.distance_km);
        if (loc.donor_name || loc.donor_blood_type) {
          setAcceptedDonor(prev => ({
            ...prev,
            donor_name: loc.donor_name || prev?.donor_name,
            donor_blood_type: loc.donor_blood_type || prev?.donor_blood_type
          }));
        }
      }
    };

    wsClient.on('STATE_TRANSITION', handleStateTransition);
    wsClient.on('GPS_UPDATE', handleGpsUpdate);
    wsClient.on('DONOR_STATUS_CHANGED', handleDonorStatus);
    wsClient.on('SEARCH_PROGRESS', handleSearchProgress);
    wsClient.on('DONOR_MARKERS', handleDonorMarkers);
    wsClient.on('RING_COUNTDOWN', handleRingCountdown);
    wsClient.on('CONNECTION_STATE', handleConnectionState);
    wsClient.on('DONOR_LOCATION_UPDATED', handleDonorLocationUpdated);

    return () => {
      wsClient.off('STATE_TRANSITION', handleStateTransition);
      wsClient.off('GPS_UPDATE', handleGpsUpdate);
      wsClient.off('DONOR_STATUS_CHANGED', handleDonorStatus);
      wsClient.off('SEARCH_PROGRESS', handleSearchProgress);
      wsClient.off('DONOR_MARKERS', handleDonorMarkers);
      wsClient.off('RING_COUNTDOWN', handleRingCountdown);
      wsClient.off('CONNECTION_STATE', handleConnectionState);
      wsClient.off('DONOR_LOCATION_UPDATED', handleDonorLocationUpdated);
      wsClient.disconnect();
    };
  }, [reqId]);

  // Auto-center map when donor accepted or tracking
  useEffect(() => {
    if (donorLocation && isDonorAccepted) {
      // Center between donor and hospital
      const midLat = (donorLocation[0] + hospitalLoc[0]) / 2;
      const midLng = (donorLocation[1] + hospitalLoc[1]) / 2;
      setMapCenter([midLat, midLng]);
    }
  }, [donorLocation, isDonorAccepted]);

  // Filter markers: if donor accepted, fade out other markers
  const displayMarkers = useMemo(() => {
    if (isDonorAccepted) return []; // Hide nearby dots when donor accepted
    return nearbyDonorMarkers;
  }, [nearbyDonorMarkers, isDonorAccepted]);

  return (
    <div className="fixed inset-0 top-[64px] z-0 overflow-hidden bg-[#050505] animate-cinematic-in">
      {/* Connection State Indicator */}
      <AnimatePresence>
        {connectionState === 'reconnecting' && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            className="absolute top-2 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 bg-amber-900/80 px-3 py-1.5 rounded-full backdrop-blur-md"
          >
            <WifiOff className="w-3 h-3 text-amber-400 animate-pulse" />
            <span className="text-xs font-bold text-amber-300">Reconnecting...</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* MAP Layer */}
      <MapContainer center={hospitalLoc} zoom={13} zoomControl={false} scrollWheelZoom={true} className="absolute inset-0 w-full h-full z-0">
        <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />
        
        {/* Auto-center when tracking */}
        {mapCenter && <MapAutoCenter center={mapCenter} zoom={12} />}
        
        {/* Hospital Marker */}
        <Marker position={hospitalLoc} icon={hospitalIcon}>
          <Popup className="cinematic-popup"><strong>{requestData?.request?.hospital_name}</strong></Popup>
        </Marker>

        {/* Animated Search Circles (CSS-driven, smooth) */}
        <SearchCircles center={hospitalLoc} isSearching={isSearching} />

        {/* Nearby Donor Markers (pulsing dots during search) */}
        {displayMarkers.map((marker, idx) => (
          <Marker
            key={`donor-${idx}`}
            position={[marker.lat, marker.lng]}
            icon={createNearbyDonorMarker(marker.status === 'eligible')}
          >
            <Popup className="cinematic-popup">
              <span style={{ fontSize: '11px' }}>
                {marker.blood_type} • {marker.distance_km ? `${marker.distance_km} km` : 'Nearby'}
              </span>
            </Popup>
          </Marker>
        ))}

        {/* Accepted Donor — highlighted green, zoomed */}
        {donorLocation && isDonorAccepted && (
          <>
            <Polyline
              positions={[donorLocation, hospitalLoc]}
              pathOptions={{
                color: '#10b981',
                weight: 3,
                opacity: 0.7,
                dashArray: '8, 8',
              }}
            />
            <Marker position={donorLocation} icon={isTracking ? donorTrackingIcon : createAcceptedDonorMarker()}>
              <Popup className="cinematic-popup">
                <strong>{acceptedDonor?.donor_name || 'Donor'}</strong>
                <br />
                <span style={{ fontSize: '11px' }}>ETA: {eta || '-'} min • {distance || '-'} km</span>
              </Popup>
            </Marker>
          </>
        )}
      </MapContainer>

      {/* Map overlay gradients */}
      <div className="absolute top-0 left-0 right-0 h-24 map-overlay-gradient-top z-[5] pointer-events-none" />

      {/* OVERLAYS */}
      <div className="absolute inset-0 pointer-events-none z-10 flex p-4 pb-20 lg:p-6 gap-6">
        {/* Left Side: Timeline */}
        <div className="w-[350px] hidden lg:block pointer-events-auto h-full overflow-y-auto no-scrollbar">
          <LiveTimeline events={events} currentState={requestState} />
        </div>

        {/* Right Side: Search Progress Stream + Status */}
        <div className="flex-1 flex flex-col justify-between items-end h-full">
          {/* Top-right: Search Progress Stream */}
          <div className="w-full max-w-sm pointer-events-auto">
            <SearchProgressStream
              searchProgress={searchProgress}
              ringCountdown={ringCountdown}
              currentState={requestState}
            />
          </div>

          {/* Bottom Tracking Sheet */}
          <AnimatePresence>
            {(isTracking || requestState === 'ARRIVED') && (
              <motion.div 
                initial={{ y: 100, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                exit={{ y: 100, opacity: 0 }}
                transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
                className="w-full max-w-md pointer-events-auto bg-[#0A0A0C]/95 backdrop-blur-xl border border-emerald-500/30 rounded-[32px] p-6 shadow-[0_0_40px_rgba(16,185,129,0.15)] relative overflow-hidden"
              >
                {/* Animated progress bar at top */}
                <div className="absolute top-0 left-0 right-0 h-1 bg-emerald-500/20 overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-emerald-500 to-emerald-400"
                    initial={{ width: "0%" }}
                    animate={{ width: requestState === 'ARRIVED' ? "100%" : "60%" }}
                    transition={{ duration: requestState === 'ARRIVED' ? 0.5 : 30 }}
                  />
                </div>

                <h2 className="text-emerald-400 font-black tracking-widest uppercase text-[10px] mb-4 flex items-center gap-2">
                  <CheckCircle2 className="w-3 h-3" />
                  {requestState === 'ARRIVED' ? 'Donor Arrived' : 'Live Tracking'}
                </h2>
                
                <div className="flex flex-col gap-4">
                  <div className="flex items-center gap-4">
                    <div className={`w-14 h-14 rounded-full border-2 flex items-center justify-center shrink-0 ${
                      requestState === 'ARRIVED'
                        ? 'bg-emerald-500/30 border-emerald-400 animate-accepted-glow'
                        : 'bg-emerald-500/20 border-emerald-500/50'
                    }`}>
                      <User className="w-6 h-6 text-emerald-400" />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between">
                        <h3 className="text-xl font-black text-white">{acceptedDonor?.donor_name || 'Donor'}</h3>
                        <span className="text-2xl font-black text-emerald-500">
                          {eta || '-'}
                          <span className="text-[10px] text-[#86868B] uppercase block -mt-1 text-right">Min</span>
                        </span>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <span className="px-2 py-0.5 bg-blood-500/20 text-blood-500 text-[10px] font-bold rounded">
                          {acceptedDonor?.donor_blood_type || 'O-'}
                        </span>
                        <span className="text-sm text-[#86868B] flex items-center gap-1">
                          <MapPin className="w-3 h-3" /> {distance || '-'} km away
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Donor Simulator Button + Connection indicator */}
          <div className="pointer-events-auto mt-4 self-end flex items-center gap-3">
            <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-[#111111]/80 border border-white/5">
              {connectionState === 'connected' ? (
                <><Wifi className="w-3 h-3 text-emerald-500" /><span className="text-[9px] text-emerald-400 font-bold">LIVE</span></>
              ) : (
                <><WifiOff className="w-3 h-3 text-amber-500" /><span className="text-[9px] text-amber-400 font-bold">{connectionState.toUpperCase()}</span></>
              )}
            </div>
            <button
              onClick={() => onSimulateDonor(requestData?.matching_summary?.request_id)}
              className="px-4 py-2 bg-slate-800/80 backdrop-blur-md text-xs text-white rounded-full hover:bg-slate-700 border border-slate-600/50 transition-colors"
            >
              Open Donor Simulator
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
