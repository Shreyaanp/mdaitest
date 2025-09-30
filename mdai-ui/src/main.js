import { jsx as _jsx } from "react/jsx-runtime";
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import DebugPreview from './components/DebugPreview';
import './styles/index.css';
const AppRouter = () => {
    const path = window.location.pathname;
    if (path === '/debug-preview') {
        return _jsx(DebugPreview, {});
    }
    return _jsx(App, {});
};
ReactDOM.createRoot(document.getElementById('root')).render(_jsx(React.StrictMode, { children: _jsx(AppRouter, {}) }));
