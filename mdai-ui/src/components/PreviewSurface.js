import { jsx as _jsx, Fragment as _Fragment, jsxs as _jsxs } from "react/jsx-runtime";
import { useEffect, useRef } from 'react';
import { SelfieSegmentation } from '@mediapipe/selfie_segmentation';
const DEFAULT_TITLE = 'Camera preview';
const DEFAULT_BLOCK_SIZE = 24; // Increased from 20 for better performance (fewer tiles)
const KEEP_THRESHOLD = 0.50; // Reduced from 0.55 for more permissive masking
const LOCATE_FILE_BASE = 'https://cdn.jsdelivr.net/npm/@mediapipe/selfie_segmentation/';
function getCanvasImageSourceDimensions(source) {
    if ('videoWidth' in source && 'videoHeight' in source) {
        return {
            width: source.videoWidth,
            height: source.videoHeight
        };
    }
    if ('naturalWidth' in source && 'naturalHeight' in source) {
        return {
            width: source.naturalWidth,
            height: source.naturalHeight
        };
    }
    if ('width' in source && 'height' in source) {
        const maybeCanvas = source;
        if (typeof maybeCanvas.width === 'number' && typeof maybeCanvas.height === 'number') {
            return {
                width: maybeCanvas.width,
                height: maybeCanvas.height
            };
        }
    }
    return { width: 0, height: 0 };
}
function ensureCanvasBundle(ref) {
    if (ref.current) {
        return ref.current;
    }
    const mask = document.createElement('canvas');
    const maskCtx = mask.getContext('2d', { willReadFrequently: true });
    const frame = document.createElement('canvas');
    const frameCtx = frame.getContext('2d');
    const downsample = document.createElement('canvas');
    const downsampleCtx = downsample.getContext('2d');
    const pixel = document.createElement('canvas');
    const pixelCtx = pixel.getContext('2d');
    if (!maskCtx || !frameCtx || !downsampleCtx || !pixelCtx) {
        return null;
    }
    pixelCtx.imageSmoothingEnabled = false;
    ref.current = {
        mask,
        maskCtx,
        frame,
        frameCtx,
        downsample,
        downsampleCtx,
        pixel,
        pixelCtx
    };
    return ref.current;
}
function renderTileSnappedPixelation(results, outputCanvas, blockSize, keepThreshold, bundle) {
    const maskSize = getCanvasImageSourceDimensions(results.segmentationMask);
    let { width, height } = maskSize;
    if (width === 0 || height === 0) {
        const fallbackSize = getCanvasImageSourceDimensions(results.image);
        width = fallbackSize.width;
        height = fallbackSize.height;
    }
    if (width === 0 || height === 0) {
        return;
    }
    outputCanvas.width = width;
    outputCanvas.height = height;
    const columns = Math.floor(width / blockSize);
    const rows = Math.floor(height / blockSize);
    if (columns === 0 || rows === 0) {
        const ctx = outputCanvas.getContext('2d');
        if (ctx) {
            ctx.clearRect(0, 0, width, height);
            ctx.drawImage(results.image, 0, 0, width, height);
        }
        return;
    }
    const useWidth = columns * blockSize;
    const useHeight = rows * blockSize;
    const { mask, maskCtx, frame, frameCtx, downsample, downsampleCtx, pixel, pixelCtx } = bundle;
    mask.width = width;
    mask.height = height;
    frame.width = width;
    frame.height = height;
    downsample.width = columns;
    downsample.height = rows;
    pixel.width = useWidth;
    pixel.height = useHeight;
    maskCtx.clearRect(0, 0, width, height);
    maskCtx.drawImage(results.segmentationMask, 0, 0, width, height);
    frameCtx.clearRect(0, 0, width, height);
    frameCtx.drawImage(results.image, 0, 0, width, height);
    downsampleCtx.imageSmoothingEnabled = false; // Faster rendering
    downsampleCtx.clearRect(0, 0, columns, rows);
    downsampleCtx.drawImage(frame, 0, 0, useWidth, useHeight, 0, 0, columns, rows);
    pixelCtx.imageSmoothingEnabled = false;
    pixelCtx.clearRect(0, 0, useWidth, useHeight);
    pixelCtx.drawImage(downsample, 0, 0, columns, rows, 0, 0, useWidth, useHeight);
    const outputCtx = outputCanvas.getContext('2d');
    if (!outputCtx) {
        return;
    }
    outputCtx.fillStyle = '#000';
    outputCtx.fillRect(0, 0, width, height);
    const maskData = maskCtx.getImageData(0, 0, useWidth, useHeight).data;
    const tilePixelCount = blockSize * blockSize;
    const threshold = keepThreshold * 255 * tilePixelCount;
    for (let tileY = 0; tileY < rows; tileY += 1) {
        const baseY = tileY * blockSize;
        for (let tileX = 0; tileX < columns; tileX += 1) {
            const baseX = tileX * blockSize;
            let sum = 0;
            for (let y = 0; y < blockSize; y += 1) {
                let index = ((baseY + y) * useWidth + baseX) * 4;
                for (let x = 0; x < blockSize; x += 1) {
                    sum += maskData[index];
                    index += 4;
                }
            }
            if (sum >= threshold) {
                outputCtx.drawImage(pixel, baseX, baseY, blockSize, blockSize, baseX, baseY, blockSize, blockSize);
            }
        }
    }
}
const TARGET_FPS = 15; // Throttle to 15 FPS to match camera and reduce CPU
const FRAME_INTERVAL_MS = 1000 / TARGET_FPS;
export default function PreviewSurface({ visible, previewUrl, title = DEFAULT_TITLE }) {
    const canvasRef = useRef(null);
    const imageRef = useRef(null);
    const animationFrameRef = useRef(null);
    const processingRef = useRef(false);
    const offscreenRef = useRef(null);
    const lastFrameTimeRef = useRef(0);
    useEffect(() => {
        const canvasEl = canvasRef.current;
        const imageEl = imageRef.current;
        if (!canvasEl || !imageEl) {
            return () => { };
        }
        if (!visible) {
            const ctx = canvasEl.getContext('2d');
            if (ctx) {
                ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
            }
            return () => { };
        }
        const bundle = ensureCanvasBundle(offscreenRef);
        if (!bundle) {
            return () => { };
        }
        const segmentation = new SelfieSegmentation({
            locateFile: (file) => `${LOCATE_FILE_BASE}${file}`
        });
        segmentation.setOptions({
            modelSelection: 0, // Use faster general model (was 1 = landscape)
            selfieMode: false // Disable selfie mode for better performance
        });
        let isActive = true;
        segmentation.onResults((results) => {
            if (!isActive) {
                return;
            }
            renderTileSnappedPixelation(results, canvasEl, DEFAULT_BLOCK_SIZE, KEEP_THRESHOLD, bundle);
        });
        const scheduleNext = () => {
            if (!isActive) {
                return;
            }
            animationFrameRef.current = window.requestAnimationFrame(() => {
                void processFrame();
            });
        };
        const processFrame = async () => {
            if (!isActive) {
                return;
            }
            // Throttle to target FPS
            const now = performance.now();
            const timeSinceLastFrame = now - lastFrameTimeRef.current;
            if (timeSinceLastFrame < FRAME_INTERVAL_MS) {
                // Too soon, schedule for later
                setTimeout(scheduleNext, FRAME_INTERVAL_MS - timeSinceLastFrame);
                return;
            }
            if (!imageEl.complete || imageEl.naturalWidth === 0 || imageEl.naturalHeight === 0) {
                scheduleNext();
                return;
            }
            if (processingRef.current) {
                // Skip this frame if still processing previous one
                scheduleNext();
                return;
            }
            lastFrameTimeRef.current = now;
            processingRef.current = true;
            try {
                await segmentation.send({ image: imageEl });
            }
            catch (error) {
                console.error('PreviewSurface: segmentation failed', error);
                isActive = false;
                // Fallback: show raw image without segmentation
                if (imageEl.naturalWidth > 0 && imageEl.naturalHeight > 0) {
                    canvasEl.width = imageEl.naturalWidth;
                    canvasEl.height = imageEl.naturalHeight;
                }
                const fallbackCtx = canvasEl.getContext('2d');
                if (fallbackCtx) {
                    fallbackCtx.clearRect(0, 0, canvasEl.width, canvasEl.height);
                    fallbackCtx.drawImage(imageEl, 0, 0, canvasEl.width, canvasEl.height);
                }
            }
            finally {
                processingRef.current = false;
                if (isActive) {
                    scheduleNext();
                }
            }
        };
        scheduleNext();
        return () => {
            isActive = false;
            if (animationFrameRef.current !== null) {
                cancelAnimationFrame(animationFrameRef.current);
                animationFrameRef.current = null;
            }
            processingRef.current = false;
            void segmentation.close().catch((error) => {
                console.error('PreviewSurface: failed to close segmentation', error);
            });
        };
    }, [previewUrl, visible]);
    const classNames = [
        'preview-surface',
        visible ? 'visible' : 'hidden'
    ];
    return (_jsx("div", { className: classNames.join(' '), "data-preview-surface": true, children: visible ? (_jsxs(_Fragment, { children: [_jsx("canvas", { ref: canvasRef, className: "preview-surface__media preview-surface__canvas", title: title, "aria-label": title }), _jsx("img", { ref: imageRef, className: "preview-surface__source", src: previewUrl, crossOrigin: "anonymous", alt: "" })] })) : null }));
}
