import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import DebugPreview from './components/DebugPreview'
import DebugScreenGallery from './components/DebugScreenGallery'
import DebugFlowController from './components/DebugFlowController'
import './styles/index.css'

const AppRouter = () => {
  const path = window.location.pathname
  
  console.log('🔧 [APP ROUTER] Path:', path)
  
  // Debug routes
  if (path === '/debug-preview') {
    console.log('🔧 [APP ROUTER] Rendering DebugPreview')
    return <DebugPreview />
  }
  
  if (path === '/debug/flow') {
    console.log('🔧 [APP ROUTER] Rendering DebugFlowController')
    return <DebugFlowController />
  }
  
  if (path === '/debug' || path === '/debug/') {
    console.log('🔧 [APP ROUTER] Rendering DebugScreenGallery')
    return <DebugScreenGallery />
  }
  
  // Main app
  console.log('🔧 [APP ROUTER] Rendering Main App')
  return <App />
}

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <AppRouter />
  </React.StrictMode>
)