import PlantPot from "../pieces/PlantPot";

// Pre-defined plant arrangements for 1–3 pots.
// Staggered heights create a pleasing silhouette.
const LAYOUTS: { x: number; y: number; height: number; variant: 0 | 1 | 2 }[][] = [
  // 1 plant — medium, centered in zone
  [{ x: 650, y: 350, height: 80, variant: 0 }],
  // 2 plants — medium + shorter
  [
    { x: 620, y: 355, height: 75, variant: 0 },
    { x: 695, y: 375, height: 58, variant: 1 },
  ],
  // 3 plants — tall, medium, small
  [
    { x: 605, y: 340, height: 90, variant: 0 },
    { x: 665, y: 360, height: 70, variant: 1 },
    { x: 725, y: 378, height: 55, variant: 2 },
  ],
];

export default function PlantZone({ count }: { count: number }) {
  const clamped = Math.min(Math.max(count, 1), 3);
  const layout = LAYOUTS[clamped - 1];

  return (
    <g>
      {layout.map((plant, i) => (
        <PlantPot key={i} {...plant} />
      ))}
    </g>
  );
}
