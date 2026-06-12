import WallArtFrame from "../pieces/WallArtFrame";

// Pre-defined gallery arrangements for 1–4 frames.
// Slightly offset from perfect grid for a hand-placed organic feel.
const LAYOUTS: { x: number; y: number; w: number; h: number; rotate?: number }[][] = [
  // 1 frame — single large centered
  [{ x: 270, y: 70, w: 100, h: 80 }],
  // 2 frames — side by side, second offset higher
  [
    { x: 215, y: 82, w: 85, h: 68 },
    { x: 340, y: 75, w: 85, h: 68, rotate: -0.8 },
  ],
  // 3 frames — asymmetric trio
  [
    { x: 195, y: 65, w: 95, h: 85 },
    { x: 320, y: 60, w: 68, h: 55, rotate: 1.2 },
    { x: 328, y: 130, w: 72, h: 55 },
  ],
  // 4 frames — loose 2x2 grid
  [
    { x: 200, y: 58, w: 78, h: 60 },
    { x: 308, y: 53, w: 82, h: 65, rotate: -1 },
    { x: 195, y: 138, w: 82, h: 55, rotate: 0.7 },
    { x: 312, y: 133, w: 72, h: 58 },
  ],
];

export default function GalleryWallZone({ count }: { count: number }) {
  const clamped = Math.min(Math.max(count, 1), 4);
  const layout = LAYOUTS[clamped - 1];

  return (
    <g>
      {layout.map((frame, i) => (
        <WallArtFrame key={i} {...frame} />
      ))}
    </g>
  );
}
