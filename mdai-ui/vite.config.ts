import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

function resolveEnv(mode: string) {
  const rawEnv = loadEnv(mode, process.cwd(), '')

  const resolved: Record<string, string> = {}

  const bridge = (target: string, candidates: string[]) => {
    if (rawEnv[target]) {
      return
    }

    for (const key of candidates) {
      const value = rawEnv[key]
      if (typeof value === 'string' && value.length > 0) {
        resolved[target] = value
        break
      }
    }
  }

  bridge('VITE_BACKEND_URL', ['VITE_BACKEND_API_URL', 'BACKEND_API_URL'])
  bridge('VITE_DEVICE_ID', ['DEVICE_ID'])
  bridge('VITE_DEVICE_ADDRESS', ['DEVICE_ADDRESS', 'EVM_ADDRESS'])
  bridge('VITE_BACKEND_WS_URL', ['BACKEND_WS_URL'])

  return Object.keys(resolved).reduce<Record<string, string>>((acc, key) => {
    acc[`import.meta.env.${key}`] = JSON.stringify(resolved[key])
    return acc
  }, {})
}

export default defineConfig(({ mode }) => ({
  plugins: [
    react({
      include: [/\.jsx?$/, /\.tsx?$/]
    })
  ],
  define: resolveEnv(mode),
  resolve: {
    extensions: ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.json']
  },
  optimizeDeps: {
    esbuildOptions: {
      loader: {
        '.js': 'jsx'
      }
    }
  },
  build: {
    rollupOptions: {
      output: {
        entryFileNames: `assets/[name].js`,
        chunkFileNames: `assets/[name].js`,
        assetFileNames: `assets/[name].[ext]`
      }
    }
  },
  server: {
    port: 3000,
    host: '0.0.0.0'
  }
}))
