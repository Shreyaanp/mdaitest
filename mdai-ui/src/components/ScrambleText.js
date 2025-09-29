import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useState, useRef } from 'react';
const DEFAULT_SCRAMBLE_CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?';
export default function ScrambleText({ text, className = '', duration = 2000, scrambleChars = DEFAULT_SCRAMBLE_CHARS, onComplete }) {
    const [displayText, setDisplayText] = useState('');
    const [isAnimating, setIsAnimating] = useState(true);
    const intervalRef = useRef(null);
    const timeoutRef = useRef(null);
    useEffect(() => {
        if (!text)
            return;
        setIsAnimating(true);
        setDisplayText('');
        const totalSteps = Math.floor(duration / 50); // 50ms per frame
        const revealDelay = duration * 0.3; // Start revealing after 30% of duration
        let currentStep = 0;
        const animate = () => {
            const progress = currentStep / totalSteps;
            const revealProgress = Math.max(0, (progress - 0.3) / 0.7); // Reveal in last 70%
            const revealedLength = Math.floor(revealProgress * text.length);
            let newText = '';
            // Build the display text
            for (let i = 0; i < text.length; i++) {
                if (i < revealedLength) {
                    // Character is revealed
                    newText += text[i];
                }
                else if (text[i] === ' ') {
                    // Keep spaces as spaces
                    newText += ' ';
                }
                else {
                    // Show random character
                    const randomChar = scrambleChars[Math.floor(Math.random() * scrambleChars.length)];
                    newText += randomChar;
                }
            }
            setDisplayText(newText);
            currentStep++;
            if (currentStep >= totalSteps) {
                setDisplayText(text);
                setIsAnimating(false);
                onComplete?.();
                return;
            }
        };
        // Start animation
        intervalRef.current = window.setInterval(animate, 50);
        // Cleanup
        return () => {
            if (intervalRef.current) {
                window.clearInterval(intervalRef.current);
            }
            if (timeoutRef.current) {
                window.clearTimeout(timeoutRef.current);
            }
        };
    }, [text, duration, scrambleChars, onComplete]);
    return (_jsx("span", { className: `scramble-text ${isAnimating ? 'animating' : ''} ${className}`, children: displayText || text }));
}
