import React, { useState, useMemo } from 'react';
import { Copy, CheckCircle2, Share2, MessageCircle, Smartphone, X, QrCode } from 'lucide-react';

// Tiny inline QR Code generator (no dependency)
function generateQRMatrix(text) {
  // Simplified QR-like visual — actual QR requires a library, so we generate a branded share card instead
  return null;
}

export default function ShareRequestPanel({ requestId, requestDetails, onClose }) {
  const [copied, setCopied] = useState(false);

  const shareUrl = useMemo(() => {
    const base = window.location.origin;
    return `${base}/#/request/${requestId}`;
  }, [requestId]);

  const shareText = useMemo(() => {
    const bt = requestDetails?.blood_type || 'O-';
    const units = requestDetails?.units_needed || 2;
    const hospital = requestDetails?.hospital_name || 'Emergency Hospital';
    return `🚨 URGENT BLOOD NEEDED!\n\n${units} units of ${bt} blood needed at ${hospital}.\n\nIf you can donate or know someone, please help:\n${shareUrl}\n\n#BloodDonation #SaveALife`;
  }, [requestDetails, shareUrl]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = shareUrl;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2500);
    }
  };

  const handleWhatsApp = () => {
    window.open(`https://wa.me/?text=${encodeURIComponent(shareText)}`, '_blank');
  };

  const handleSMS = () => {
    window.open(`sms:?body=${encodeURIComponent(shareText)}`, '_blank');
  };

  const handleNativeShare = async () => {
    if (navigator.share) {
      try {
        await navigator.share({
          title: '🚨 Urgent Blood Request — LifePulse AI',
          text: shareText,
          url: shareUrl,
        });
      } catch {
        // User cancelled or not supported
      }
    } else {
      handleCopy();
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-5 border border-indigo-500/30 bg-indigo-950/15 space-y-4 animate-fade-up">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Share2 className="w-5 h-5 text-indigo-400" />
          <h3 className="font-bold text-white text-sm">Share This Emergency</h3>
        </div>
        {onClose && (
          <button onClick={onClose} className="text-slate-500 hover:text-white transition">
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <p className="text-xs text-slate-400">
        Share this emergency request to reach more potential donors. Every share can save a life.
      </p>

      {/* Share URL with copy */}
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-slate-900/90 rounded-xl px-3.5 py-2.5 border border-slate-800 text-xs text-slate-300 font-mono truncate select-all">
          {shareUrl}
        </div>
        <button
          onClick={handleCopy}
          className={`px-3.5 py-2.5 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all border shrink-0 ${
            copied
              ? 'bg-emerald-950 text-emerald-400 border-emerald-700'
              : 'bg-slate-800 text-slate-200 border-slate-700 hover:bg-slate-700'
          }`}
        >
          {copied ? (
            <>
              <CheckCircle2 className="w-3.5 h-3.5" /> Copied!
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" /> Copy
            </>
          )}
        </button>
      </div>

      {/* Share Buttons */}
      <div className="grid grid-cols-3 gap-2.5">
        <button
          onClick={handleWhatsApp}
          className="py-3 rounded-xl bg-emerald-950/60 text-emerald-400 border border-emerald-800/50 hover:bg-emerald-900/60 transition flex flex-col items-center gap-1.5 text-xs font-bold hover-lift"
        >
          <MessageCircle className="w-5 h-5" />
          WhatsApp
        </button>

        <button
          onClick={handleSMS}
          className="py-3 rounded-xl bg-blue-950/60 text-blue-400 border border-blue-800/50 hover:bg-blue-900/60 transition flex flex-col items-center gap-1.5 text-xs font-bold hover-lift"
        >
          <Smartphone className="w-5 h-5" />
          SMS
        </button>

        <button
          onClick={handleNativeShare}
          className="py-3 rounded-xl bg-purple-950/60 text-purple-400 border border-purple-800/50 hover:bg-purple-900/60 transition flex flex-col items-center gap-1.5 text-xs font-bold hover-lift"
        >
          <Share2 className="w-5 h-5" />
          {navigator.share ? 'Share' : 'Copy Link'}
        </button>
      </div>

      {/* Emergency Info Card */}
      <div className="p-3 rounded-xl bg-red-950/30 border border-red-900/40 text-xs text-red-200 flex items-start gap-2">
        <span className="text-base shrink-0">🩸</span>
        <div>
          <strong className="text-white">{requestDetails?.blood_type || 'O-'}</strong> — {requestDetails?.units_needed || 2} units needed at{' '}
          <strong>{requestDetails?.hospital_name || 'Emergency Hospital'}</strong>
          <div className="text-[10px] text-red-400 mt-0.5 font-mono">
            Request ID: {requestId}
          </div>
        </div>
      </div>
    </div>
  );
}
