import { jsx as _jsx } from "react/jsx-runtime";
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import DebugPreview from './components/DebugPreview';
import DebugScreenGallery from './components/DebugScreenGallery';
import './styles/index.css';
const AppRouter = () => {
    const path = window.location.pathname;
    console.log('🔧 [APP ROUTER] Path:', path);
    // Debug routes
    if (path === '/debug-preview') {
        console.log('🔧 [APP ROUTER] Rendering DebugPreview');
        return _jsx(DebugPreview, {});
    }
    if (path === '/debug' || path === '/debug/') {
        console.log('🔧 [APP ROUTER] Rendering DebugScreenGallery');
        return _jsx(DebugScreenGallery, {});
    }
    // Main app
    console.log('🔧 [APP ROUTER] Rendering Main App');
    return _jsx(App, {});
};
ReactDOM.createRoot(document.getElementById('root')).render(_jsx(React.StrictMode, { children: _jsx(AppRouter, {}) }));
