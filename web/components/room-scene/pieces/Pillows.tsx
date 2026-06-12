import { FILL, RADIUS, strokeProps } from "../constants";

export default function Pillows() {
  return (
    <g>
      {/* Left pillow */}
      <ellipse cx={175} cy={250} rx={24} ry={12} fill={FILL.surface} {...strokeProps} />
      {/* Right pillow */}
      <ellipse cx={228} cy={250} rx={24} ry={12} fill={FILL.surface} {...strokeProps} />
    </g>
  );
}
