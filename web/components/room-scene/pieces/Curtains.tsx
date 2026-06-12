import { FILL, RADIUS, strokeProps } from "../constants";

export default function Curtains() {
  return (
    <g>
      {/* Left curtain */}
      <path
        d={`M12 30 L12 300 Q18 298 22 300 Q28 298 32 300 Q38 298 42 300
            L50 300 L50 30 Q40 32 30 30 Q20 32 12 30 Z`}
        fill={FILL.warm1}
        {...strokeProps}
      />
      {/* Left rod */}
      <rect x={8} y={26} width={48} height={5} rx={2.5} fill={FILL.warm3} {...strokeProps} />

      {/* Right curtain */}
      <path
        d={`M750 30 L750 300 Q756 298 760 300 Q766 298 770 300 Q776 298 780 300
            L788 300 L788 30 Q778 32 768 30 Q758 32 750 30 Z`}
        fill={FILL.warm1}
        {...strokeProps}
      />
      {/* Right rod */}
      <rect x={744} y={26} width={48} height={5} rx={2.5} fill={FILL.warm3} {...strokeProps} />
    </g>
  );
}
