import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import DebugPreview from './components/DebugPreview'
import DebugScreenGallery from './components/DebugScreenGallery'
import DebugFlowController from './components/DebugFlowController'
import CRTWrapperEffect from './components/CRTWrapperEffect'
import { frontendConfig } from './config'
import './styles/index.css'

const AppRouter = () => {
  const path = window.location.pathname
  const crtSettings = frontendConfig.crtSettings
  
  console.log('🔧 [APP ROUTER] Path:', path)
  
  // Debug routes - wrapped with CRT effect
  if (path === '/debug-preview') {
    console.log('🔧 [APP ROUTER] Rendering DebugPreview')
    return (
      <CRTWrapperEffect
        enabled={crtSettings.enabled}
        curvature={crtSettings.curvature}
        vignette={crtSettings.vignette}
        scanline={crtSettings.scanline}
        bloom={crtSettings.bloom}
        chromAberr={crtSettings.chromAberr}
      >
        <DebugPreview />
      </CRTWrapperEffect>
    )
  }
  
  if (path === '/debug/flow') {
    console.log('🔧 [APP ROUTER] Rendering DebugFlowController')
    return (
      <CRTWrapperEffect
        enabled={crtSettings.enabled}
        curvature={crtSettings.curvature}
        vignette={crtSettings.vignette}
        scanline={crtSettings.scanline}
        bloom={crtSettings.bloom}
        chromAberr={crtSettings.chromAberr}
      >
        <DebugFlowController />
      </CRTWrapperEffect>
    )
  }
  
  if (path === '/debug' || path === '/debug/') {
    console.log('🔧 [APP ROUTER] Rendering DebugScreenGallery')
    return (
      <CRTWrapperEffect
        enabled={crtSettings.enabled}
        curvature={crtSettings.curvature}
        vignette={crtSettings.vignette}
        scanline={crtSettings.scanline}
        bloom={crtSettings.bloom}
        chromAberr={crtSettings.chromAberr}
      >
        <DebugScreenGallery />
      </CRTWrapperEffect>
    )
  }
  
  // Main app - already wrapped in App.tsx
  console.log('🔧 [APP ROUTER] Rendering Main App')
  return <App />
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <AppRouter />
  </React.StrictMode>
)