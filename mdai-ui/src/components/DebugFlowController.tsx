/**
 * Comprehensive Debug Flow Controller
 * Single source of truth for testing complete flow
 * Shows ACTUAL production UI flow with debug controls overlaid
 */

import { useState, useEffect, useRef, useMemo, useCallback } from 'react'
import { useMachine } from '@xstate/react'
import { sessionMachine, type SessionPhase } from '../app-state/sessionMachine'
import StageRouter from './StageRouter'
import PreviewSurface from './PreviewSurface'
import { DEFAULT_MOCK_CONFIG, TEST_SCENARIOS, PHASE_TIMINGS } from '../config/mockFlowData'
import type { MockFlowConfig, TestScenario } from '../config/mockFlowData'
import { backendConfig } from '../config'

interface FlowState {
  phase: string
  tofDistance: number
  cameraSource: 'realsense' | 'webcam' | 'mock'
  cameraActive: boolean
  eyeTrackingMode: boolean
  faceDetected: boolean
  validationProgress: number
  frameCount: number
}

export default function DebugFlowController() {
  // Use actual session machine (same as production App)
  const [state, send] = useMachine(sessionMachine)
  
  const [config, setConfig] = useState<MockFlowConfig>(DEFAULT_MOCK_CONFIG)
  const [flowState, setFlowState] = useState<FlowState>({
    phase: 'idle',
    tofDistance: 800,
    cameraSource: 'webcam',
    cameraActive: false,
    eyeTrackingMode: true,
    faceDetected: false,
    validationProgress: 0,
    frameCount: 0
  })
  const [logs, setLogs] = useState<string[]>([])
  const [runningScenario, setRunningScenario] = useState<string | null>(null)
  const [cpuUsage, setCpuUsage] = useState<number>(0)
  const [memoryUsage, setMemoryUsage] = useState<number>(0)
  const wsRef = useRef<WebSocket | null>(null)
  const tofDebounceTimer = useRef<number | null>(null)
  const performanceInterval = useRef<number | null>(null)
  
  // Mock QR payload
  const mockQrPayload = useMemo(() => ({
    token: config.qr.token,
    ws_app_url: config.qr.ws_app_url,
    ws_hardware_url: config.qr.ws_hardware_url,
    server_host: config.qr.server_host
  }), [config])
  
  const { previewUrl } = backendConfig
  const showPreview = state.value === 'human_detect'

  const addLog = (msg: string) => {
    const timestamp = new Date().toLocaleTimeString()
    setLogs(prev => [...prev.slice(-100), `[${timestamp}] ${msg}`])
  }
  
  // Update flowState.phase when state machine changes
  useEffect(() => {
    setFlowState(prev => ({ ...prev, phase: state.value as string }))
  }, [state.value])

  // Initialize camera and WebSocket
  useEffect(() => {
    const init = async () => {
      try {
        // Fetch initial state from backend
        const healthResponse = await fetch('http://localhost:5000/healthz')
        if (healthResponse.ok) {
          const health = await healthResponse.json()
          addLog(`📍 Initial phase: ${health.phase}`)
          // Sync state machine with backend
          send({
            type: 'CONTROLLER_STATE',
            phase: health.phase,
            data: {},
            error: undefined
          })
        }
        
        // Set camera source
        await fetch('http://localhost:5000/debug/camera-source', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ source: config.camera.source })
        })

        // Activate camera if needed
        if (config.camera.source === 'webcam') {
          const response = await fetch('http://localhost:5000/debug/webcam', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: true })
          })
          if (response.ok) {
            setFlowState(prev => ({ ...prev, cameraActive: true, cameraSource: 'webcam' }))
            addLog('✅ Webcam activated')
          }
        }

        // Connect WebSocket for live updates
        const ws = new WebSocket('ws://localhost:5000/ws/ui')
        wsRef.current = ws

        ws.onopen = () => {
          addLog('✅ WebSocket connected')
          console.log('🔌 WebSocket opened')
        }
        
        ws.onerror = (error) => {
          addLog('❌ WebSocket error')
          console.error('🔌 WebSocket error:', error)
        }
        
        ws.onclose = () => {
          addLog('⚠️ WebSocket disconnected')
          console.warn('🔌 WebSocket closed')
        }
        
        ws.onmessage = (event) => {
          try {
            const msg = JSON.parse(event.data)
            console.log('📨 WebSocket message:', msg)
            
            // Sync controller state with UI state machine
            if (msg.type === 'state') {
              const eventData = msg.data || {}
              
              // Add mock QR payload when entering qr_display phase
              if (msg.phase === 'qr_display' && !eventData.qr_payload) {
                eventData.qr_payload = mockQrPayload
                eventData.token = config.qr.token
                eventData.expires_in = 300
              }
              
              send({
                type: 'CONTROLLER_STATE',
                phase: msg.phase,
                data: eventData,
                error: msg.error
              })
              setFlowState(prev => ({ ...prev, phase: msg.phase }))
              addLog(`📍 Phase changed: ${msg.phase}`)
            }
            
            if (msg.type === 'metrics') {
              const data = msg.data || {}
              setFlowState(prev => ({
                ...prev,
                faceDetected: data.face_detected || false,
                validationProgress: data.validation_progress || 0
              }))
            }
          } catch (e) {
            console.error('WS parse error:', e)
          }
        }
      } catch (error) {
        addLog(`❌ Init error: ${error}`)
      }
    }

    init()
    
    // Start CPU/Memory monitoring (real-time)
    performanceInterval.current = setInterval(async () => {
      try {
        const response = await fetch('http://localhost:5000/debug/performance')
        if (response.ok) {
          const data = await response.json()
          setCpuUsage(data.cpu_percent || 0)
          setMemoryUsage(data.memory_percent || 0)
        }
      } catch (e) {
        console.error('Performance monitoring error:', e)
      }
    }, 2000)  // Update every 2s

    return () => {
      if (wsRef.current) wsRef.current.close()
      if (tofDebounceTimer.current) clearTimeout(tofDebounceTimer.current)
      if (performanceInterval.current) clearInterval(performanceInterval.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Trigger ToF with 1.2s debounce
  const triggerToF = async (distance_mm: number, immediate: boolean = false) => {
    try {
      const triggered = distance_mm < 450
      
      if (!immediate) {
        // Clear any existing timer
        if (tofDebounceTimer.current) {
          clearTimeout(tofDebounceTimer.current)
        }
        
        // Update UI immediately
        setFlowState(prev => ({ ...prev, tofDistance: distance_mm }))
        addLog(`📏 ToF: ${distance_mm}mm (waiting 1.2s to trigger...)`)
        
        // Wait 1.2s before actually triggering
        tofDebounceTimer.current = setTimeout(async () => {
          const response = await fetch('http://localhost:5000/debug/mock-tof', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ triggered, distance_mm })
          })
          if (response.ok) {
            addLog(`📏 ToF: ${distance_mm}mm ${triggered ? '✓ TRIGGERED' : '✓ idle'}`)
          }
        }, 1200)
      } else {
        // Immediate trigger (for button clicks)
        const response = await fetch('http://localhost:5000/debug/mock-tof', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ triggered, distance_mm })
        })
        if (response.ok) {
          setFlowState(prev => ({ ...prev, tofDistance: distance_mm }))
          addLog(`📏 ToF: ${distance_mm}mm ${triggered ? '(TRIGGERED)' : '(idle)'}`)
        }
      }
    } catch (error) {
      addLog(`❌ ToF error: ${error}`)
    }
  }

  // Mock app ready with optional scenario parameters
  const mockAppReady = async (scenarioParams?: Record<string, any>) => {
    console.log('🔵 mockAppReady called with params:', scenarioParams)
    addLog('📱 Sending app ready signal...')
    
    try {
      const payload = {
        platform_id: config.qr.platform_id,
        ...scenarioParams  // Merge scenario-specific params
      }
      
      console.log('📤 Sending to /debug/app-ready:', payload)
      
      const response = await fetch('http://localhost:5000/debug/app-ready', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      
      console.log('📥 Response status:', response.status)
      
      if (response.ok) {
        const data = await response.json()
        console.log('📥 Response data:', data)
        
        if (data.scenario) {
          if (data.scenario.no_face) addLog('🎭 Scenario: NO FACE')
          if (data.scenario.lost_tracking) addLog('🎭 Scenario: LOST TRACKING')
          if (data.scenario.liveness_fail) addLog('🎭 Scenario: LIVENESS FAIL')
        }
        addLog(`✅ App ready acknowledged (${data.status})`)
      } else {
        addLog(`❌ App ready failed: ${response.status}`)
      }
    } catch (error) {
      console.error('❌ App ready error:', error)
      addLog(`❌ App ready error: ${error}`)
    }
  }

  // Run automated scenario
  const runScenario = async (scenario: TestScenario) => {
    setRunningScenario(scenario.name)
    addLog(`🎬 Running scenario: ${scenario.name}`)

    for (const step of scenario.steps) {
      if (step.delayMs) {
        await new Promise(resolve => setTimeout(resolve, step.delayMs))
      }

      switch (step.action) {
        case 'trigger_tof':
          await triggerToF(step.params?.distance_mm || 345, true)  // Immediate for scenarios
          break
        case 'mock_app_ready':
          await mockAppReady(step.params)  // Pass scenario params
          break
        case 'wait':
          addLog(`⏳ Waiting ${step.delayMs}ms...`)
          break
        case 'check_phase':
          addLog(`🔍 Expected phase: ${step.params?.expected}, actual: ${state.value}`)
          if (step.params?.expected !== state.value) {
            addLog(`⚠️ Phase mismatch!`)
          }
          break
      }
    }

    setRunningScenario(null)
    addLog(`✅ Scenario complete: ${scenario.name}`)
  }

  // Reset to IDLE
  const resetToIdle = async () => {
    await triggerToF(800, true)  // Immediate trigger
    addLog('🔄 Reset to IDLE')
  }

  return (
    <div style={{
      width: '100vw',
      height: '100vh',
      position: 'relative',
      overflow: 'hidden'
    }}>
      {/* Actual Production UI Flow */}
      <div className="app-shell">
        <div className="visual-area">
          {/* Real stage routing - shows IDLE, hello_human, QR, etc. */}
          <StageRouter state={state} qrPayload={mockQrPayload} />
          
          {/* Real preview surface - shows Eye of Horus during human_detect */}
          <PreviewSurface
            visible={showPreview}
            previewUrl={previewUrl}
            title="Debug Flow Preview"
          />
        </div>
      </div>

      {/* Top Control Panel (Semi-transparent) */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(10px)',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)',
        padding: '16px 20px',
        fontFamily: 'monospace',
        fontSize: '12px',
        color: '#fff',
        zIndex: 1000
      }}>
        {/* Top Row: Current State */}
        <div style={{
          display: 'flex',
          gap: '30px',
          marginBottom: '12px',
          flexWrap: 'wrap'
        }}>
          <div>
            <span style={{ opacity: 0.6 }}>Phase:</span>{' '}
            <span style={{ 
              color: state.value === 'error' ? '#f44' : '#4f4',
              fontWeight: 'bold' 
            }}>
              {state.value}
            </span>
          </div>
          <div>
            <span style={{ opacity: 0.6 }}>ToF:</span>{' '}
            <span style={{ color: flowState.tofDistance < 450 ? '#4f4' : '#888' }}>
              {flowState.tofDistance}mm
            </span>
          </div>
          <div>
            <span style={{ opacity: 0.6 }}>Camera:</span>{' '}
            <span style={{ color: flowState.cameraActive ? '#4f4' : '#f44' }}>
              {flowState.cameraSource} {flowState.cameraActive ? '✓' : '✗'}
            </span>
          </div>
          <div>
            <span style={{ opacity: 0.6 }}>Face:</span>{' '}
            <span style={{ color: flowState.faceDetected ? '#4f4' : '#888' }}>
              {flowState.faceDetected ? 'Detected' : 'Not Found'}
            </span>
          </div>
          <div>
            <span style={{ opacity: 0.6 }}>Progress:</span>{' '}
            <span style={{ color: '#4af' }}>
              {Math.round(flowState.validationProgress * 100)}%
            </span>
          </div>
          <div style={{ marginLeft: 'auto' }}>
            <span style={{ opacity: 0.6 }}>CPU:</span>{' '}
            <span style={{ color: cpuUsage > 80 ? '#f44' : '#4f4' }}>
              {cpuUsage}%
            </span>
            {' | '}
            <span style={{ opacity: 0.6 }}>Mem:</span>{' '}
            <span style={{ color: memoryUsage > 75 ? '#f44' : '#4f4' }}>
              {memoryUsage}%
            </span>
          </div>
        </div>

        {/* Second Row: Quick Controls */}
        <div style={{
          display: 'flex',
          gap: '8px',
          flexWrap: 'wrap',
          marginBottom: '8px'
        }}>
          <button
            onClick={() => triggerToF(345, true)}
            style={{
              padding: '6px 12px',
              background: '#4f4',
              color: '#000',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '11px'
            }}
          >
            ▶ Start Flow (ToF &lt; 450)
          </button>

          <button
            onClick={resetToIdle}
            style={{
              padding: '6px 12px',
              background: '#f44',
              color: '#000',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontWeight: 'bold',
              fontSize: '11px'
            }}
          >
            ⏹ Reset to IDLE
          </button>

          <button
            onClick={() => {
              console.log('🔴 Button clicked! Current phase:', state.value)
              mockAppReady()
            }}
            disabled={state.value !== 'qr_display'}
            style={{
              padding: '6px 12px',
              background: state.value === 'qr_display' ? '#4af' : '#333',
              color: state.value === 'qr_display' ? '#000' : '#666',
              border: 'none',
              borderRadius: '4px',
              cursor: state.value === 'qr_display' ? 'pointer' : 'not-allowed',
              fontWeight: 'bold',
              fontSize: '11px'
            }}
          >
            📱 Mock App Ready {state.value === 'qr_display' && '(Click Me!)'}
          </button>

          <div style={{ borderLeft: '1px solid rgba(255,255,255,0.2)', height: '100%', margin: '0 4px' }} />

          {/* Scenario Buttons */}
          {TEST_SCENARIOS.map(scenario => (
            <button
              key={scenario.name}
              onClick={() => runScenario(scenario)}
              disabled={runningScenario !== null}
              title={scenario.description}
              style={{
                padding: '6px 12px',
                background: runningScenario === scenario.name ? '#fa0' : '#667eea',
                color: '#fff',
                border: 'none',
                borderRadius: '4px',
                cursor: runningScenario ? 'not-allowed' : 'pointer',
                fontSize: '11px',
                opacity: runningScenario && runningScenario !== scenario.name ? 0.5 : 1
              }}
            >
              {runningScenario === scenario.name && '⏳ '}
              {scenario.name}
            </button>
          ))}
        </div>

        {/* Third Row: Manual ToF Control */}
        <div style={{
          display: 'flex',
          gap: '8px',
          alignItems: 'center',
          fontSize: '11px'
        }}>
          <span style={{ opacity: 0.6 }}>ToF Distance:</span>
          <input
            type="range"
            min="100"
            max="1000"
            step="50"
            value={flowState.tofDistance}
            onChange={(e) => {
              const distance = parseInt(e.target.value)
              setFlowState(prev => ({ ...prev, tofDistance: distance }))
              triggerToF(distance)
            }}
            style={{ width: '200px' }}
          />
          <span style={{ 
            color: flowState.tofDistance < 450 ? '#4f4' : '#888',
            minWidth: '60px'
          }}>
            {flowState.tofDistance}mm
          </span>

          <div style={{ borderLeft: '1px solid rgba(255,255,255,0.2)', height: '20px', margin: '0 8px' }} />

          <span style={{ opacity: 0.6 }}>Timeout Tests:</span>
          <button
            onClick={() => addLog('⏱️ Testing 30s timeout...')}
            style={{
              padding: '4px 8px',
              background: '#555',
              color: '#fff',
              border: '1px solid #777',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '10px'
            }}
          >
            30s Stuck Test
          </button>
        </div>
      </div>

      {/* Bottom-Right: Live Logs
      <div style={{
        position: 'absolute',
        bottom: '20px',
        right: '20px',
        width: '400px',
        maxHeight: '300px',
        background: 'rgba(0, 0, 0, 0.85)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        borderRadius: '8px',
        padding: '12px',
        fontFamily: 'monospace',
        fontSize: '10px',
        color: '#fff',
        overflowY: 'auto',
        zIndex: 1000
      }}>
        <div style={{ 
          marginBottom: '8px', 
          paddingBottom: '8px', 
          borderBottom: '1px solid rgba(255,255,255,0.2)',
          fontWeight: 'bold',
          fontSize: '11px'
        }}>
          📋 Live Logs ({logs.length})
        </div>
        {logs.map((log, i) => (
          <div
            key={i}
            style={{
              marginBottom: '3px',
              color: log.includes('❌') ? '#f44' :
                     log.includes('✅') ? '#4f4' :
                     log.includes('📍') ? '#4af' : '#ccc'
            }}
          >
            {log}
          </div>
        ))}
        {logs.length === 0 && (
          <div style={{ opacity: 0.4 }}>Waiting for events...</div>
        )}
      </div> */}

      {/* Bottom-Left: Phase Timing Info */}
      <div style={{
        position: 'absolute',
        bottom: '20px',
        left: '20px',
        background: 'rgba(0, 0, 0, 0.85)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        borderRadius: '8px',
        padding: '12px',
        fontFamily: 'monospace',
        fontSize: '10px',
        color: '#fff',
        zIndex: 1000
      }}>
        <div style={{ 
          marginBottom: '8px', 
          fontWeight: 'bold',
          fontSize: '11px'
        }}>
          ⏱️ Expected Timings
        </div>
        <div style={{ opacity: 0.8, lineHeight: 1.6 }}>
          <div>TV Bars Exit: 1.23s</div>
          <div>Hello Human: 3s</div>
          <div>Scan Prompt: 1.5s</div>
          <div>Human Detect: 3.5s</div>
          <div>Processing: 3s min</div>
          <div>Complete/Error: 3s</div>
        </div>
        <div style={{ 
          marginTop: '8px',
          paddingTop: '8px',
          borderTop: '1px solid rgba(255,255,255,0.2)',
          fontSize: '9px',
          opacity: 0.6
        }}>
          Total Flow: ~15-20s
        </div>
      </div>

      {/* Scenario Running Indicator */}
      {runningScenario && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          background: 'rgba(255, 170, 0, 0.95)',
          padding: '20px 40px',
          borderRadius: '12px',
          fontSize: '18px',
          fontWeight: 'bold',
          color: '#000',
          zIndex: 2000,
          boxShadow: '0 8px 32px rgba(0,0,0,0.5)'
        }}>
          ⏳ Running: {runningScenario}
        </div>
      )}
    </div>
  )
}

