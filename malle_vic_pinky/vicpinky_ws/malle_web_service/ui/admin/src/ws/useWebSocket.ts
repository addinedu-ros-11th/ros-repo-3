import { useEffect, useRef, useCallback } from "react";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || `ws://${window.location.hostname}:8000`;

export interface WsMessage {
  type: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

type MessageHandler = (msg: WsMessage) => void;

interface UseWebSocketOptions {
  /** WebSocket path, e.g. "/ws/mobile/123" or "/ws/dashboard" */
  path: string;
  /** Called on every incoming message */
  onMessage: MessageHandler;
  /** Auto-reconnect (default true) */
  reconnect?: boolean;
  /** Reconnect interval in ms (default 3000) */
  reconnectInterval?: number;
}

export function useWebSocket({
  path,
  onMessage,
  reconnect = true,
  reconnectInterval = 3000,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(`${WS_BASE}${path}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const msg: WsMessage = JSON.parse(event.data);
        onMessageRef.current(msg);
      } catch (e) {
        console.error("[WS] Failed to parse message:", e);
      }
    };

    ws.onclose = () => {
      if (reconnect) {
        reconnectTimer.current = setTimeout(connect, reconnectInterval);
      }
    };

    ws.onerror = (err) => {
      console.error("[WS] Error:", err);
      ws.close();
    };
  }, [path, reconnect, reconnectInterval]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((type: string, payload: Record<string, unknown> = {}) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload, timestamp: new Date().toISOString() }));
    }
  }, []);

  return { send };
}
