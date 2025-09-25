#!/usr/bin/env node
import { spawn } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const logDir = '/workspace/mdaitest/logs'
mkdirSync(logDir, { recursive: true })
const logPath = join(logDir, 'ui-dev.log')

const tee = spawn('tee', [logPath], { stdio: ['pipe', process.stdout, process.stderr] })
const dev = spawn('npm', ['run', 'dev', '--', '--host', '0.0.0.0', '--port', '3100'], {
  cwd: '/workspace/mdaitest/mdai-ui',
  stdio: ['ignore', 'pipe', 'pipe'],
  env: process.env
})

dev.stdout.pipe(tee.stdin)
dev.stderr.pipe(tee.stdin)

dev.on('exit', (code) => {
  console.log(`\nUI dev server exited with code ${code}`)
  tee.stdin.end()
})
