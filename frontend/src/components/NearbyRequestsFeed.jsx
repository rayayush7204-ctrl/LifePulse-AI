import React, { useState, useEffect, useCallback } from 'react';
import { MapPin, Clock, Droplet, Heart, RefreshCw, Navigation, AlertTriangle } from 'lucide-react';
import { fetchNearbyRequests } from '../services/api';
import { haversineDistance, formatDistance, estimateETA } from '../services/geolocation';

export default function NearbyRequestsFeed({ userLat, userLon, onHelpRequest }) {
  const [requests, setRequests] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(null);

  const loadNearby = useCallback(async () => {
    if (!userLat || !userLon) return;
    setIsLoading(true);
    try {
      const data = await fetchNearbyRequests(userLat, userLon, 50);
      // Add calculated distance from user
      const withDistance = (data || []).map((r) => ({
        ...r,
        _userDist: haversineDistance(userLat, userLon, r.latitude || 0, r.longitude || 0),
      }));
      withDistance.sort((a, b) => a._userDist - b._userDist);
      setRequests(withDistance);
      setLastRefresh(new Date());
    } catch (err) {
      console.warn('[NearbyFeed] Error loading nearby requests:', err);
    } finally {
      setIsLoading(false);
    }
  }, [userLat, userLon]);

  useEffect(() => {
    loadNearby();
    const interval = setInterval(loadNearby, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [loadNearby]);

  const timeSince = (dateStr) => {
    if (!dateStr) return '';
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    return `${hrs}h ${mins % 60}m ago`;
  };

  // Compatible blood types that this donor can donate to
  const COMPATIBLE = {
    'O-': ['O-', 'O+', 'A-', 'A+', 'B-', 'B+', 'AB-', 'AB+'],
    'O+': ['O+', 'A+', 'B+', 'AB+'],
    'A-': ['A-', 'A+', 'AB-', 'AB+'],
    'A+': ['A+', 'AB+'],
    'B-': ['B-', 'B+', 'AB-', 'AB+'],
    'B+': ['B+', 'AB+'],
    'AB-': ['AB-', 'AB+'],
    'AB+': ['AB+'],
  };

  if (!userLat || !userLon) {
    return (
      <div className="glass-panel p-5 rounded-2xl text-center space-y-2">
        <MapPin className="w-8 h-8 text-slate-600 mx-auto" />
        <p className="text-xs text-slate-400">
          Enable location to see nearby emergency requests.
        </p>
      </div>
    );
  }

  return (
    <div className="glass-panel p-5 rounded-2xl space-y-4 border border-red-500/20">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="relative">
            <AlertTriangle className="w-5 h-5 text-red-400" />
            {requests.length > 0 && (
              <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-red-500 rounded-full animate-ping" />
            )}
          </div>
          <h3 className="font-bold text-white text-sm">Nearby Emergency Requests</h3>
        </div>
        <button
          onClick={loadNearby}
          disabled={isLoading}
          className="px-2.5 py-1 text-[10px] font-bold rounded-lg bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 transition flex items-center gap-1"
        >
          <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
          {lastRefresh ? timeSince(lastRefresh.toISOString()) : 'Refresh'}
        </button>
      </div>

      {isLoading && requests.length === 0 ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-20 rounded-xl" />
          ))}
        </div>
      ) : requests.length === 0 ? (
        <div className="p-6 text-center space-y-2">
          <Heart className="w-8 h-8 text-emerald-500 mx-auto" />
          <p className="text-sm font-bold text-slate-300">No active emergencies nearby</p>
          <p className="text-xs text-slate-500">
            You'll be notified when blood is needed in your area.
          </p>
        </div>
      ) : (
        <div className="space-y-2.5 max-h-[400px] overflow-y-auto pr-1">
          {requests.map((req, idx) => {
            const dist = req._userDist;
            const eta = estimateETA(dist);
            const urgencyColor =
              req.urgency_level === 'CRITICAL'
                ? 'bg-red-950 text-red-400 border-red-800'
                : 'bg-amber-950 text-amber-400 border-amber-800';

            return (
              <div
                key={req.id || idx}
                className="p-3.5 rounded-xl bg-slate-900/90 border border-slate-800 hover:border-red-500/40 transition-all stagger-item space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="px-2 py-0.5 text-xs font-black rounded bg-blood-950 text-blood-400 border border-blood-800">
                        {req.blood_type}
                      </span>
                      <span className="text-sm font-bold text-white">
                        {req.units_needed} Units Needed
                      </span>
                      <span
                        className={`px-2 py-0.5 text-[10px] font-extrabold rounded-full border ${urgencyColor}`}
                      >
                        {req.urgency_level}
                      </span>
                    </div>
                    <div className="text-xs text-slate-400 flex items-center gap-2 flex-wrap">
                      <span className="flex items-center gap-1">
                        <MapPin className="w-3 h-3 text-slate-500" />
                        {req.hospital_name}
                      </span>
                      <span className="flex items-center gap-1">
                        <Navigation className="w-3 h-3 text-emerald-500" />
                        {formatDistance(dist)} away
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3 text-slate-500" />
                        {timeSince(req.created_at)}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => onHelpRequest?.(req)}
                    className="flex-1 py-2 bg-gradient-to-r from-red-600 to-blood-600 hover:from-red-500 hover:to-blood-500 text-white font-extrabold text-xs rounded-xl shadow-md flex items-center justify-center gap-1.5 transition"
                  >
                    <Heart className="w-3.5 h-3.5" />
                    I Can Help — {eta} away
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
