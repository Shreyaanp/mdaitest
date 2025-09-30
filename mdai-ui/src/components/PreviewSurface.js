import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useRef } from 'react';
const DEFAULT_TITLE = 'Camera Preview';
export default function PreviewSurface({ visible, previewUrl, title = DEFAULT_TITLE }) {
    console.log('📹 [PREVIEW SURFACE] Rendered | visible:', visible, '| previewUrl:', previewUrl);
    const imageRef = useRef(null);
    useEffect(() => {
        console.log('📹 [PREVIEW EFFECT] useEffect triggered | visible:', visible);
        const imageEl = imageRef.current;
        if (!imageEl) {
            console.log('📹 [PREVIEW EFFECT] No image element');
            return () => { };
        }
        if (!visible) {
            console.log('📹 [PREVIEW EFFECT] Not visible - clearing src');
            imageEl.src = '';
            return () => { };
        }
        console.log('📹 [PREVIEW EFFECT] Visible - setting MJPEG stream URL:', previewUrl);
        // Add timestamp to prevent caching
        const streamUrl = `${previewUrl}?t=${Date.now()}`;
        imageEl.src = streamUrl;
        imageEl.onerror = (e) => {
            console.error('📹 [PREVIEW EFFECT] Image load error:', e);
        };
        imageEl.onload = () => {
            console.log('📹 [PREVIEW EFFECT] Image loaded successfully');
        };
        return () => {
            if (imageEl) {
                imageEl.src = '';
                imageEl.onerror = null;
                imageEl.onload = null;
            }
        };
    }, [previewUrl, visible]);
    const classNames = [
        'preview-surface',
        visible ? 'visible' : 'hidden'
    ];
    return (_jsx("div", { className: classNames.join(' '), "data-preview-surface": true, children: _jsx("img", { ref: imageRef, className: "preview-surface__img preview-surface__media", alt: title, style: {
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                display: 'block',
                backgroundColor: '#000'
            } }) }));
}
