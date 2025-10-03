import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useState, useRef } from 'react';
export default function DebugPreview() {
    const [cameraActive, setCameraActive] = useState(false);
    const [metrics, setMetrics] = useState({});
    const [logs, setLogs] = useState([]);
    const imgRef = useRef(null);
    const wsRef = useRef(null);
    const addLog = (msg) => {
        const timestamp = new Date().toLocaleTimeString();
        setLogs(prev => [...prev.slice(-50), `[${timestamp}] ${msg}`]);
        console.log('🔍 [DEBUG PREVIEW]', msg);
    };
    const activateCamera = async () => {
        try {
            addLog('Activating camera hardware...');
            const response = await fetch('http://localhost:5000/debug/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: true })
            });
            if (response.ok) {
                const data = await response.json();
                setCameraActive(true);
                addLog(`✅ Camera activated (hardware=${data.hardware_active}, liveness=${data.liveness_active})`);
                // UI stream disabled; show placeholder image instead
                if (imgRef.current) {
                    imgRef.current.src = '/hero/scan.gif';
                    addLog('📺 Placeholder image shown (stream disabled)');
                }
                // Connect to metrics websocket
                const ws = new WebSocket('ws://localhost:5000/ws/ui');
                wsRef.current = ws;
                ws.onopen = () => addLog('✅ WebSocket connected for metrics');
                ws.onclose = () => addLog('❌ WebSocket closed');
                ws.onerror = (err) => addLog(`❌ WebSocket error`);
                ws.onmessage = (event) => {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.type === 'metrics') {
                            setMetrics(msg.data);
                            const { stable_alive, instant_alive, depth_ok, screen_ok, movement_ok } = msg.data;
                            addLog(`📊 ${instant_alive ? '✅' : '❌'} instant | ${stable_alive ? '✅' : '❌'} stable | D:${depth_ok ? '✓' : '✗'} S:${screen_ok ? '✓' : '✗'} M:${movement_ok ? '✓' : '✗'}`);
                        }
                        else if (msg.type === 'state') {
                            addLog(`📍 Phase: ${msg.phase}`);
                        }
                        else if (msg.type === 'heartbeat') {
                            // Ignore heartbeats
                        }
                        else {
                            addLog(`📨 ${msg.type}`);
                        }
                    }
                    catch (e) {
                        console.error('Failed to parse message:', e);
                    }
                };
            }
            else {
                addLog(`❌ Failed to activate camera: ${response.status}`);
            }
        }
        catch (error) {
            addLog(`❌ Error: ${error}`);
        }
    };
    const deactivateCamera = async () => {
        try {
            addLog('Deactivating camera...');
            if (wsRef.current) {
                wsRef.current.close();
                wsRef.current = null;
            }
            if (imgRef.current) {
                imgRef.current.src = '';
            }
            await fetch('http://localhost:5000/debug/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: false })
            });
            setCameraActive(false);
            setMetrics({});
            addLog('✅ Camera deactivated');
        }
        catch (error) {
            addLog(`❌ Error: ${error}`);
        }
    };
    useEffect(() => {
        return () => {
            if (wsRef.current)
                wsRef.current.close();
        };
    }, []);
    return (_jsxs("div", { style: {
            width: '100vw',
            height: '100vh',
            background: '#000',
            color: '#fff',
            fontFamily: 'monospace',
            display: 'flex'
        }, children: [_jsxs("div", { style: {
                    flex: 2,
                    position: 'relative',
                    background: '#111',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                }, children: [_jsx("img", { ref: imgRef, alt: "Camera preview", style: {
                            maxWidth: '100%',
                            maxHeight: '100%',
                            objectFit: 'contain',
                            display: cameraActive ? 'block' : 'none',
                            border: '2px solid #333'
                        } }), !cameraActive && (_jsxs("div", { style: {
                            textAlign: 'center'
                        }, children: [_jsx("p", { style: { fontSize: '24px', margin: '20px' }, children: "Camera Inactive" }), _jsx("p", { style: { fontSize: '14px', opacity: 0.6 }, children: "Click \"Start Camera\" to begin" })] })), cameraActive && (_jsxs("div", { style: {
                            position: 'absolute',
                            top: '20px',
                            left: '20px',
                            background: 'rgba(0,0,0,0.85)',
                            padding: '15px',
                            borderRadius: '8px',
                            fontSize: '13px',
                            lineHeight: '1.8',
                            minWidth: '280px',
                            border: '1px solid #333'
                        }, children: [_jsx("div", { style: { fontSize: '14px', fontWeight: 'bold', marginBottom: '10px', color: '#4f4' }, children: "\uD83D\uDD2C LIVENESS HEURISTICS" }), _jsx("div", { style: { marginBottom: '8px', borderBottom: '1px solid #333', paddingBottom: '8px' }, children: _jsx("strong", { children: "Quality Metrics:" }) }), _jsxs("div", { children: ["Stability: ", _jsx("span", { style: { float: 'right', color: '#4af' }, children: metrics.stability?.toFixed(3) ?? 'N/A' })] }), _jsxs("div", { children: ["Focus: ", _jsx("span", { style: { float: 'right', color: '#4af' }, children: metrics.focus?.toFixed(1) ?? 'N/A' })] }), _jsxs("div", { children: ["Composite: ", _jsx("span", { style: { float: 'right', color: '#4af' }, children: metrics.composite?.toFixed(3) ?? 'N/A' })] }), _jsx("div", { style: { marginTop: '12px', marginBottom: '8px', borderBottom: '1px solid #333', paddingBottom: '8px' }, children: _jsx("strong", { children: "Liveness Checks:" }) }), _jsx("div", { children: _jsxs("span", { style: { color: metrics.instantAlive ? '#0f0' : '#f00', fontWeight: 'bold' }, children: [metrics.instantAlive ? '✅' : '❌', " Instant Alive"] }) }), _jsx("div", { children: _jsxs("span", { style: { color: metrics.stableAlive ? '#0f0' : '#f00', fontWeight: 'bold' }, children: [metrics.stableAlive ? '✅' : '❌', " Stable Alive"] }) }), _jsxs("div", { style: { marginTop: '12px', fontSize: '11px', opacity: 0.8 }, children: [_jsxs("div", { children: ["Depth (3D Profile):", _jsx("span", { style: { float: 'right', color: metrics.depthOk ? '#0f0' : '#f00' }, children: metrics.depthOk ? '✓ PASS' : '✗ FAIL' })] }), _jsxs("div", { children: ["IR Anti-Spoofing:", _jsx("span", { style: { float: 'right', color: metrics.screenOk ? '#0f0' : '#f00' }, children: metrics.screenOk ? '✓ PASS' : '✗ FAIL' })] }), _jsxs("div", { children: ["Movement Detection:", _jsx("span", { style: { float: 'right', color: metrics.movementOk ? '#0f0' : '#f00' }, children: metrics.movementOk ? '✓ PASS' : '✗ FAIL' })] })] }), _jsx("div", { style: { marginTop: '12px', fontSize: '10px', opacity: 0.5, fontStyle: 'italic' }, children: "instant_alive = depth_ok \u2227 screen_ok \u2227 movement_ok" })] }))] }), _jsxs("div", { style: {
                    flex: 1,
                    background: '#0a0a0a',
                    padding: '20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '20px',
                    borderLeft: '1px solid #333'
                }, children: [_jsxs("div", { children: [_jsx("h2", { style: { margin: '0 0 15px 0', fontSize: '18px', color: '#4f4' }, children: "\uD83D\uDD2C Camera Debug Preview" }), _jsx("div", { style: { marginBottom: '10px', fontSize: '11px', opacity: 0.7, lineHeight: '1.6' }, children: "Tests camera + liveness without full session flow" }), _jsx("button", { onClick: cameraActive ? deactivateCamera : activateCamera, style: {
                                    padding: '12px 24px',
                                    background: cameraActive ? '#f44' : '#4f4',
                                    color: '#000',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontWeight: 'bold',
                                    fontSize: '14px',
                                    width: '100%',
                                    marginBottom: '15px'
                                }, children: cameraActive ? '⏹ Stop Camera' : '▶ Start Camera' }), _jsxs("div", { style: {
                                    fontSize: '11px',
                                    opacity: 0.6,
                                    padding: '10px',
                                    background: '#111',
                                    borderRadius: '4px',
                                    marginBottom: '10px'
                                }, children: [_jsx("div", { children: "\uD83D\uDCFA Stream: Placeholder (no /preview)" }), _jsx("div", { children: "\uD83D\uDCCA Metrics: WebSocket" }), _jsx("div", { children: "\uD83D\uDD2C Heuristics: IR + Depth + Movement" })] })] }), _jsxs("div", { style: { flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }, children: [_jsxs("h3", { style: { margin: '0 0 10px 0', fontSize: '14px' }, children: ["\uD83D\uDCCB Event Logs (", logs.length, ")"] }), _jsxs("div", { style: {
                                    flex: 1,
                                    background: '#000',
                                    padding: '10px',
                                    borderRadius: '4px',
                                    fontSize: '10px',
                                    fontFamily: 'monospace',
                                    overflow: 'auto',
                                    border: '1px solid #222'
                                }, children: [logs.map((log, i) => (_jsx("div", { style: {
                                            marginBottom: '3px',
                                            color: log.includes('❌') ? '#f44' :
                                                log.includes('✅') ? '#4f4' :
                                                    log.includes('📊') ? '#4af' : '#fff'
                                        }, children: log }, i))), logs.length === 0 && (_jsx("div", { style: { opacity: 0.4 }, children: "No logs yet... Click \"Start Camera\" to begin" }))] })] })] })] }));
}
