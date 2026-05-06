import { useEffect, useRef, useCallback } from 'react';

type MessageHandler = (data: unknown) => void;

interface UseWebSocketOptions {
  onMessage?: MessageHandler;
  onOpen?: () => void;
  onClose?: () => void;
  reconnectDelay?: number;
  enabled?: boolean;
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
  const { onMessage, onOpen, onClose, reconnectDelay = 3000, enabled = true } = options;
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const isMounted = useRef(true);

  const connect = useCallback(() => {
    if (!enabled || !isMounted.current) return;

    const token = localStorage.getItem('access_token');
    const fullUrl = token ? `${url}?token=${token}` : url;

    try {
      const ws = new WebSocket(fullUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        if (isMounted.current) onOpen?.();
      };

      ws.onmessage = (event) => {
        if (!isMounted.current) return;
        try {
          const data = JSON.parse(event.data as string) as unknown;
          onMessage?.(data);
        } catch {
          // ignore non-JSON
        }
      };

      ws.onclose = () => {
        if (!isMounted.current) return;
        onClose?.();
        // Переподключение
        reconnectTimer.current = setTimeout(connect, reconnectDelay);
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch {
      reconnectTimer.current = setTimeout(connect, reconnectDelay);
    }
  }, [url, enabled, onMessage, onOpen, onClose, reconnectDelay]);

  useEffect(() => {
    isMounted.current = true;
    connect();

    return () => {
      isMounted.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { send };
}
