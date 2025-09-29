import { jsx as _jsx } from "react/jsx-runtime";
const DEFAULT_TITLE = 'Camera preview';
export default function PreviewSurface({ visible, previewUrl, title = DEFAULT_TITLE }) {
    const classNames = [
        'preview-surface',
        visible ? 'visible' : 'hidden'
    ];
    return (_jsx("div", { className: classNames.join(' '), "data-preview-surface": true, children: visible ? (_jsx("iframe", { title: title, className: "preview-surface__media preview-surface__iframe", src: previewUrl, allow: "autoplay" })) : null }));
}
