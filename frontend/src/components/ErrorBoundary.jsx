import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true };
  }

  componentDidCatch(error, errorInfo) {
    this.setState({ error, errorInfo });
    console.error("[ErrorBoundary] Caught a crash:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onRetry) {
      this.props.onRetry();
    } else {
      window.location.reload();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.handleRetry);
      }
      return (
        <div className="min-h-[50vh] flex flex-col items-center justify-center p-6 bg-[#050505] text-center w-full h-full inset-0 absolute z-[999]">
          <div className="w-16 h-16 rounded-2xl bg-blood-500/20 flex items-center justify-center mb-6 border border-blood-500/30">
            <AlertTriangle className="w-8 h-8 text-blood-500" />
          </div>
          <h2 className="text-2xl font-black text-white uppercase tracking-tight mb-2">Something went wrong</h2>
          <p className="text-[#86868B] text-sm max-w-sm mx-auto mb-8">
            An unexpected error occurred in this section of the application.
          </p>
          <button
            onClick={this.handleRetry}
            className="flex items-center gap-2 px-8 py-3 rounded-full bg-white text-black font-black text-sm uppercase tracking-widest hover:bg-gray-200 transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Retry
          </button>
          
          {process.env.NODE_ENV === 'development' && this.state.error && (
            <div className="mt-8 p-4 bg-red-950/50 border border-red-500/30 rounded-xl text-left w-full max-w-2xl overflow-auto max-h-64">
              <p className="text-red-400 font-bold text-xs mb-2 font-mono">{this.state.error.toString()}</p>
              <pre className="text-red-300/70 text-[10px] font-mono whitespace-pre-wrap">
                {this.state.errorInfo?.componentStack}
              </pre>
            </div>
          )}
        </div>
      );
    }

    return this.props.children;
  }
}

export function SectionErrorBoundary({ children, onRetry }) {
  return (
    <ErrorBoundary onRetry={onRetry}>
      {children}
    </ErrorBoundary>
  );
}
