import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'
import 'leaflet/dist/leaflet.css'
import { ErrorBoundary } from './components/ErrorBoundary.jsx'

// Prevent silent blank screens from unhandled promises
window.addEventListener('unhandledrejection', (event) => {
  console.error('[Global] Unhandled Promise Rejection:', event.reason);
});

window.addEventListener('error', (event) => {
  console.error('[Global] Uncaught Error:', event.error);
});

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
