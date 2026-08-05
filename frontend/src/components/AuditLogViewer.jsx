import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ShieldCheck, ChevronDown, ChevronRight, Search, Filter, CheckCircle2, XCircle, Activity, Hash, RefreshCw } from 'lucide-react';
import { getRequestAudit } from '../services/api';

export default function AuditLogViewer({ activeRequestId }) {
  const [requestIdInput, setRequestIdInput] = useState(activeRequestId || "");
  const [auditLogs, setAuditLogs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedLog, setExpandedLog] = useState(null);
  const [filterStatus, setFilterStatus] = useState('ALL'); 

  useEffect(() => {
    if (activeRequestId) {
      setRequestIdInput(activeRequestId);
      loadAudit(activeRequestId);
    }
  }, [activeRequestId]);

  const loadAudit = async (reqId) => {
    if (!reqId) return;
    setIsLoading(true);
    try {
      const data = await getRequestAudit(reqId);
      setAuditLogs(data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadRequest = (e) => {
    e.preventDefault();
    loadAudit(requestIdInput.trim());
  };

  const filteredLogs = auditLogs.filter(log => {
    if (filterStatus === 'ALL') return true;
    if (filterStatus === 'PASSED') return log.passed_all === true;
    if (filterStatus === 'REJECTED') return log.passed_all === false;
    return true;
  });

  const passCount = auditLogs.filter(l => l.passed_all === true).length;
  const failCount = auditLogs.filter(l => l.passed_all === false).length;

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6 max-w-4xl mx-auto"
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 pb-6 border-b border-white/5">
        <div className="flex items-center gap-4">
          <div className="w-12 h-12 rounded-full bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20">
            <ShieldCheck className="w-6 h-6 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-2xl font-black text-white tracking-tight">AI Compliance Audit</h1>
            <p className="text-xs text-[#86868B] uppercase tracking-widest mt-1">Immutable decision trace</p>
          </div>
        </div>
        
        {/* Stats Chips */}
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 text-[10px] font-black rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
            <CheckCircle2 className="w-3 h-3" /> {passCount} PASSED
          </span>
          <span className="px-3 py-1 text-[10px] font-black rounded-full bg-blood-500/10 text-blood-400 border border-blood-500/20 flex items-center gap-1.5">
            <XCircle className="w-3 h-3" /> {failCount} REJECTED
          </span>
        </div>
      </div>

      {/* Request ID Search */}
      <form onSubmit={handleLoadRequest} className="flex gap-3">
        <div className="relative flex-1">
          <Hash className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-[#86868B]" />
          <input type="text" value={requestIdInput} onChange={(e) => setRequestIdInput(e.target.value)}
            placeholder="Enter Request ID... (e.g. req-abc123)"
            className="w-full bg-[#111111] text-sm font-mono text-white pl-10 pr-4 py-3 rounded-full border border-white/10 focus:outline-none focus:border-indigo-500 transition-colors" />
        </div>
        <button type="submit" disabled={isLoading || !requestIdInput.trim()}
          className="px-6 py-3 bg-white hover:bg-gray-200 text-black font-black text-xs tracking-widest rounded-full flex items-center gap-2 transition disabled:opacity-40">
          {isLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />} LOAD
        </button>
      </form>

      {/* Filter Chips */}
      {auditLogs.length > 0 && (
        <div className="flex items-center gap-2 border-b border-white/5 pb-4">
          <Filter className="w-4 h-4 text-[#86868B]" />
          {[
            { id: 'ALL', label: `ALL (${auditLogs.length})` },
            { id: 'PASSED', label: `PASSED` },
            { id: 'REJECTED', label: `REJECTED` }
          ].map(({ id, label }) => (
            <button key={id} onClick={() => setFilterStatus(id)}
              className={`px-4 py-1.5 text-[10px] font-black tracking-widest rounded-full transition-colors ${
                filterStatus === id
                  ? 'bg-indigo-500 text-white'
                  : 'bg-[#111111] text-[#86868B] border border-white/10 hover:bg-white/5'
              }`}>
              {label}
            </button>
          ))}
        </div>
      )}

      {/* Audit Timeline */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => <div key={i} className="h-24 rounded-3xl bg-[#111111] animate-pulse border border-white/5" />)}
        </div>
      ) : filteredLogs.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-[#86868B]">
          <ShieldCheck className="w-16 h-16 mb-4 opacity-20" />
          <p className="text-sm font-bold uppercase tracking-widest">
            {auditLogs.length === 0 ? 'NO LOGS LOADED' : 'NO MATCHING LOGS'}
          </p>
        </div>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-7 top-4 bottom-4 w-0.5 bg-white/5 hidden md:block rounded-full" />

          <div className="space-y-4">
            {filteredLogs.map((log, idx) => {
              const isPassed = log.passed_all;
              const isExpanded = expandedLog === log.id;
              const reasons = log.reasons || [];

              return (
                <div key={idx} className="relative group">
                  {/* Timeline node */}
                  <div className="hidden md:flex absolute left-[18px] top-6 z-10 w-6 h-6 rounded-full bg-[#050505] border-4 border-[#050505] items-center justify-center">
                    <div className={`w-3 h-3 rounded-full ${isPassed ? 'bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.5)]' : 'bg-blood-500 shadow-[0_0_10px_rgba(229,9,20,0.5)]'}`} />
                  </div>

                  {/* Card */}
                  <div className={`md:ml-16 rounded-3xl border transition-colors cursor-pointer overflow-hidden ${
                    isExpanded ? 'bg-[#0A0A0C] border-white/20' : 'bg-[#111111] border-white/5 hover:border-white/10'
                  }`}
                    onClick={() => setExpandedLog(isExpanded ? null : log.id)}
                  >
                    <div className="p-5 flex items-center justify-between gap-4">
                      <div className="flex items-center gap-4 min-w-0">
                        {/* Status Badge */}
                        <span className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${
                          isPassed ? 'bg-emerald-500/10 text-emerald-400' : 'bg-blood-500/10 text-blood-400'
                        }`}>
                          {isPassed ? <CheckCircle2 className="w-5 h-5" /> : <XCircle className="w-5 h-5" />}
                        </span>

                        <div className="min-w-0">
                          <div className="text-white font-bold text-sm truncate">
                            {log.donor_name || log.donor_id || `Audit Record #${idx + 1}`}
                          </div>
                          <div className="text-[10px] text-[#86868B] font-mono mt-0.5">
                            {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '00:00:00'} • {isPassed ? 'COMPLIANT' : 'VIOLATION DETECTED'}
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-4 shrink-0">
                        {log.score != null && (
                          <span className="text-[10px] font-black bg-white/5 px-2 py-1 rounded text-white border border-white/10">
                            {typeof log.score === 'number' ? (log.score * 100).toFixed(0) : log.score}% MATCH
                          </span>
                        )}
                        <motion.div animate={{ rotate: isExpanded ? 180 : 0 }} className="text-[#86868B]">
                          <ChevronDown className="w-5 h-5" />
                        </motion.div>
                      </div>
                    </div>

                    {/* Expanded Detail with Framer Motion AnimatePresence */}
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div 
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: "auto", opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="px-5 pb-5 overflow-hidden"
                        >
                          <div className="pt-4 border-t border-white/5 space-y-4">
                            <div className="text-[10px] font-bold text-[#86868B] uppercase tracking-widest flex items-center gap-1.5">
                              <Activity className="w-3.5 h-3.5 text-indigo-400" /> Evaluation Matrix
                            </div>
                            
                            <div className="space-y-2">
                              {reasons.map((reason, ri) => {
                                const isPass = reason.toUpperCase().startsWith('PASS');
                                return (
                                  <div key={ri} className={`flex items-start gap-3 p-3 rounded-xl border ${
                                    isPass ? 'bg-emerald-500/5 border-emerald-500/10 text-emerald-300' : 'bg-blood-500/5 border-blood-500/10 text-blood-300'
                                  }`}>
                                    {isPass
                                      ? <CheckCircle2 className="w-4 h-4 shrink-0" />
                                      : <XCircle className="w-4 h-4 shrink-0" />
                                    }
                                    <span className="text-xs font-mono leading-relaxed">{reason}</span>
                                  </div>
                                );
                              })}
                            </div>

                            {/* Raw JSON Toggle */}
                            <details className="group">
                              <summary className="cursor-pointer text-[#86868B] hover:text-white transition font-bold text-[10px] uppercase tracking-widest flex items-center gap-1 select-none">
                                <ChevronRight className="w-3 h-3 group-open:rotate-90 transition-transform" /> VIEW RAW LOG
                              </summary>
                              <div className="mt-3 p-4 bg-[#050505] border border-white/5 rounded-2xl overflow-x-auto">
                                <pre className="text-[#86868B] font-mono text-[10px] leading-relaxed">
                                  {JSON.stringify(log, null, 2)}
                                </pre>
                              </div>
                            </details>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </motion.div>
  );
}
