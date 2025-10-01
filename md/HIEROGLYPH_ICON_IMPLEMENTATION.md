# Hieroglyph Icon with Breathing Glow Effect

## Overview
Implemented an Egyptian hieroglyph (𓅽 - Swallow) with a white breathing glow effect on the `scan_prompt` phase.

## Implementation Details

### 1. **Component: HandjetMessage.tsx**
- Added optional `showIcon` prop (default: `false`)
- Created inline SVG component `HieroglyphIcon` rendering a simplified swallow hieroglyph
- SVG dimensions: 160x160px (optimized for 480x800 display)
- Icon includes: body, head, wings, tail feathers, eye, and beak

### 2. **CSS Animations: index.css**
```css
@keyframes glowBreath {
  0%   → Subtle glow (8px/16px drop-shadow, opacity 0.85)
  50%  → Peak glow (20px/32px/48px layered drop-shadow, opacity 1.0)
  100% → Back to subtle (same as 0%)
}
```

**Animation Settings:**
- Duration: 2.4 seconds
- Easing: ease-in-out
- Loop: infinite
- Performance: `will-change: filter, opacity` for GPU acceleration

### 3. **Integration: StageRouter.tsx**
- Updated `scan_prompt` phase to pass `showIcon={true}` to `HandjetMessage`
- Icon appears for 3 seconds during the "scan this to get started" message

### 4. **Layout**
- Vertical flex layout: Icon → Text
- Gap: 40px between icon and text
- Both centered on screen
- Black background (#000) for maximum contrast

## Technical Benefits

1. **Performance (Jetson Nano optimized)**
   - Inline SVG (no HTTP request)
   - GPU-accelerated animations
   - Minimal DOM nodes

2. **Maintainability**
   - Single component (`HandjetMessage`) handles both with/without icon
   - CSS-based animation (no JavaScript animation loop)
   - Auto-synced with debug gallery

3. **Visual Impact**
   - 3-layer drop-shadow for depth
   - Smooth breathing effect (2.4s cycle)
   - White-on-black creates strong visual anchor

## Usage

```tsx
// With icon
<HandjetMessage 
  lines={['scan this to', 'get started']}
  durationMs={3000}
  showIcon={true}
/>

// Without icon
<HandjetMessage 
  lines={['some other', 'message']}
  durationMs={2000}
/>
```

## Files Modified

1. `mdai-ui/src/components/HandjetMessage.tsx` - Added icon component and prop
2. `mdai-ui/src/components/StageRouter.tsx` - Enabled icon for scan_prompt
3. `mdai-ui/src/styles/index.css` - Added breathing glow animation

## Testing

- Build successful ✅
- No linter errors ✅
- Auto-synced with debug gallery ✅
- Visit `/debug` route to preview all phases including the new icon

## Future Enhancements (Optional)

- Add different hieroglyphs for other phases
- Make glow color customizable
- Add entrance/exit animations for the icon itself

