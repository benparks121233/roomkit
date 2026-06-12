import { FILL, RADIUS, strokeProps } from "../constants";

export default function Dresser() {
  return (
    <g>
      {/* Body */}
      <rect x={542} y={268} width={108} height={80} rx={RADIUS.md} fill={FILL.warm1} {...strokeProps} />
      {/* Top surface */}
      <rect x={538} y={260} width={116} height={10} rx={RADIUS.sm} fill={FILL.warm2} {...strokeProps} />
      {/* Drawer lines */}
      <line x1={555} y1={293} x2={637} y2={293} {...strokeProps} />
      <line x1={555} y1={318} x2={637} y2={318} {...strokeProps} />
      <line x1={555} y1={343} x2={637} y2={343} {...strokeProps} />
      {/* Knobs */}
      <circle cx={596} cy={281} r={2.5} fill={FILL.warm3} {...strokeProps} />
      <circle cx={596} cy={306} r={2.5} fill={FILL.warm3} {...strokeProps} />
      <circle cx={596} cy={331} r={2.5} fill={FILL.warm3} {...strokeProps} />
      {/* Legs */}
      <rect x={548} y={348} width={6} height={12} rx={2} fill={FILL.warm3} {...strokeProps} />
      <rect x={638} y={348} width={6} height={12} rx={2} fill={FILL.warm3} {...strokeProps} />
    </g>
  );
}
