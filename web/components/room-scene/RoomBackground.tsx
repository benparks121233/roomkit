import { FILL, SCENE, strokeProps } from "./constants";

export default function RoomBackground() {
  return (
    <g>
      {/* Wall */}
      <rect x={0} y={0} width={SCENE.viewBox.w} height={SCENE.floorY} fill={FILL.wall} />
      {/* Floor */}
      <rect
        x={0}
        y={SCENE.floorY}
        width={SCENE.viewBox.w}
        height={SCENE.viewBox.h - SCENE.floorY}
        fill={FILL.floor}
      />
      {/* Baseboard */}
      <rect
        x={0}
        y={SCENE.baseboardY}
        width={SCENE.viewBox.w}
        height={SCENE.baseboardH}
        fill={FILL.baseboard}
        {...strokeProps}
        strokeWidth={0.75}
      />
    </g>
  );
}
