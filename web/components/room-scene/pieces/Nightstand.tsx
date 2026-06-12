import { FILL, RADIUS, strokeProps } from "../constants";

export default function Nightstand() {
  return (
    <g>
      {/* Body */}
      <rect x={58} y={288} width={52} height={50} rx={RADIUS.sm} fill={FILL.warm2} {...strokeProps} />
      {/* Top surface */}
      <rect x={55} y={283} width={58} height={8} rx={RADIUS.sm} fill={FILL.warm3} {...strokeProps} />
      {/* Drawer line */}
      <line x1={68} y1={313} x2={100} y2={313} {...strokeProps} />
      {/* Knob */}
      <circle cx={84} cy={305} r={2.5} fill={FILL.warm3} {...strokeProps} />
      {/* Legs */}
      <rect x={62} y={338} width={5} height={14} rx={2} fill={FILL.warm3} {...strokeProps} />
      <rect x={101} y={338} width={5} height={14} rx={2} fill={FILL.warm3} {...strokeProps} />
    </g>
  );
}
