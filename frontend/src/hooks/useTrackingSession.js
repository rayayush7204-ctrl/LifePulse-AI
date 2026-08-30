/**
 * useTrackingSession — Central hook for all WebSocket-driven emergency state.
 *
 * Responsibilities:
 *  - Connect/disconnect WebSocket for a given requestId
 *  - Handle all 8 WS event types
 *  - Hydrate full state from CONNECTION_STATE snapshot on reconnect
 *  - Limit routeHistory to MAX_ROUTE_POINTS to prevent memory growth
 *  - Expose a clean, stable API for rendering components
 */
import { useState, useEffect, useRef, useCallback } from 'react';
import { wsClient } from '../services/WebSocketClient';

const MAX_ROUTE_POINTS = 200; // Cap history to prevent unbounded growth

export default function useTrackingSession(requestData) {
  const reqId      = requestData?.request?.id;
  const hospitalLoc = [
    requestData?.request?.latitude  ?? null,
    requestData?.request?.longitude ?? null,
  ];

  // ── Core state ──────────────────────────────────────────────────
  const [requestState,   setRequestState]   = useState(requestData?.request?.status || 'CREATED');
  const [events,         setEvents]         = useState([]);
  const [donorLocation,  setDonorLocation]  = useState(null);
  const [initialDonorPos,setInitialDonorPos]= useState(null);
  const [routeHistory,   setRouteHistory]   = useState([]); // bounded list
  const [etaSeconds,     setEtaSeconds]     = useState(null); // live countdown in seconds
  const [distance,       setDistance]       = useState(null);
  const [progress,       setProgress]       = useState(0);    // 0-1 based on GPS step
  const [acceptedDonor,  setAcceptedDonor]  = useState(null);
  const [searchProgress, setSearchProgress] = useState(null);
  const [ringCountdown,  setRingCountdown]  = useState(null);
  const [connectionState,setConnectionState]= useState('disconnected');
  const [routeGeometry,  setRouteGeometry]  = useState(null); // GeoJSON from OSRM

  // ── Derived flags ─────────────────────────────────────────────
  const isSearching    = ['CREATED','AI_PROCESSING','VALIDATING','SEARCHING','MATCHING','RING1','RING2','WAITING'].includes(requestState);
  const isTracking     = ['TRACKING','ARRIVING'].includes(requestState);
  const isArrived      = requestState === 'ARRIVED';
  const isDonationPhase= ['DONATION_STARTED','DONATION_COMPLETED'].includes(requestState);
  const isClosed       = requestState === 'CLOSED';
  const isCancelled    = requestState === 'CANCELLED';
  const isDonorAccepted= ['DONOR_ACCEPTED','TRACKING','ARRIVING','ARRIVED','DONATION_STARTED','DONATION_COMPLETED','CLOSED'].includes(requestState);

  // ── ETA live countdown between GPS ticks ──────────────────────
  const countdownRef = useRef(null);
  const startCountdown = useCallback((seconds) => {
    if (countdownRef.current) clearInterval(countdownRef.current);
    setEtaSeconds(seconds);
    countdownRef.current = setInterval(() => {
      setEtaSeconds(prev => (prev !== null ? Math.max(0, prev - 1) : null));
    }, 1000);
  }, []);

  // ── Event Handlers (stable refs via useCallback) ───────────────
  const handleStateTransition = useCallback((data) => {
    setRequestState(data.state);
    setEvents(prev => [{
      id:        Date.now().toString(),
      state:     data.state,
      message:   data.message,
      timestamp: new Date().toLocaleTimeString(),
    }, ...prev]);
  }, []);

  const handleGpsUpdate = useCallback((data) => {
    const pos = [data.lat, data.lng];
    setDonorLocation(pos);
    setDistance(data.distance_km);
    setProgress(data.total_steps > 0 ? data.step / data.total_steps : 0);

    // Reset live countdown to new ETA from server
    if (data.eta_minutes !== undefined) {
      startCountdown(data.eta_minutes * 60);
    }

    // Grow route history, bounded to MAX_ROUTE_POINTS
    setRouteHistory(prev => {
      const next = [...prev, pos];
      return next.length > MAX_ROUTE_POINTS
        ? next.slice(next.length - MAX_ROUTE_POINTS)
        : next;
    });

    // Capture initial donor position (for the faded full-route background line)
    setInitialDonorPos(prev => prev ?? pos);

    // Store OSRM route geometry if provided
    if (data.route_geometry) {
      setRouteGeometry(data.route_geometry);
    }
  }, [startCountdown]);

  const handleDonorStatus = useCallback((data) => {
    if (data?.match?.status === 'ACCEPTED') setAcceptedDonor(data.match);
  }, []);

  const handleSearchProgress = useCallback((data) => {
    setSearchProgress(data.data ?? data);
  }, []);

  const handleDonorMarkers = useCallback((data) => {
    // Handled separately if needed; search markers are in SearchProgressStream
  }, []);

  const handleRingCountdown = useCallback((data) => {
    setRingCountdown(data.data ?? data);
  }, []);

  const handleDonorLocationUpdated = useCallback((data) => {
    const loc = data.data ?? data;
    if (loc.latitude && loc.longitude) {
      const pos = [loc.latitude, loc.longitude];
      setDonorLocation(pos);
      if (loc.eta_minutes !== undefined) startCountdown(loc.eta_minutes * 60);
      if (loc.distance_km !== undefined) setDistance(loc.distance_km);
    }
  }, [startCountdown]);

  const handleRequestCancelled = useCallback((data) => {
    setRequestState('CANCELLED');
    setEvents(prev => [{
      id:        Date.now().toString(),
      state:     'CANCELLED',
      message:   data.message || 'Emergency request has been cancelled.',
      timestamp: new Date().toLocaleTimeString(),
    }, ...prev]);
  }, []);

  const handleDonorWithdrawn = useCallback((data) => {
    setEvents(prev => [{
      id:        Date.now().toString(),
      state:     'MATCHING',
      message:   data.data?.message || data.message || 'Donor has withdrawn. Restarting matching...',
      timestamp: new Date().toLocaleTimeString(),
    }, ...prev]);
    setAcceptedDonor(null);
    setDonorLocation(null);
    setEtaSeconds(null);
    setDistance(null);
    setRequestState('MATCHING');
  }, []);

  /**
   * CONNECTION_STATE comes from two sources:
   *  1. The WebSocketClient (local): { state: 'connected' | 'reconnecting' | ... }
   *  2. The server snapshot:         { type: 'CONNECTION_STATE', data: { current_state, timeline, ... } }
   *
   * We distinguish them by checking for data.data?.current_state (server) vs data.state (local).
   */
  const handleConnectionState = useCallback((data) => {
    if (data?.data?.current_state) {
      // Server snapshot — hydrate all state
      const snap = data.data;
      setRequestState(snap.current_state);

      if (Array.isArray(snap.timeline) && snap.timeline.length > 0) {
        setEvents(snap.timeline.map(e => ({
          id:        e.id || String(Math.random()),
          state:     e.state,
          message:   e.message,
          timestamp: new Date(e.created_at).toLocaleTimeString(),
        })));
      }

      if (snap.gps_position?.lat) {
        const pos = [snap.gps_position.lat, snap.gps_position.lng];
        setDonorLocation(pos);
        setInitialDonorPos(prev => prev ?? pos);
      }

      if (snap.eta !== null && snap.eta !== undefined) {
        startCountdown(snap.eta * 60);
      }

      if (snap.accepted_match) {
        setAcceptedDonor(snap.accepted_match);
      }

      setConnectionState('connected');
    } else if (data?.state) {
      // Local WS state change
      setConnectionState(data.state);
    }
  }, [startCountdown]);

  // ── Subscribe / unsubscribe ────────────────────────────────────
  useEffect(() => {
    if (!reqId) return;

    wsClient.connect(reqId);

    wsClient.on('STATE_TRANSITION',      handleStateTransition);
    wsClient.on('GPS_UPDATE',            handleGpsUpdate);
    wsClient.on('DONOR_STATUS_CHANGED',  handleDonorStatus);
    wsClient.on('SEARCH_PROGRESS',       handleSearchProgress);
    wsClient.on('DONOR_MARKERS',         handleDonorMarkers);
    wsClient.on('RING_COUNTDOWN',        handleRingCountdown);
    wsClient.on('CONNECTION_STATE',      handleConnectionState);
    wsClient.on('DONOR_LOCATION_UPDATED',handleDonorLocationUpdated);
    wsClient.on('REQUEST_CANCELLED',     handleRequestCancelled);
    wsClient.on('DONOR_WITHDRAWN',       handleDonorWithdrawn);

    return () => {
      wsClient.off('STATE_TRANSITION',      handleStateTransition);
      wsClient.off('GPS_UPDATE',            handleGpsUpdate);
      wsClient.off('DONOR_STATUS_CHANGED',  handleDonorStatus);
      wsClient.off('SEARCH_PROGRESS',       handleSearchProgress);
      wsClient.off('DONOR_MARKERS',         handleDonorMarkers);
      wsClient.off('RING_COUNTDOWN',        handleRingCountdown);
      wsClient.off('CONNECTION_STATE',      handleConnectionState);
      wsClient.off('DONOR_LOCATION_UPDATED',handleDonorLocationUpdated);
      wsClient.off('REQUEST_CANCELLED',     handleRequestCancelled);
      wsClient.off('DONOR_WITHDRAWN',       handleDonorWithdrawn);
      wsClient.disconnect();

      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [reqId]); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    // State
    requestState,
    events,
    donorLocation,
    initialDonorPos,
    routeHistory,
    etaSeconds,
    distance,
    progress,
    acceptedDonor,
    searchProgress,
    ringCountdown,
    connectionState,
    hospitalLoc,
    // Derived flags
    isSearching,
    isTracking,
    isArrived,
    isDonationPhase,
    isClosed,
    isCancelled,
    isDonorAccepted,
    routeGeometry,
  };
}
