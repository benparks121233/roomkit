import { FILL, strokeProps } from "../constants";

export default function FloorLamp() {
  return (
    <g>
      {/* Shade */}
      <path
        d="M490 200 L485 225 L515 225 L510 200 Z"
        fill={FILL.warm3}
        {...strokeProps}
      />
      {/* Stem */}
      <line x1={500} y1={225} x2={500} y2={340} stroke={FILL.accent} strokeWidth={1.5} strokeLinecap="round" />
      {/* Base */}
      <ellipse cx={500} cy={342} rx={14} ry={5} fill={FILL.warm2} {...strokeProps} />
    </g>
  );
}
