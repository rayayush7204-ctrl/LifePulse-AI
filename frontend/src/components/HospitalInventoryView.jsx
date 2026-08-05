import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Building2, Phone, MapPin, AlertTriangle, Navigation, Droplet, ExternalLink, RefreshCw, Layers } from 'lucide-react';
import { fetchBloodBanks } from '../services/api';
import { useGPS } from '../App';
import { haversineDistance, formatDistance, openDirections } from '../services/geolocation';
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';

const hospitalIcon = L.divIcon({
  className: 'custom-leaflet-marker',
  html: `<div style="background: #e50914; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #050505; box-shadow: 0 0 16px rgba(229,9,20,0.6);"></div>`,
  iconSize: [14, 14], iconAnchor: [7, 7]
});

const userIcon = L.divIcon({
  className: 'custom-leaflet-marker',
  html: `<div style="background: #3b82f6; width: 12px; height: 12px; border-radius: 50%; border: 2px solid #050505; box-shadow: 0 0 16px rgba(59,130,246,0.6);"></div>`,
  iconSize: [12, 12], iconAnchor: [6, 6]
});

const BLOOD_TYPES_ORDER = ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"];

// Ultra-thin minimal data visualization bar
function MinimalStockBar({ type, count, maxCount = 20, delay = 0 }) {
  const pct = Math.min(100, (count / maxCount) * 100);
  const isCritical = pct < 15;
  const isLow = pct < 35 && !isCritical;
  
  const colorClass = isCritical ? 'bg-blood-500 shadow-[0_0_10px_rgba(229,9,20,0.8)]' 
                   : isLow ? 'bg-amber-500 shadow-[0_0_10px_rgba(245,158,11,0.5)]' 
                   : 'bg-[#86868B]';

  return (
    <div className="flex items-center gap-4 group">
      <div className="w-8 flex items-center justify-between shrink-0">
        <span className={`text-[10px] font-black ${isCritical ? 'text-blood-400' : 'text-[#86868B]'}`}>{type}</span>
      </div>
      
      <div className="flex-1 h-1 bg-white/5 rounded-full overflow-hidden relative">
        <motion.div 
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 1, delay, ease: "easeOut" }}
          className={`absolute top-0 bottom-0 left-0 rounded-full ${colorClass}`} 
        />
      </div>
      
      <div className="w-8 flex justify-end shrink-0">
        <span className={`text-[10px] font-mono ${isCritical ? 'text-blood-400 font-bold' : 'text-white'}`}>
          {count.toString().padStart(2, '0')}
        </span>
      </div>
    </div>
  );
}

export default function HospitalInventoryView() {
  const gps = useGPS();
  const [banks, setBanks] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadBanks();
  }, [gps?.location]);

  const loadBanks = async () => {
    setIsLoading(true);
    try {
      const data = await fetchBloodBanks();
      const loc = gps?.location;
      const withDist = data.map(b => ({
        ...b,
        _userDist: loc ? haversineDistance(loc.latitude, loc.longitude, b.latitude, b.longitude) : b.distance_km
      }));
      withDist.sort((a, b) => a._userDist - b._userDist);
      setBanks(withDist);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const mapCenter = gps?.location
    ? [gps.location.latitude, gps.location.longitude]
    : banks[0]
    ? [banks[0].latitude, banks[0].longitude]
    : [37.7749, -122.4194];

  const getTotalStock = (bank) => {
    if (!bank.inventory) return 0;
    return Object.values(bank.inventory).reduce((sum, v) => sum + v, 0);
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6 max-w-6xl mx-auto"
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 pb-6 border-b border-white/5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center border border-white/10">
            <Layers className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-tight">Network Inventory</h1>
            <p className="text-xs text-[#86868B] uppercase tracking-widest mt-1">Live Global Reserves • Sorted by Proximity</p>
          </div>
        </div>
        <button onClick={loadBanks} disabled={isLoading}
          className="px-4 py-2 rounded-full bg-[#111111] text-white text-xs font-bold border border-white/10 hover:bg-white/10 transition flex items-center gap-2">
          <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} /> {isLoading ? 'SYNCING...' : 'SYNC DATA'}
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-8">
        
        {/* Map View */}
        <div className="xl:col-span-5 space-y-4 flex flex-col h-[600px]">
          <h4 className="text-[10px] font-bold text-[#86868B] uppercase tracking-widest flex items-center gap-2 shrink-0">
            <MapPin className="w-3.5 h-3.5 text-blood-500" /> Geographic Distribution
          </h4>
          <div className="flex-1 rounded-3xl overflow-hidden border border-white/5 relative bg-[#050505]">
            <MapContainer center={mapCenter} zoom={11} scrollWheelZoom={true} className="w-full h-full">
              <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}{r}.png" />
              {gps?.location && (
                <Marker position={[gps.location.latitude, gps.location.longitude]} icon={userIcon}>
                  <Popup className="cinematic-popup"><strong>Your Location</strong></Popup>
                </Marker>
              )}
              {banks.map((bank, i) => (
                <Marker key={i} position={[bank.latitude, bank.longitude]} icon={hospitalIcon}>
                  <Popup className="cinematic-popup">
                    <div className="font-bold text-white text-sm">{bank.name}</div>
                    <div className="text-[10px] text-[#86868B] mt-1">Total Reserves: {getTotalStock(bank)} Units</div>
                  </Popup>
                </Marker>
              ))}
            </MapContainer>
            <div className="absolute inset-0 shadow-[inset_0_0_40px_rgba(5,5,5,0.8)] pointer-events-none z-[400]" />
          </div>
        </div>

        {/* Blood Banks List */}
        <div className="xl:col-span-7 space-y-6 flex flex-col h-[600px]">
          <h4 className="text-[10px] font-bold text-[#86868B] uppercase tracking-widest flex items-center gap-2 shrink-0">
            <Building2 className="w-3.5 h-3.5 text-white" /> Node Facilities
          </h4>
          
          <div className="flex-1 overflow-y-auto pr-2 space-y-4 scrollbar-hide">
            {isLoading ? (
              [1, 2, 3].map(i => <div key={i} className="h-40 rounded-3xl bg-[#111111] animate-pulse border border-white/5" />)
            ) : banks.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full text-[#86868B]">
                <Layers className="w-12 h-12 mb-4 opacity-20" />
                <p className="text-sm font-bold uppercase tracking-widest">No Active Nodes Found</p>
              </div>
            ) : (
              banks.map((bank, idx) => (
                <motion.div 
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: idx * 0.1 }}
                  key={idx} 
                  className="p-6 rounded-3xl bg-[#0A0A0C] border border-white/5 hover:border-white/10 transition-colors flex flex-col sm:flex-row gap-6"
                >
                  {/* Bank Info */}
                  <div className="sm:w-1/3 flex flex-col justify-between">
                    <div>
                      <h3 className="font-bold text-white text-sm leading-tight mb-2">{bank.name}</h3>
                      <div className="text-[10px] text-[#86868B] space-y-1 font-mono">
                        <div className="truncate">{bank.address}</div>
                        <div className="text-emerald-500">{(bank._userDist).toFixed(2)} km away</div>
                      </div>
                    </div>
                    <div className="flex gap-2 mt-4 sm:mt-0">
                      <button onClick={() => openDirections(bank.latitude, bank.longitude, bank.name)}
                        className="px-3 py-1.5 bg-[#111111] text-white border border-white/10 hover:bg-white/10 rounded-full text-[10px] font-bold tracking-widest transition flex-1 flex justify-center items-center gap-1">
                        <Navigation className="w-3 h-3" /> MAP
                      </button>
                    </div>
                  </div>

                  {/* Stock Visualization */}
                  <div className="sm:w-2/3 pl-0 sm:pl-6 sm:border-l border-white/5">
                    <div className="flex items-center justify-between mb-4">
                      <span className="text-[10px] font-bold text-[#86868B] uppercase tracking-widest">Reserves</span>
                      <span className="text-xs font-black text-white bg-white/10 px-2 py-0.5 rounded-md">
                        {getTotalStock(bank)} Units
                      </span>
                    </div>

                    <div className="grid grid-cols-2 gap-x-8 gap-y-3">
                      {BLOOD_TYPES_ORDER.map((bt, i) => (
                        <MinimalStockBar 
                          key={bt} 
                          type={bt} 
                          count={bank.inventory?.[bt] || 0} 
                          delay={(idx * 0.1) + (i * 0.05)}
                        />
                      ))}
                    </div>

                    {/* Low stock warnings */}
                    {bank.inventory && Object.entries(bank.inventory).some(([, v]) => v < 3) && (
                      <div className="mt-4 pt-4 border-t border-white/5 flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-blood-500 shrink-0 animate-pulse" />
                        <div className="text-[10px] text-[#86868B]">
                          <strong className="text-blood-400">CRITICAL SHORTAGE:</strong>{' '}
                          {Object.entries(bank.inventory)
                            .filter(([, v]) => v < 3)
                            .map(([bt, v]) => `${bt} (${v})`)
                            .join(', ')}
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              ))
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
