// This file must be placed in the public directory to be accessible at the root scope.
importScripts('https://www.gstatic.com/firebasejs/11.0.1/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/11.0.1/firebase-messaging-compat.js');

// IMPORTANT: Do not include sensitive API keys in the service worker directly if they differ by environment.
// Since Vite env vars aren't directly accessible in standard service workers without a bundler plugin,
// we initialize it using URL params passing or injecting via a separate script if possible.
// For simplicity in this demo, we'll listen for a message to get config or we can hardcode for testing.
// Alternatively, we use `importScripts` to pull a config file.

// We will expect the main thread to configure the service worker or we just provide the basic structure.

let messaging = null;

self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'FIREBASE_CONFIG') {
    firebase.initializeApp(event.data.config);
    messaging = firebase.messaging();
    
    messaging.onBackgroundMessage((payload) => {
      console.log('[firebase-messaging-sw.js] Received background message ', payload);
      
      const notificationTitle = payload.notification?.title || 'Emergency Blood Request';
      const notificationOptions = {
        body: payload.notification?.body || 'A new request matches your profile.',
        icon: '/vite.svg'
      };

      self.registration.showNotification(notificationTitle, notificationOptions);
    });
  }
});
