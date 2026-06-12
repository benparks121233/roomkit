import { SLOT_ZONES } from "./constants";

export default function SlotHighlight({ slotId }: { slotId: string }) {
  const zone = SLOT_ZONES[slotId];
  if (!zone) return null;

  return (
    <rect
      x={zone.x}
      y={zone.y}
      width={zone.w}
      height={zone.h}
      rx={8}
      fill="none"
      stroke="#C8C5BC"
      strokeWidth={1.5}
      strokeDasharray="8 5"
      opacity={0.5}
    />
  );
}
