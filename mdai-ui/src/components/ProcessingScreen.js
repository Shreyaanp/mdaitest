import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef } from 'react';
const DEFAULT_IMAGE_SRC = '/hero/test1.gif';
const DEFAULT_STATUS = ['processing scan', "hold steady"];
const DEFAULT_GUIDANCE = ['align your face with the frame', 'remove hats or glasses', 'keep your gaze forward'];
const DEFAULT_DURATION = 3000;
export default function ProcessingScreen({ imageSrc = DEFAULT_IMAGE_SRC, imageAlt = 'Processing animation', durationMs = DEFAULT_DURATION, onComplete, statusLines = DEFAULT_STATUS, guidanceLines = DEFAULT_GUIDANCE }) {
    const callbackRef = useRef(onComplete);
    useEffect(() => {
        callbackRef.current = onComplete;
    }, [onComplete]);
    useEffect(() => {
        if (!callbackRef.current) {
            return;
        }
        const timer = window.setTimeout(() => {
            callbackRef.current?.();
        }, durationMs);
        return () => {
            window.clearTimeout(timer);
        };
    }, [durationMs]);
    return (
        _jsxs("main", { className: "processing-screen", "data-processing-screen": true, children: [
            _jsx("div", { className: "processing-screen__status", children: statusLines.map((line) => (_jsx("span", { children: line }, line))) }),    
            _jsx("img", { className: "processing-screen__hero", src: imageSrc, alt: imageAlt })
        
        
        ] 
        
        })
        
        
        );
}
