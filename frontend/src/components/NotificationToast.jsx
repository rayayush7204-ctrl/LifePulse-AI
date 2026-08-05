import React, { useState, useEffect, useCallback, createContext, useContext } from 'react';
import { CheckCircle2, AlertTriangle, Info, Heart, X } from 'lucide-react';

// ── Toast Context ───────────────────────────────────────────────
const ToastContext = createContext(null);

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be inside ToastProvider');
  return ctx;
}

const ICONS = {
  success: <CheckCircle2 className="w-5 h-5 text-emerald-400" />, 
  alert: <AlertTriangle className="w-5 h-5 text-amber-400" />,
  emergency: <Heart className="w-5 h-5 text-red-400 animate-heartbeat" />,
  info: <Info className="w-5 h-5 text-blue-400" />,
};

const BORDER_COLORS = {
  success: 'border-emerald-500/40',
  alert: 'border-amber-500/40',
  emergency: 'border-red-500/50',
  info: 'border-blue-500/40',
};

const BAR_COLORS = {
  success: 'bg-emerald-500',
  alert: 'bg-amber-500',
  emergency: 'bg-red-500',
  info: 'bg-blue-500',
};

let toastId = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback(({ title, message, type = 'info', duration = 4000 }) => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, title, message, type, duration, exiting: false }]);

    if (duration > 0) {
      setTimeout(() => {
        setToasts((prev) =>
          prev.map((t) => (t.id === id ? { ...t, exiting: true } : t))
        );
        setTimeout(() => {
          setToasts((prev) => prev.filter((t) => t.id !== id));
        }, 350);
      }, duration);
    }

    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, exiting: true } : t))
    );
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 350);
  }, []);

  return (
    <ToastContext.Provider value={{ addToast, removeToast }}>
      {children}
      {/* Toast Stack */}
      <div className="fixed top-4 right-4 z-[100] flex flex-col gap-3 max-w-sm w-full pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto glass-panel rounded-xl border ${
              BORDER_COLORS[toast.type]
            } p-4 shadow-2xl ${toast.exiting ? 'toast-exit' : 'toast-enter'} relative overflow-hidden`}
          >
            <div className="flex items-start gap-3">
              <div className="shrink-0 mt-0.5">{ICONS[toast.type]}</div>
              <div className="flex-1 min-w-0">
                {toast.title && (
                  <div className="text-sm font-bold text-white truncate">
                    {toast.title}
                  </div>
                )}
                {toast.message && (
                  <div className="text-xs text-slate-300 mt-0.5 line-clamp-2">
                    {toast.message}
                  </div>
                )}
              </div>
              <button
                onClick={() => removeToast(toast.id)}
                className="shrink-0 text-slate-500 hover:text-white transition p-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
            {/* Progress bar */}
            {toast.duration > 0 && (
              <div className="absolute bottom-0 left-0 right-0 h-[2px]">
                <div
                  className={`h-full ${BAR_COLORS[toast.type]} toast-progress opacity-60`}
                  style={{ animationDuration: `${toast.duration}ms` }}
                />
              </div>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export default ToastProvider;
