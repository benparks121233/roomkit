// Shared illustration tokens — every piece imports these.
// Zero hardcoded colors or dimensions in individual pieces.

export const SCENE = {
  viewBox: { w: 800, h: 520 },
  wallY: 0,
  floorY: 312,
  baseboardY: 308,
  baseboardH: 8,
} as const;

export const STROKE = {
  width: 1.5,
  linecap: "round" as const,
  linejoin: "round" as const,
  color: "#C8C5BC", // --color-border-strong
} as const;

export const FILL = {
  wall: "#FAF8F5",       // --color-bg
  floor: "#F3F0EB",      // --color-surface-muted
  baseboard: "#E2DED6",  // --color-border
  surface: "#FFFFFF",    // --color-surface (sheets, mirror, canvas)
  warm1: "#F3F0EB",      // light taupe (mattress, dresser body)
  warm2: "#E2DED6",      // medium taupe (bed frame, nightstand)
  warm3: "#C8C5BC",      // dark taupe (lampshades, headboard accent)
  accent: "#1C1917",     // very sparingly (lamp wire, thin details)
  green: "#5E8C61",      // --color-success (plant leaves)
  greenLight: "#8DB98F", // lighter sage (secondary foliage)
  terracotta: "#C4A882", // pot color
} as const;

export const RADIUS = {
  sm: 4,
  md: 8,
  lg: 12,
} as const;

// Stroke props spread helper — use on every outlined shape
export const strokeProps = {
  stroke: STROKE.color,
  strokeWidth: STROKE.width,
  strokeLinecap: STROKE.linecap,
  strokeLinejoin: STROKE.linejoin,
} as const;

// Zone bounding boxes for slot highlights and future AI-mode overlay hotspots
export const SLOT_ZONES: Record<string, { x: number; y: number; w: number; h: number }> = {
  bed_frame:     { x: 120, y: 230, w: 340, h: 130 },
  mattress:      { x: 140, y: 235, w: 300, h: 70 },
  sheets:        { x: 140, y: 230, w: 300, h: 60 },
  comforter:     { x: 140, y: 235, w: 300, h: 75 },
  pillows:       { x: 145, y: 215, w: 110, h: 35 },
  nightstand:    { x: 55, y: 278, w: 55, h: 72 },
  dresser:       { x: 535, y: 250, w: 120, h: 100 },
  ceiling_light: { x: 355, y: 0, w: 90, h: 80 },
  table_lamp:    { x: 60, y: 248, w: 45, h: 40 },
  floor_lamp:    { x: 490, y: 190, w: 40, h: 130 },
  wall_art:      { x: 180, y: 45, w: 280, h: 160 },
  plants:        { x: 580, y: 330, w: 180, h: 140 },
  mirror:        { x: 550, y: 65, w: 75, h: 110 },
  rug:           { x: 95, y: 365, w: 390, h: 105 },
  curtains:      { x: 5, y: 25, w: 55, h: 290 },
  throw_blanket: { x: 255, y: 295, w: 130, h: 55 },
};
