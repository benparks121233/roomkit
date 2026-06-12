import { FILL, RADIUS, strokeProps } from "../constants";

export default function Sheets() {
  return (
    <g>
      {/* Flat sheet */}
      <rect x={152} y={255} width={287} height={22} rx={RADIUS.sm} fill={FILL.surface} {...strokeProps} />
      {/* Folded-back top edge */}
      <path
        d="M152 255 L152 248 Q155 244 162 244 L290 244 Q297 244 300 248 L300 255 Z"
        fill={FILL.surface}
        {...strokeProps}
      />
    </g>
  );
}
