import { FILL, RADIUS, strokeProps } from "../constants";

export default function BedFrame() {
  return (
    <g>
      {/* Headboard */}
      <rect x={125} y={200} width={18} height={110} rx={RADIUS.md} fill={FILL.warm3} {...strokeProps} />
      {/* Frame rails */}
      <rect x={140} y={290} width={310} height={14} rx={RADIUS.sm} fill={FILL.warm2} {...strokeProps} />
      <rect x={140} y={310} width={310} height={14} rx={RADIUS.sm} fill={FILL.warm2} {...strokeProps} />
      {/* Footboard */}
      <rect x={445} y={255} width={12} height={72} rx={RADIUS.sm} fill={FILL.warm2} {...strokeProps} />
      {/* Legs */}
      <rect x={142} y={324} width={8} height={26} rx={3} fill={FILL.warm3} {...strokeProps} />
      <rect x={205} y={324} width={8} height={26} rx={3} fill={FILL.warm3} {...strokeProps} />
      <rect x={380} y={324} width={8} height={26} rx={3} fill={FILL.warm3} {...strokeProps} />
      <rect x={442} y={324} width={8} height={26} rx={3} fill={FILL.warm3} {...strokeProps} />
    </g>
  );
}
