import { FILL, RADIUS, strokeProps } from "../constants";

export default function CeilingLight() {
  return (
    <g>
      {/* Cord */}
      <line x1={400} y1={0} x2={400} y2={35} stroke={FILL.accent} strokeWidth={1.2} strokeLinecap="round" />
      {/* Canopy (ceiling mount) */}
      <rect x={390} y={0} width={20} height={6} rx={3} fill={FILL.warm3} {...strokeProps} />
      {/* Shade */}
      <path
        d="M375 40 Q378 35 400 35 Q422 35 425 40 L420 65 Q415 68 400 68 Q385 68 380 65 Z"
        fill={FILL.warm3}
        {...strokeProps}
      />
      {/* Bulb glow hint */}
      <ellipse cx={400} cy={58} rx={8} ry={5} fill={FILL.surface} opacity={0.4} />
    </g>
  );
}
