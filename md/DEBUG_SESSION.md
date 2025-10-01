# Debug Session - Preview Visibility Issue

## Current Status

✅ **Debug logging added** to track preview visibility
✅ **UI rebuilt and restarted** (http://localhost:3000)
❌ **Controller needs manual start** (ToF sensor issue)

## What Was Fixed

The `StageRouter.tsx` already had the correct logic to return `null` during camera phases, but we've added comprehensive debug logging to trace the exact flow.

## Debug Logging Added

### 1. App.tsx (line 176-180)
```typescript
console.log('🎥 [APP PREVIEW] Phase:', state.value, '| Should show:', shouldShow, '| Phases:', Array.from(previewVisiblePhases))
```

### 2. PreviewSurface.tsx (lines 214, 224, 234, 242)
```typescript
console.log('📹 [PREVIEW SURFACE] Rendered | visible:', visible)
console.log('📹 [PREVIEW EFFECT] useEffect triggered | visible:', visible)
console.log('📹 [PREVIEW EFFECT] Not visible - clearing canvas')
console.log('📹 [PREVIEW EFFECT] Visible - starting segmentation')
```

### 3. StageRouter.tsx (lines 16, 19, 24, 29, 57)
```typescript
console.log('🎬 [STAGE ROUTER] Rendering | Phase:', currentPhase)
console.log('🎬 [STAGE ROUTER] → Rendering ErrorOverlay')
console.log('🎬 [STAGE ROUTER] → Rendering IdleScreen')
console.log('🎬 [STAGE ROUTER] → Rendering QR/Waiting phase')
console.log('🎬 [STAGE ROUTER] → Camera phase - rendering NULL (preview should be visible)')
```

## How to Start Services

### Start Controller (Manual)
```bash
cd /home/ichiro/Desktop/mercleapp/mDai/mdaitest
source controller/.venv/bin/activate
cd controller
uvicorn app.main:app --host 0.0.0.0 --port 5000 --log-config /dev/null
```

### UI is Already Running
- URL: http://localhost:3000
- Dev server running in background

## Test Flow

1. **Trigger Session** (bypasses physical ToF):
```bash
curl --location 'http://localhost:5000/debug/trigger' --header 'Content-Type: application/json' --data '{}'
```

2. **Watch Browser Console** - Open DevTools and watch for debug logs with emojis:
   - 🎥 [APP PREVIEW] - Shows when preview visibility changes
   - 📹 [PREVIEW SURFACE] - Shows preview component state
   - 🎬 [STAGE ROUTER] - Shows what's being rendered

3. **Scan QR Code** with your mobile app

4. **Simulate App Ready** (if needed):
```bash
curl --location 'http://localhost:5000/debug/app-ready' \
  --header 'Content-Type: application/json' \
  --data '{"platform_id": "TEST123"}'
```

5. **Watch the console** during `human_detect` and `stabilizing` phases

## Expected Console Output During Camera Phases

```
🎥 [APP PREVIEW] Phase: human_detect | Should show: true | Phases: [...]
🎬 [STAGE ROUTER] Rendering | Phase: human_detect
🎬 [STAGE ROUTER] → Camera phase - rendering NULL (preview should be visible)
📹 [PREVIEW SURFACE] Rendered | visible: true
📹 [PREVIEW EFFECT] useEffect triggered | visible: true
📹 [PREVIEW EFFECT] Visible - starting segmentation and frame processing
```

## What to Look For

1. **Phase transitions** - Does `Phase:` change to `human_detect`?
2. **Preview visibility** - Does `Should show:` become `true`?
3. **StageRouter behavior** - Does it render NULL or something else?
4. **PreviewSurface state** - Does `visible` prop become `true`?

## Common Issues to Debug

### Issue 1: Preview stays false
- Check `previewVisiblePhases` in config includes the current phase
- Look for: `🎥 [APP PREVIEW] ... | Should show: false` when it should be true

### Issue 2: StageRouter renders overlay instead of null
- Look for: `🎬 [STAGE ROUTER] → Rendering InstructionStage` during camera phases
- Should see: `🎬 [STAGE ROUTER] → Camera phase - rendering NULL`

### Issue 3: Preview element not visible in DOM
- Check CSS z-index conflicts
- Use browser DevTools Elements tab to find `.preview-surface`
- Check if `opacity: 1` and `z-index: 1`

## Configuration

### Preview Visible Phases (src/config/index.ts line 136):
```typescript
previewVisiblePhases: new Set<SessionPhase>(['human_detect', 'stabilizing', 'uploading', 'waiting_ack'])
```

### Z-Index Layers:
- `.preview-surface`: z-index: 1
- `.idle-screen`, `.overlay`: z-index: 2
- `.phase-controls`: z-index: 3

