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
        icon: '/vite.svg',
        data: payload.data
      };

      self.registration.showNotification(notificationTitle, notificationOptions);
    });
  }
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const data = event.notification.data || {};
  // Construct URL with match info if available
  let url = '/';
  if (data.type === 'EMERGENCY_REQUEST' && data.request_id) {
    url = `/?incoming_request=${data.request_id}&match_id=${data.match_id}`;
  }

  const urlToOpen = new URL(url, self.location.origin).href;

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // If app is already open, focus it and optionally post a message to it
      for (let i = 0; i < windowClients.length; i++) {
        const client = windowClients[i];
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.postMessage({
            type: 'NOTIFICATION_CLICKED',
            data: data
          });
          return client.focus();
        }
      }
      // If no window is open, open one
      if (clients.openWindow) {
        return clients.openWindow(urlToOpen);
      }
    })
  );
});
