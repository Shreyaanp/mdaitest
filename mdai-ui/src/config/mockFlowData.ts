/**
 * Single Source of Truth for Mock Flow Testing
 * All debug scenarios and mock data defined here
 */

export interface MockFlowConfig {
  tof: {
    triggerDistance: number  // mm - distance to trigger session
    idleDistance: number     // mm - distance to return to idle
    debounceMs: number       // ms - how long to wait before trigger
  }
  qr: {
    token: string
    platform_id: string
    ws_app_url: string
    ws_hardware_url: string
    server_host: string
  }
  camera: {
    source: 'realsense' | 'webcam' | 'mock'
    eyeTracking: boolean
  }
  validation: {
    durationMs: number
    minPassingFrames: number
  }
  timeouts: {
    qrWaitMs: number        // How long to wait for app connection
    processingMaxMs: number // Max processing time
    errorDisplayMs: number  // How long to show error
    completeDisplayMs: number // How long to show success
  }
}

export const DEFAULT_MOCK_CONFIG: MockFlowConfig = {
  tof: {
    triggerDistance: 450,  // Within 500mm threshold
    idleDistance: 1000,    // Well beyond 500mm threshold
    debounceMs: 1500       // Matches backend config
  },
  qr: {
    token: 'DEBUG_TOKEN_ABC123XYZ789',
    platform_id: 'test-device-mock-123',
    ws_app_url: 'ws://localhost:3001/ws/app',
    ws_hardware_url: 'ws://localhost:5000/ws/hardware',
    server_host: 'localhost:3000'
  },
  camera: {
    source: 'webcam',
    eyeTracking: true
  },
  validation: {
    durationMs: 3500,
    minPassingFrames: 10
  },
  timeouts: {
    qrWaitMs: 300000,      // 5 minutes
    processingMaxMs: 15000, // 15 seconds
    errorDisplayMs: 3000,   // 3 seconds
    completeDisplayMs: 3000 // 3 seconds
  }
}

/**
 * Test Scenarios - Automated flows for different cases
 */
export interface TestScenario {
  name: string
  description: string
  steps: ScenarioStep[]
}

export interface ScenarioStep {
  action: 'trigger_tof' | 'mock_app_ready' | 'wait' | 'check_phase'
  params?: Record<string, any>
  delayMs?: number
}

export const TEST_SCENARIOS: TestScenario[] = [
  {
    name: 'Happy Path',
    description: 'Complete successful flow from start to finish',
    steps: [
      { action: 'trigger_tof', params: { distance_mm: 450 } },
      { action: 'wait', delayMs: 7000 }, // Wait for hello_human + scan_prompt
      { action: 'mock_app_ready', params: { platform_id: 'test-123' } },
      { action: 'wait', delayMs: 3500 }, // Wait for validation
      { action: 'check_phase', params: { expected: 'processing' } }
    ]
  },
  {
    name: 'No Face Error',
    description: 'User has no face detected during validation',
    steps: [
      { action: 'trigger_tof', params: { distance_mm: 450 } },
      { action: 'wait', delayMs: 7000 },
      { action: 'mock_app_ready', params: { platform_id: 'test-no-face', simulate_no_face: true } },
      { action: 'wait', delayMs: 4000 },
      { action: 'check_phase', params: { expected: 'error' } }
    ]
  },
  {
    name: 'Lost Tracking',
    description: 'Face detected briefly then lost',
    steps: [
      { action: 'trigger_tof', params: { distance_mm: 450 } },
      { action: 'wait', delayMs: 7000 },
      { action: 'mock_app_ready', params: { platform_id: 'test-lost', simulate_lost_tracking: true } },
      { action: 'wait', delayMs: 4000 },
      { action: 'check_phase', params: { expected: 'error' } }
    ]
  },
  {
    name: 'User Walks Away',
    description: 'ToF > 500mm for 1.5s during flow',
    steps: [
      { action: 'trigger_tof', params: { distance_mm: 450 } },
      { action: 'wait', delayMs: 3000 },
      { action: 'trigger_tof', params: { distance_mm: 1000, duration_ms: 1600 } },
      { action: 'check_phase', params: { expected: 'idle' } }
    ]
  },
  {
    name: 'QR Data Delay',
    description: 'QR data takes time - shows fallback screen for 1.8s minimum',
    steps: [
      { action: 'trigger_tof', params: { distance_mm: 450 } },
      { action: 'wait', delayMs: 5500 }, // Wait for pairing + hello + scan
      // QR phase will show "Loading" fallback
      { action: 'wait', delayMs: 2000 }, // Fallback should stay minimum 1.8s
      { action: 'check_phase', params: { expected: 'qr_display' } }
    ]
  },
  {
    name: 'Backend Timeout',
    description: 'Backend processing takes too long (3s timeout)',
    steps: [
      { action: 'trigger_tof', params: { distance_mm: 450 } },
      { action: 'wait', delayMs: 7000 },
      { action: 'mock_app_ready', params: { platform_id: 'test-timeout' } },
      { action: 'wait', delayMs: 7000 }, // 3.5s validation + 3s processing
      { action: 'check_phase', params: { expected: 'complete' } }
    ]
  }
]

/**
 * Phase timing expectations for validation
 */
export const PHASE_TIMINGS = {
  idle: 'indefinite',
  pairing_request: 1230,      // TV bars exit
  hello_human: 3000,
  scan_prompt: 1500,
  qr_display: 'indefinite',
  human_detect: 3500,
  processing: 3000,           // minimum
  complete: 3000,
  error: 3000
}

