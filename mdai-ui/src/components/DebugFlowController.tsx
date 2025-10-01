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
  tofLive: number | null  // Live ToF reading from sensor
  cameraSource: 'realsense' | 'webcam' | 'mock'
  cameraActive: boolean
  eyeTrackingMode: boolean
  faceDetected: boolean
  validationProgress: number
  frameCount: number
  realsenseEnabled: boolean
}

export default function DebugFlowController() {
  // Use actual session machine (same as production App)
  const [state, send] = useMachine(sessionMachine)
  
  const [config, setConfig] = useState<MockFlowConfig>(DEFAULT_MOCK_CONFIG)
  const [flowState, setFlowState] = useState<FlowState>({
    phase: 'idle',
    tofDistance: 1000,  // Default to idle distance (beyond 500mm threshold)
    tofLive: null,  // Live ToF reading
    cameraSource: 'realsense',  // Production default
    cameraActive: false,
    eyeTrackingMode: true,
    faceDetected: false,
    validationProgress: 0,
    frameCount: 0,
    realsenseEnabled: false
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
        // Fetch initial state and configuration from backend
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
        
        // Get initial performance data to detect camera mode
        const perfResponse = await fetch('http://localhost:5000/debug/performance')
        if (perfResponse.ok) {
          const perfData = await perfResponse.json()
          const detectedSource = perfData.camera_source || (perfData.realsense_enabled ? 'realsense' : 'webcam')
          setFlowState(prev => ({ 
            ...prev, 
            cameraSource: detectedSource,
            realsenseEnabled: perfData.realsense_enabled || false
          }))
          addLog(`📷 Detected camera: ${detectedSource} (RealSense: ${perfData.realsense_enabled ? 'Yes' : 'No'})`)
        }

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
    
    // Start CPU/Memory/ToF monitoring (real-time)
    performanceInterval.current = setInterval(async () => {
      try {
        const response = await fetch('http://localhost:5000/debug/performance')
        if (response.ok) {
          const data = await response.json()
          setCpuUsage(data.cpu_percent || 0)
          setMemoryUsage(data.memory_percent || 0)
          
          // Update live ToF feed and camera info
          setFlowState(prev => ({
            ...prev,
            tofLive: data.tof_distance_mm,
            realsenseEnabled: data.realsense_enabled || false
          }))
        }
      } catch (e) {
        console.error('Performance monitoring error:', e)
      }
    }, 500)  // Update every 0.5s for responsive ToF display

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
        addLog(`📏 ToF: ${distance_mm}mm (waiting ${config.tof.debounceMs}ms to trigger...)`)
        
        // Wait configured debounce time before actually triggering
        tofDebounceTimer.current = setTimeout(async () => {
          const response = await fetch('http://localhost:5000/debug/mock-tof', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ triggered, distance_mm })
          })
          if (response.ok) {
            addLog(`📏 ToF: ${distance_mm}mm ${triggered ? '✓ TRIGGERED' : '✓ idle'}`)
          }
        }, config.tof.debounceMs)
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
    await triggerToF(1000, true)  // Immediate trigger with idle distance
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
            <span style={{ opacity: 0.6 }}>ToF Manual:</span>{' '}
            <span style={{ color: flowState.tofDistance <= 500 ? '#4f4' : '#888', fontWeight: 'bold' }}>
              {flowState.tofDistance}mm
            </span>
          </div>
          {flowState.tofLive !== null && (
            <div>
              <span style={{ opacity: 0.6 }}>ToF Live:</span>{' '}
              <span style={{ 
                color: flowState.tofLive <= 500 ? '#0f0' : '#888',
                fontWeight: 'bold',
                animation: 'pulse 1s infinite'
              }}>
                {flowState.tofLive}mm
              </span>
              <span style={{ fontSize: '10px', marginLeft: '4px', opacity: 0.5 }}>
                (sensor reading)
              </span>
            </div>
          )}
          <div>
            <span style={{ opacity: 0.6 }}>Camera:</span>{' '}
            <span style={{ 
              color: flowState.realsenseEnabled ? '#4af' : '#fa0',
              fontWeight: 'bold'
            }}>
              {flowState.realsenseEnabled ? 'RealSense D435i' : 'Webcam (Test)'}
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
            ▶ Start Flow (ToF ≤ 500mm)
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
          fontSize: '11px',
          background: 'rgba(255, 255, 255, 0.05)',
          padding: '8px 12px',
          borderRadius: '4px',
          border: '1px solid rgba(255, 255, 255, 0.1)'
        }}>
          <span style={{ opacity: 0.8, fontWeight: 'bold' }}>🎮 Manual ToF Control:</span>
          <input
            type="range"
            min="100"
            max="1500"
            step="50"
            value={flowState.tofDistance}
            onChange={(e) => {
              const distance = parseInt(e.target.value)
              triggerToF(distance, false)  // Use debounced trigger for slider
            }}
            style={{ width: '300px' }}
          />
          <span style={{ 
            color: flowState.tofDistance <= 500 ? '#4f4' : '#f44',
            minWidth: '90px',
            fontWeight: 'bold',
            fontSize: '13px'
          }}>
            {flowState.tofDistance}mm
          </span>
          <span style={{ 
            background: flowState.tofDistance <= 500 ? 'rgba(0,255,0,0.2)' : 'rgba(255,68,68,0.2)',
            padding: '2px 8px',
            borderRadius: '3px',
            fontSize: '10px',
            fontWeight: 'bold'
          }}>
            {flowState.tofDistance <= 500 ? '✓ TRIGGER' : 'IDLE'}
          </span>
          <span style={{ opacity: 0.5, fontSize: '10px' }}>
            (moves after 1.5s)
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

