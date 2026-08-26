import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getRequestStatus } from '../services/api';
import EmergencyLiveTracker from './EmergencyLiveTracker';
import { Activity, AlertTriangle } from 'lucide-react';

export default function RequesterDashboard({ requestId: propRequestId, onSimulateDonorAction }) {
  const [requestData, setRequestData] = useState(null);
  const [fetchError, setFetchError] = useState(null);
  const { id: routeId } = useParams();
  const navigate = useNavigate();
  const requestId = propRequestId || routeId;

  useEffect(() => {
    if (!requestId) {
      setFetchError('No emergency request ID found.');
      return;
    }
    setRequestData(null);
    setFetchError(null);

    // Fetch with retry — on page reload the backend may need a moment
    let cancelled = false;
    const fetchStatus = async (attempt = 0) => {
      try {
        const data = await getRequestStatus(requestId);
        if (!cancelled) setRequestData(data);
      } catch (error) {
        if (cancelled) return;
        if (attempt < 3) {
          setTimeout(() => fetchStatus(attempt + 1), 1000 * (attempt + 1));
        } else {
          console.error('Failed to fetch request status after retries:', error);
          setFetchError(`Could not load emergency #${requestId}. The request may have expired or the server is unavailable.`);
        }
      }
    };
    fetchStatus();
    return () => { cancelled = true; };
  }, [requestId]);

  // Error state — give the user a way back
  if (fetchError) {
    const isMissingId = !requestId;
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-6
                      bg-[#050505] w-full h-full absolute inset-0 z-50 px-6 text-center">
        <AlertTriangle className="w-12 h-12 text-amber-500" />
        <h3 className="text-xl font-black text-white tracking-widest uppercase">
          {isMissingId ? "No Active Emergency" : "Unable to Load"}
        </h3>
        <p className="text-sm text-white/40 max-w-sm">
          {isMissingId ? "Broadcast an emergency request to start tracking live donors." : fetchError}
        </p>
        <button
          onClick={() => navigate(isMissingId ? '/request' : '/')}
          className="mt-4 px-6 py-3 bg-white text-black font-black rounded-2xl text-sm
                     hover:bg-white/90 transition-colors uppercase tracking-wider"
        >
          {isMissingId ? "Broadcast Emergency" : "Return to Home"}
        </button>
      </div>
    );
  }

  // Loading state
  if (!requestData) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-6
                      bg-[#050505] w-full h-full absolute inset-0 z-50">
        <Activity className="w-12 h-12 text-blood-500 animate-pulse" />
        <h3 className="text-xl font-black text-white tracking-widest uppercase">Initializing Radar...</h3>
        <p className="text-xs text-white/30">{requestId}</p>
      </div>
    );
  }

  return (
    <EmergencyLiveTracker
      requestData={requestData}
      onSimulateDonor={onSimulateDonorAction}
    />
  );
}
