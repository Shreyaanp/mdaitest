import { useEffect, useRef } from 'react';
const DEFAULT_WS_URL = 'ws://127.0.0.1:5000/ws/ui';
export function useControllerSocket(send, options) {
    const socketRef = useRef(null);
    useEffect(() => {
        const wsUrl = options?.wsUrl ?? DEFAULT_WS_URL;
        const onEvent = options?.onEvent;
        const onStatusChange = options?.onStatusChange;
        let cancelled = false;
        const connect = () => {
            if (cancelled)
                return;
            onStatusChange?.('connecting');
            const socket = new WebSocket(wsUrl);
            socketRef.current = socket;
            socket.onopen = () => {
                onStatusChange?.('open');
            };
            socket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    onEvent?.(message);
                    if (message.type === 'heartbeat') {
                        send({ type: 'HEARTBEAT' });
                        return;
                    }
                    if (message.type === 'state' && typeof message.phase === 'string') {
                        send({
                            type: 'CONTROLLER_STATE',
                            phase: message.phase,
                            data: message.data,
                            error: message.error
                        });
                    }
                }
                catch (err) {
                    console.error('Failed to parse controller message', err);
                }
            };
            socket.onclose = () => {
                if (cancelled)
                    return;
                onStatusChange?.('closed');
            };
            socket.onerror = () => {
                socket.close();
            };
        };
        connect();
        return () => {
            cancelled = true;
            socketRef.current?.close();
            socketRef.current = null;
            onStatusChange?.('closed');
        };
    }, [send, options?.wsUrl, options?.onEvent, options?.onStatusChange]);
}
