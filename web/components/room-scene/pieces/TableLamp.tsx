import { FILL, strokeProps } from "../constants";

export default function TableLamp() {
  return (
    <g>
      {/* Shade (trapezoid) */}
      <path
        d="M68 258 L62 275 L98 275 L92 258 Z"
        fill={FILL.warm3}
        {...strokeProps}
      />
      {/* Stem */}
      <line x1={80} y1={275} x2={80} y2={286} stroke={FILL.accent} strokeWidth={1.5} strokeLinecap="round" />
      {/* Base */}
      <ellipse cx={80} cy={287} rx={10} ry={3} fill={FILL.warm2} {...strokeProps} />
    </g>
  );
}
