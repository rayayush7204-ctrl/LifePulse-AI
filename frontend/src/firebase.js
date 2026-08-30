import { initializeApp } from "firebase/app";
import { getMessaging, getToken, onMessage, isSupported } from "firebase/messaging";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID
};

const app = initializeApp(firebaseConfig);

// ── SAFE Messaging init ────────────────────────────────────────
// getMessaging() throws on browsers that don't support FCM (e.g. iOS Safari
// without a service-worker context). We must never let that crash the React
// tree, so we initialise lazily and guard every call site.
let messaging = null;

// Lazy, one-shot initialiser — returns messaging instance or null.
async function getMessagingSafe() {
  if (messaging) return messaging;
  try {
    const supported = await isSupported();
    if (supported) {
      messaging = getMessaging(app);
      return messaging;
    }
  } catch (err) {
    console.warn("[Firebase] Messaging not supported on this browser:", err.message);
  }
  return null;
}

export const requestFirebaseNotificationPermission = async () => {
  try {
    const msg = await getMessagingSafe();
    if (!msg) {
      console.warn("[Firebase] Push notifications are not supported on this browser/device.");
      return null;
    }
    const permission = await Notification.requestPermission();
    if (permission === 'granted') {
      // Properly register the service worker
      const registration = await navigator.serviceWorker.register('/firebase-messaging-sw.js');

      // Wait for it to be ready
      await navigator.serviceWorker.ready;

      // Post the public config so the SW can initialize Firebase
      if (registration.active) {
        registration.active.postMessage({
          type: 'FIREBASE_CONFIG',
          config: firebaseConfig
        });
      }

      const token = await getToken(msg, { 
        vapidKey: import.meta.env.VITE_FIREBASE_VAPID_KEY,
        serviceWorkerRegistration: registration
      });
      return token;
    } else {
      console.warn("Notification permission denied.");
      return null;
    }
  } catch (error) {
    console.error("Error getting notification permission or token:", error);
    return null;
  }
};

export const subscribeToForegroundMessages = async (callback) => {
  try {
    const msg = await getMessagingSafe();
    if (msg) {
      return onMessage(msg, callback);
    }
  } catch (err) {
    console.warn("[Firebase] Foreground subscription failed:", err);
  }
  return () => {}; // return no-op unsubscribe if failed
};

export { messaging };
