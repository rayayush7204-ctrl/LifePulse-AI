/**
 * TrackingMap — Leaflet map with:
 *  - Animated donor marker (smooth interpolated position)
 *  - Route polyline: faded full-route background + live growing progress line
 *  - Hospital marker
 *  - Nearby donor dots during search phase
 *  - Animated search radar circles
 *  - Auto-follow camera with manual override
 *
 * Wrapped in React.memo — only re-renders when props change.
 */
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import useSmoothPosition from '../../hooks/useSmoothPosition';
import { Navigation } from 'lucide-react';

// ── Custom Marker Factories ────────────────────────────────────────────────
const createCustomMarker = (color, isAnimated = false, size = 14) =>
  L.divIcon({
    className: 'custom-leaflet-marker',
    html: `<div style="
      background-color:${color};width:${size}px;height:${size}px;
      border-radius:50%;border:2px solid #050505;
      box-shadow:0 0 16px ${color};
      ${isAnimated ? 'animation:acceptedGlow 2s ease-in-out infinite;' : ''}
    "></div>`,
    iconSize:   [size, size],
    iconAnchor: [size / 2, size / 2],
  });

const createNearbyDonorMarker = (isEligible = false) => {
  const color = isEligible ? '#3b82f6' : '#64748b';
  return L.divIcon({
    className: 'custom-leaflet-marker',
    html: `<div class="animate-donor-appear" style="
      background-color:${color};width:8px;height:8px;
      border-radius:50%;box-shadow:0 0 12px ${color}80;opacity:0.7;
    "></div>`,
    iconSize:   [8, 8],
    iconAnchor: [4, 4],
  });
};

const createDonorTrackingMarker = () =>
  L.divIcon({
    className: 'custom-leaflet-marker',
    html: `<div style="
      width:22px;height:22px;border-radius:50%;
      background:radial-gradient(circle, #10b981, #059669);
      border:3px solid #050505;
      box-shadow:0 0 0 6px rgba(16,185,129,0.25), 0 0 24px rgba(16,185,129,0.7);
      animation:acceptedGlow 1.5s ease-in-out infinite;
    "></div>`,
    iconSize:   [22, 22],
    iconAnchor: [11, 11],
  });

const hospitalIcon = createCustomMarker('#e50914', false, 16);
const donorTrackingMarker = createDonorTrackingMarker();

// ── Auto-Follow Camera ────────────────────────────────────────────────────
function AutoFollowCamera({ target, isFollowing, zoom = 14 }) {
  const map = useMap();
  const prevTarget = useRef(null);

  useEffect(() => {
    if (!target || !isFollowing) return;
    if (!prevTarget.current) {
      map.setView(target, zoom, { animate: false });
    } else {
      map.panTo(target, { animate: true, duration: 1.0, easeLinearity: 0.5 });
    }
    prevTarget.current = target;
  }, [target, isFollowing, zoom, map]);

  return null;
}

// ── Manual Pan Detector ───────────────────────────────────────────────────
function ManualPanDetector({ onManualPan }) {
  useMapEvents({ dragstart: onManualPan, zoomstart: onManualPan });
  return null;
}

// ── Animated Search Circles ───────────────────────────────────────────────
function SearchCircles({ center, isSearching }) {
  const [circles, setCircles] = useState([]);

  useEffect(() => {
    if (!isSearching) { setCircles([]); return; }
    const spawnInterval  = setInterval(() => {
      setCircles(prev => [...prev.slice(-3), { id: Date.now(), radius: 200 }]);
    }, 2000);
    const expandInterval = setInterval(() => {
      setCircles(prev =>
        prev.map(c => ({ ...c, radius: c.radius + 150 })).filter(c => c.radius < 8000)
      );
    }, 100);
    return () => { clearInterval(spawnInterval); clearInterval(expandInterval); };
  }, [isSearching]);

  return (
    <>
      {circles.map(c => (
        <Circle
          key={c.id}
          center={center}
          radius={c.radius}
          pathOptions={{
            color:       '#3b82f6',
            fillColor:   '#3b82f6',
            fillOpacity: Math.max(0.01, 0.15 - (c.radius / 8000) * 0.15),
            weight:      Math.max(0.5, 1.5  - (c.radius / 8000) * 1.5),
            opacity:     Math.max(0.1, 0.6  - (c.radius / 8000) * 0.6),
          }}
        />
      ))}
    </>
  );
}

// ── Re-center Button (portal inside map) ─────────────────────────────────
function RecenterButton({ visible, onClick }) {
  if (!visible) return null;
  return (
    <div
      className="absolute bottom-4 right-4 z-[1000] pointer-events-auto"
      style={{ position: 'absolute' }}
    >
      <button
        onClick={onClick}
        className="flex items-center gap-2 px-3 py-2 bg-[#0A0A0C]/90 backdrop-blur-md
                   border border-emerald-500/40 rounded-full text-xs text-emerald-400
                   font-bold shadow-lg hover:bg-emerald-900/30 transition-colors"
      >
        <Navigation className="w-3 h-3" />
        Re-center
      </button>
    </div>
  );
}

// ── Main Map Component ────────────────────────────────────────────────────
const TrackingMap = React.memo(function TrackingMap({
  hospitalLoc,
  donorLocation,
  initialDonorPos,
  routeHistory,
  nearbyMarkers,
  isSearching,
  isTracking,
  isDonorAccepted,
  requestState,
  acceptedDonor,
  etaSeconds,
  distance,
  hospitalName,
}) {
  const smoothPos = useSmoothPosition(donorLocation, 1000);

  const [isFollowing,    setIsFollowing]    = useState(true);
  const [showRecenter,   setShowRecenter]   = useState(false);

  const handleManualPan = useCallback(() => {
    setIsFollowing(false);
    setShowRecenter(true);
  }, []);

  const handleRecenter = useCallback(() => {
    setIsFollowing(true);
    setShowRecenter(false);
  }, []);

  // Stop following when not actively tracking
  useEffect(() => {
    if (!isTracking) { setIsFollowing(false); setShowRecenter(false); }
    else              { setIsFollowing(true); }
  }, [isTracking]);

  // Camera target: mid-point between donor and hospital during search, donor during tracking
  const cameraTarget = useMemo(() => {
    if (isTracking && smoothPos) return smoothPos;
    if (isDonorAccepted && smoothPos) {
      return [(smoothPos[0] + hospitalLoc[0]) / 2, (smoothPos[1] + hospitalLoc[1]) / 2];
    }
    return null;
  }, [isTracking, isDonorAccepted, smoothPos, hospitalLoc]);

  const displayEta = etaSeconds !== null
    ? `${Math.floor(etaSeconds / 60)}:${String(etaSeconds % 60).padStart(2, '0')}`
    : null;

  return (
    <div className="relative w-full h-full">
      <MapContainer
        center={hospitalLoc}
        zoom={13}
        zoomControl={false}
        scrollWheelZoom={true}
        className="absolute inset-0 w-full h-full z-0"
      >
        <TileLayer url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png" />

        {/* Auto-follow camera */}
        {cameraTarget && (
          <AutoFollowCamera
            target={cameraTarget}
            isFollowing={isFollowing}
            zoom={isTracking ? 15 : 13}
          />
        )}

        {/* Manual pan detector */}
        <ManualPanDetector onManualPan={handleManualPan} />

        {/* Hospital marker */}
        <Marker position={hospitalLoc} icon={hospitalIcon}>
          <Popup className="cinematic-popup"><strong>{hospitalName || 'Hospital'}</strong></Popup>
        </Marker>

        {/* Search radar circles */}
        <SearchCircles center={hospitalLoc} isSearching={isSearching} />

        {/* Nearby donor dots (search phase only) */}
        {!isDonorAccepted && nearbyMarkers.map((m, i) => (
          <Marker
            key={`nearby-${i}`}
            position={[m.lat, m.lng]}
            icon={createNearbyDonorMarker(m.status === 'eligible')}
          >
            <Popup className="cinematic-popup">
              <span style={{ fontSize: '11px' }}>
                {m.blood_type} · {m.distance_km ? `${m.distance_km} km` : 'Nearby'}
              </span>
            </Popup>
          </Marker>
        ))}

        {/* Route lines (tracking phase) */}
        {isDonorAccepted && smoothPos && (
          <>
            {/* Faded full-route background */}
            {initialDonorPos && (
              <Polyline
                positions={[initialDonorPos, hospitalLoc]}
                pathOptions={{ color: '#10b981', weight: 2, opacity: 0.12, dashArray: '4 6' }}
              />
            )}
            {/* Growing progress line (route history trail) */}
            {routeHistory.length > 1 && (
              <Polyline
                positions={[...routeHistory, hospitalLoc]}
                pathOptions={{ color: '#10b981', weight: 3, opacity: 0.85 }}
              />
            )}
            {/* Donor marker (smoothly interpolated) */}
            <Marker position={smoothPos} icon={donorTrackingMarker}>
              <Popup className="cinematic-popup">
                <strong>{acceptedDonor?.donor_name || 'Donor'}</strong><br />
                <span style={{ fontSize: '11px' }}>
                  {displayEta ? `ETA ${displayEta}` : ''} · {distance ? `${distance} km` : ''}
                </span>
              </Popup>
            </Marker>
          </>
        )}
      </MapContainer>

      {/* Re-center button overlay */}
      <RecenterButton visible={showRecenter && isTracking} onClick={handleRecenter} />
    </div>
  );
});

export default TrackingMap;
