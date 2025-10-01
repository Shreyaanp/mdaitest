import { useEffect, useState, useRef } from 'react'

interface LivenessMetrics {
  stability?: number
  focus?: number
  composite?: number
  instantAlive?: boolean
  stableAlive?: boolean
  depthOk?: boolean
  screenOk?: boolean
  movementOk?: boolean
}

export default function DebugPreview() {
  const [cameraActive, setCameraActive] = useState(false)
  const [cameraSource, setCameraSource] = useState<'realsense' | 'webcam'>('webcam')
  const [eyeTrackingMode, setEyeTrackingMode] = useState(false)
  const [metrics, setMetrics] = useState<LivenessMetrics>({})
  const [logs, setLogs] = useState<string[]>([])
  const imgRef = useRef<HTMLImageElement | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  const addLog = (msg: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [...prev.slice(-50), `[${timestamp}] ${msg}`])
    console.log('🔍 [DEBUG PREVIEW]', msg)
  }
  
  const toggleEyeTracking = async () => {
    try {
      const newMode = !eyeTrackingMode
      const mode = newMode ? 'eye_tracking' : 'normal'
      
      const response = await fetch('http://localhost:5000/debug/preview-mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode })
      })
      
      if (response.ok) {
        const data = await response.json()
        setEyeTrackingMode(newMode)
        addLog(`👁️ Preview mode: ${data.mode}`)
      } else {
        addLog(`❌ Failed to toggle preview mode: ${response.status}`)
      }
    } catch (error) {
      addLog(`❌ Error toggling eye tracking: ${error}`)
    }
  }
  
  const switchCameraSource = async (source: 'realsense' | 'webcam') => {
    try {
      const response = await fetch('http://localhost:5000/debug/camera-source', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source })
      })
      
      if (response.ok) {
        const data = await response.json()
        setCameraSource(source)
        addLog(`📷 Camera source: ${data.camera_source}`)
        
        // If camera is active, restart stream with new source
        if (cameraActive && imgRef.current) {
          imgRef.current.src = `http://localhost:5000/preview?t=${Date.now()}`
        }
      } else {
        addLog(`❌ Failed to switch camera source: ${response.status}`)
      }
    } catch (error) {
      addLog(`❌ Error switching camera: ${error}`)
    }
  }

  const activateCamera = async () => {
    try {
      const endpoint = cameraSource === 'webcam' 
        ? 'http://localhost:5000/debug/webcam'
        : 'http://localhost:5000/debug/preview'
      
      addLog(`Activating ${cameraSource} camera...`)
      
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: true })
      })
      
      if (response.ok) {
        const data = await response.json()
        setCameraActive(true)
        
        if (cameraSource === 'webcam') {
          addLog(`✅ Webcam activated (laptop camera)`)
        } else {
          addLog(`✅ RealSense activated (hardware=${data.hardware_active}, liveness=${data.liveness_active})`)
        }
        
        // Setup MJPEG stream
        if (imgRef.current) {
          const streamUrl = `http://localhost:5000/preview?t=${Date.now()}`
          imgRef.current.src = streamUrl
          addLog(`📺 MJPEG stream started: ${streamUrl}`)
        }
        
        // Connect to metrics websocket (only for RealSense)
        if (cameraSource === 'realsense') {
          const ws = new WebSocket('ws://localhost:5000/ws/ui')
          wsRef.current = ws
          
          ws.onopen = () => addLog('✅ WebSocket connected for metrics')
          ws.onclose = () => addLog('❌ WebSocket closed')
          ws.onerror = (err) => addLog(`❌ WebSocket error`)
          
          ws.onmessage = (event) => {
            try {
              const msg = JSON.parse(event.data)
              
              if (msg.type === 'metrics') {
                setMetrics(msg.data)
                const { stable_alive, instant_alive, depth_ok, screen_ok, movement_ok } = msg.data
                addLog(`📊 ${instant_alive ? '✅' : '❌'} instant | ${stable_alive ? '✅' : '❌'} stable | D:${depth_ok ? '✓' : '✗'} S:${screen_ok ? '✓' : '✗'} M:${movement_ok ? '✓' : '✗'}`)
              } else if (msg.type === 'state') {
                addLog(`📍 Phase: ${msg.phase}`)
              } else if (msg.type === 'heartbeat') {
                // Ignore heartbeats
              } else {
                addLog(`📨 ${msg.type}`)
              }
            } catch (e) {
              console.error('Failed to parse message:', e)
            }
          }
        }
        
      } else {
        addLog(`❌ Failed to activate camera: ${response.status}`)
      }
    } catch (error) {
      addLog(`❌ Error: ${error}`)
    }
  }

  const deactivateCamera = async () => {
    try {
      const endpoint = cameraSource === 'webcam' 
        ? 'http://localhost:5000/debug/webcam'
        : 'http://localhost:5000/debug/preview'
      
      addLog('Deactivating camera...')
      
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      
      if (imgRef.current) {
        imgRef.current.src = ''
      }
      
      await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: false })
      })
      
      setCameraActive(false)
      setMetrics({})
      addLog('✅ Camera deactivated')
    } catch (error) {
      addLog(`❌ Error: ${error}`)
    }
  }

  useEffect(() => {
    // Initialize camera source on mount
    const initCameraSource = async () => {
      try {
        const response = await fetch('http://localhost:5000/debug/camera-source', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: 'webcam' })
        })
        if (response.ok) {
          console.log('Camera source initialized to webcam')
        }
      } catch (error) {
        console.error('Failed to initialize camera source:', error)
      }
    }
    
    initCameraSource()
    
    return () => {
      if (wsRef.current) wsRef.current.close()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div style={{ 
      width: '100vw', 
      height: '100vh', 
      background: '#000', 
      color: '#fff',
      fontFamily: 'monospace',
      display: 'flex'
    }}>
      {/* Left: Preview */}
      <div style={{ 
        flex: 2, 
        position: 'relative',
        background: '#111',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center'
      }}>
        <img
          ref={imgRef}
          alt="Camera preview"
          style={{
            maxWidth: '100%',
            maxHeight: '100%',
            objectFit: 'contain',
            display: cameraActive ? 'block' : 'none',
            border: '2px solid #333'
          }}
        />
        
        {!cameraActive && (
          <div style={{
            textAlign: 'center'
          }}>
            <p style={{ fontSize: '24px', margin: '20px' }}>Camera Inactive</p>
            <p style={{ fontSize: '14px', opacity: 0.6 }}>Click "Start Camera" to begin</p>
          </div>
        )}
        
        {/* Metrics Overlay - Only for RealSense */}
        {cameraActive && cameraSource === 'realsense' && (
          <div style={{
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
          }}>
            <div style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px', color: '#4f4' }}>
              🔬 LIVENESS HEURISTICS
            </div>
            
            <div style={{ marginBottom: '8px', borderBottom: '1px solid #333', paddingBottom: '8px' }}>
              <strong>Quality Metrics:</strong>
            </div>
            <div>Stability: <span style={{float: 'right', color: '#4af'}}>{metrics.stability?.toFixed(3) ?? 'N/A'}</span></div>
            <div>Focus: <span style={{float: 'right', color: '#4af'}}>{metrics.focus?.toFixed(1) ?? 'N/A'}</span></div>
            <div>Composite: <span style={{float: 'right', color: '#4af'}}>{metrics.composite?.toFixed(3) ?? 'N/A'}</span></div>
            
            <div style={{ marginTop: '12px', marginBottom: '8px', borderBottom: '1px solid #333', paddingBottom: '8px' }}>
              <strong>Liveness Checks:</strong>
            </div>
            <div>
              <span style={{ color: metrics.instantAlive ? '#0f0' : '#f00', fontWeight: 'bold' }}>
                {metrics.instantAlive ? '✅' : '❌'} Instant Alive
              </span>
            </div>
            <div>
              <span style={{ color: metrics.stableAlive ? '#0f0' : '#f00', fontWeight: 'bold' }}>
                {metrics.stableAlive ? '✅' : '❌'} Stable Alive
              </span>
            </div>
            
            <div style={{ marginTop: '12px', fontSize: '11px', opacity: 0.8 }}>
              <div>
                Depth (3D Profile): 
                <span style={{ float: 'right', color: metrics.depthOk ? '#0f0' : '#f00' }}>
                  {metrics.depthOk ? '✓ PASS' : '✗ FAIL'}
                </span>
              </div>
              <div>
                IR Anti-Spoofing: 
                <span style={{ float: 'right', color: metrics.screenOk ? '#0f0' : '#f00' }}>
                  {metrics.screenOk ? '✓ PASS' : '✗ FAIL'}
                </span>
              </div>
              <div>
                Movement Detection: 
                <span style={{ float: 'right', color: metrics.movementOk ? '#0f0' : '#f00' }}>
                  {metrics.movementOk ? '✓ PASS' : '✗ FAIL'}
                </span>
              </div>
            </div>
            
            <div style={{ marginTop: '12px', fontSize: '10px', opacity: 0.5, fontStyle: 'italic' }}>
              instant_alive = depth_ok ∧ screen_ok ∧ movement_ok
            </div>
          </div>
        )}
      </div>

      {/* Right: Controls & Logs */}
      <div style={{ 
        flex: 1, 
        background: '#0a0a0a',
        padding: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        borderLeft: '1px solid #333'
      }}>
        <div>
          <h2 style={{ margin: '0 0 15px 0', fontSize: '18px', color: '#4f4' }}>
            🔬 Camera Debug Preview
          </h2>
          
          <div style={{ marginBottom: '10px', fontSize: '11px', opacity: 0.7, lineHeight: '1.6' }}>
            Tests camera + liveness without full session flow
          </div>
          
          {/* Camera Source Selector */}
          <div style={{ marginBottom: '15px' }}>
            <div style={{ fontSize: '12px', marginBottom: '8px', opacity: 0.8 }}>
              Camera Source:
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={() => !cameraActive && switchCameraSource('webcam')}
                disabled={cameraActive}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: cameraSource === 'webcam' ? '#4af' : '#222',
                  color: cameraSource === 'webcam' ? '#000' : '#aaa',
                  border: cameraSource === 'webcam' ? '2px solid #4af' : '2px solid #444',
                  borderRadius: '6px',
                  cursor: cameraActive ? 'not-allowed' : 'pointer',
                  fontWeight: cameraSource === 'webcam' ? 'bold' : 'normal',
                  fontSize: '12px',
                  opacity: cameraActive ? 0.5 : 1
                }}
              >
                💻 Laptop Camera
              </button>
              <button
                onClick={() => !cameraActive && switchCameraSource('realsense')}
                disabled={cameraActive}
                style={{
                  flex: 1,
                  padding: '10px',
                  background: cameraSource === 'realsense' ? '#4af' : '#222',
                  color: cameraSource === 'realsense' ? '#000' : '#aaa',
                  border: cameraSource === 'realsense' ? '2px solid #4af' : '2px solid #444',
                  borderRadius: '6px',
                  cursor: cameraActive ? 'not-allowed' : 'pointer',
                  fontWeight: cameraSource === 'realsense' ? 'bold' : 'normal',
                  fontSize: '12px',
                  opacity: cameraActive ? 0.5 : 1
                }}
              >
                📷 RealSense D435i
              </button>
            </div>
            <div style={{ fontSize: '10px', marginTop: '5px', opacity: 0.5, textAlign: 'center' }}>
              {cameraActive ? '⚠️ Stop camera to switch source' : 'Select before starting camera'}
            </div>
          </div>
          
          <button
            onClick={cameraActive ? deactivateCamera : activateCamera}
            style={{
              padding: '12px 24px',
              background: cameraActive ? '#f44' : '#4f4',
              color: '#000',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '14px',
              width: '100%',
              marginBottom: '10px'
            }}
          >
            {cameraActive ? '⏹ Stop Camera' : '▶ Start Camera'}
          </button>
          
          <button
            onClick={toggleEyeTracking}
            disabled={!cameraActive}
            style={{
              padding: '10px 20px',
              background: eyeTrackingMode ? '#764ba2' : '#333',
              color: eyeTrackingMode ? '#fff' : '#aaa',
              border: eyeTrackingMode ? '2px solid #667eea' : '2px solid #444',
              borderRadius: '6px',
              cursor: cameraActive ? 'pointer' : 'not-allowed',
              fontWeight: 'bold',
              fontSize: '13px',
              width: '100%',
              marginBottom: '15px',
              opacity: cameraActive ? 1 : 0.5
            }}
          >
            {eyeTrackingMode ? '👁️ Eye of Horus Mode ON' : '👁️ Eye of Horus Mode OFF'}
          </button>
          
          <div style={{ 
            fontSize: '11px', 
            opacity: 0.6, 
            padding: '10px',
            background: '#111',
            borderRadius: '4px',
            marginBottom: '10px'
          }}>
            <div>📺 Stream: MJPEG {eyeTrackingMode ? '(Eye Tracking)' : '(Normal)'}</div>
            <div>📷 Source: {cameraSource === 'webcam' ? 'Laptop Camera' : 'RealSense D435i'}</div>
            {cameraSource === 'realsense' && (
              <>
                <div>📊 Metrics: WebSocket</div>
                <div>🔬 Heuristics: IR + Depth + Movement</div>
              </>
            )}
            {cameraSource === 'webcam' && (
              <div>💻 Simple: Face detection only</div>
            )}
            {eyeTrackingMode && <div style={{color: '#667eea'}}>👁️ Visualizing: Eye landmarks only</div>}
          </div>
        </div>

        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <h3 style={{ margin: '0 0 10px 0', fontSize: '14px' }}>
            📋 Event Logs ({logs.length})
          </h3>
          <div style={{
            flex: 1,
            background: '#000',
            padding: '10px',
            borderRadius: '4px',
            fontSize: '10px',
            fontFamily: 'monospace',
            overflow: 'auto',
            border: '1px solid #222'
          }}>
            {logs.map((log, i) => (
              <div 
                key={i} 
                style={{ 
                  marginBottom: '3px',
                  color: log.includes('❌') ? '#f44' : 
                         log.includes('✅') ? '#4f4' : 
                         log.includes('📊') ? '#4af' : '#fff'
                }}
              >
                {log}
              </div>
            ))}
            {logs.length === 0 && (
              <div style={{ opacity: 0.4 }}>No logs yet... Click "Start Camera" to begin</div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}