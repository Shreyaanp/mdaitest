import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect } from 'react';
const DEFAULT_TITLE = 'Camera Preview';
export default function PreviewSurface({ visible, previewUrl, title = DEFAULT_TITLE }) {
    console.log('📹 [PREVIEW SURFACE] Rendered | visible:', visible, '| previewUrl:', previewUrl);
    // Placeholder surface; backend /preview stream is not used
    useEffect(() => {
        console.log('📹 [PREVIEW EFFECT] Placeholder active | visible:', visible);
    }, [visible]);
    const classNames = [
        'preview-surface',
        visible ? 'visible' : 'hidden'
    ];
    return (_jsx("div", { className: classNames.join(' '), "data-preview-surface": true, children: _jsx("div", { children: [
                _jsx("div", { className: "preview-surface__status", "aria-live": "polite", children: "Scanning…" }),
                _jsx("img", { className: "preview-surface__img preview-surface__media", src: "/hero/scan.gif", alt: title || 'Scanning placeholder', style: {
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        display: 'block',
                        backgroundColor: '#000'
                    } })
            ] }) }));
}
