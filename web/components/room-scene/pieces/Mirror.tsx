import { FILL, RADIUS, strokeProps } from "../constants";

export default function Mirror() {
  return (
    <g>
      {/* Outer frame */}
      <rect x={560} y={80} width={55} height={85} rx={RADIUS.lg} fill={FILL.warm2} {...strokeProps} />
      {/* Glass surface */}
      <rect x={567} y={87} width={41} height={71} rx={RADIUS.md} fill={FILL.surface} {...strokeProps} />
      {/* Highlight gleam */}
      <path
        d="M575 95 Q578 92 582 95"
        fill="none"
        stroke={FILL.warm1}
        strokeWidth={1.5}
        strokeLinecap="round"
      />
    </g>
  );
}
