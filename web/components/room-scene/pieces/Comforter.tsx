import { FILL, RADIUS, strokeProps } from "../constants";

export default function Comforter() {
  return (
    <path
      d={`M160 252 L430 252 L430 282
          Q420 290 400 288 Q370 292 340 287 Q310 292 280 288
          Q250 292 220 287 Q190 290 170 286 L160 282 Z`}
      rx={RADIUS.sm}
      fill={FILL.warm2}
      {...strokeProps}
    />
  );
}
