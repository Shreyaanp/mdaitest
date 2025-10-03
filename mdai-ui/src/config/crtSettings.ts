/**
 * CRT Effect Configuration
 * 
 * Adjust these values to customize the CRT screen effect
 */

export interface CRTSettings {
  enabled: boolean
  curvature: number     // 0 → 0.15 (screen curvature/barrel distortion)
  vignette: number      // 0 → 2 (edge darkening)
  scanline: number      // 0 → 1 (horizontal scanline intensity)
  bloom: number         // 0 → 2 (glow/bloom effect)
  chromAberr: number    // 0 → 10 (chromatic aberration - color fringing)
}

/**
 * Default CRT settings - Adjust these to change the effect globally
 */
export const defaultCRTSettings: CRTSettings = {
  enabled: true,
  curvature: 0.01,      // Subtle screen curvature
  vignette: 1.0,        // Moderate edge darkening
  scanline: 0.8,        // Visible scanlines
  bloom: 0.2,           // Subtle glow
  chromAberr: 3.0       // Moderate color fringing
}

/**
 * Preset configurations for different CRT styles
 */
export const crtPresets = {
  none: {
    enabled: false,
    curvature: 0,
    vignette: 0,
    scanline: 0,
    bloom: 0,
    chromAberr: 0
  },
  
  subtle: {
    enabled: true,
    curvature: 0.005,
    vignette: 0.5,
    scanline: 0.4,
    bloom: 0.1,
    chromAberr: 1.0
  },
  
  classic: {
    enabled: true,
    curvature: 0.02,
    vignette: 1.0,
    scanline: 0.8,
    bloom: 0.3,
    chromAberr: 3.0
  },
  
  intense: {
    enabled: true,
    curvature: 0.05,
    vignette: 1.5,
    scanline: 1.0,
    bloom: 0.6,
    chromAberr: 5.0
  },
  
  retro: {
    enabled: true,
    curvature: 0.08,
    vignette: 2.0,
    scanline: 1.0,
    bloom: 0.8,
    chromAberr: 8.0
  }
} as const


