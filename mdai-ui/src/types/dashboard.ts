export interface MetricsSnapshot {
  stability?: number
  focus?: number
  composite?: number
  instantAlive?: boolean
  stableAlive?: boolean
}

export type LogLevel = 'info' | 'error'

export interface LogEntry {
  id: string
  ts: number
  message: string
  level: LogLevel
}
