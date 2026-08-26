/**
 * WebSocket Client with typed event handlers for the dispatch experience.
 * Handles: STATE_TRANSITION, SEARCH_PROGRESS, DONOR_MARKERS, RING_COUNTDOWN,
 * GPS_UPDATE, DONOR_ACCEPTED_HIGHLIGHT, ETA_UPDATE, DONOR_LOCATION_UPDATED,
 * DONOR_STATUS_CHANGED, RING_ESCALATED, and connection state management.
 */

class WebSocketClient {
    constructor() {
        this.socket = null;
        this.listeners = {};
        this.reconnectTimer = null;
        this.request_id = null;
        // Use VITE_WS_URL env override (production) or derive from current window host (dev through Vite proxy)
        const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.baseUrl = import.meta.env.VITE_WS_URL || `${proto}//${window.location.host}/ws/requests`;
        this.connectionState = "disconnected"; // disconnected | connecting | connected | reconnecting

        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
    }

    connect(request_id) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.disconnect();
        }
        
        this.request_id = request_id;
        this.setConnectionState("connecting");
        const url = `${this.baseUrl}/${request_id}`;
        
        try {
            this.socket = new WebSocket(url);
            
            this.socket.onopen = () => {
                console.log(`[WS] Connected to request ${request_id}`);
                this.reconnectAttempts = 0;
                this.setConnectionState("connected");
                this.emit("connected", { request_id });
                if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
            };

            this.socket.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    const type = data.type || data.event || "UNKNOWN";
                    this.emit(type, data);
                } catch (e) {
                    console.error("[WS] Error parsing message:", e);
                }
            };

            this.socket.onclose = (event) => {
                console.log("[WS] Disconnected:", event);
                this.emit("disconnected", event);
                // Auto-reconnect if not intentionally closed
                if (!event.wasClean) {
                    this.setConnectionState("reconnecting");
                    this.scheduleReconnect();
                } else {
                    this.setConnectionState("disconnected");
                }
            };

            this.socket.onerror = (error) => {
                console.error("[WS] Error:", error);
                this.emit("error", error);
            };
        } catch (e) {
            console.error("[WS] Connection failed:", e);
            this.setConnectionState("reconnecting");
            this.scheduleReconnect();
        }
    }

    setConnectionState(state) {
        this.connectionState = state;
        this.emit("CONNECTION_STATE", { state });
    }

    getConnectionState() {
        return this.connectionState;
    }

    scheduleReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.log("[WS] Max reconnect attempts reached.");
            this.setConnectionState("disconnected");
            return;
        }
        
        if (!this.reconnectTimer && this.request_id) {
            const delay = Math.min(3000 * Math.pow(1.5, this.reconnectAttempts), 15000);
            this.reconnectAttempts++;
            console.log(`[WS] Scheduling reconnect in ${Math.round(delay / 1000)}s (attempt ${this.reconnectAttempts})...`);
            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                this.connect(this.request_id);
            }, delay);
        }
    }

    disconnect() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.socket) {
            this.socket.close(1000, "Intentional disconnect");
            this.socket = null;
        }
        this.request_id = null;
        this.reconnectAttempts = 0;
        this.setConnectionState("disconnected");
    }

    send(type, payload) {
        if (this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify({ type, ...payload }));
        }
    }

    on(event, callback) {
        if (!this.listeners[event]) {
            this.listeners[event] = [];
        }
        this.listeners[event].push(callback);
    }

    off(event, callback) {
        if (!this.listeners[event]) return;
        this.listeners[event] = this.listeners[event].filter(cb => cb !== callback);
    }

    emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(cb => cb(data));
        }
    }
}

// Export a singleton instance
export const wsClient = new WebSocketClient();
