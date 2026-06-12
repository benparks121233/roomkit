import { FILL, strokeProps } from "../constants";

export default function ThrowBlanket() {
  return (
    <path
      d={`M270 295 Q290 292 320 295 Q350 292 370 295
          L375 310 Q360 318 340 315 Q310 320 290 316 Q270 319 265 315 Z`}
      fill={FILL.warm3}
      {...strokeProps}
    />
  );
}
