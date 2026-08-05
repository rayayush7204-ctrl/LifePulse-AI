import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { getRequestStatus } from '../services/api';
import EmergencyLiveTracker from './EmergencyLiveTracker';
import { Activity } from 'lucide-react';

export default function RequesterDashboard({ requestId: propRequestId, onSimulateDonorAction }) {
  const [requestData, setRequestData] = useState(null);
  const { id: routeId } = useParams();
  const requestId = propRequestId || routeId;

  useEffect(() => {
    if (!requestId) return;
    
    // Initial fetch to get the hospital location and baseline data
    const fetchStatus = async () => {
      try {
        const data = await getRequestStatus(requestId);
        setRequestData(data);
      } catch (error) {
        console.error("Failed to fetch initial request status:", error);
      }
    };
    
    fetchStatus();
  }, [requestId]);

  if (!requestData) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-6 bg-[#050505] w-full h-full fixed inset-0 z-50">
        <Activity className="w-12 h-12 text-blood-500 animate-pulse" />
        <h3 className="text-xl font-black text-white tracking-widest uppercase">Initializing Radar...</h3>
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
