import { FILL, RADIUS, strokeProps } from "../constants";

export default function Mattress() {
  return (
    <rect
      x={148} y={262} width={295} height={32}
      rx={RADIUS.md}
      fill={FILL.warm1}
      {...strokeProps}
    />
  );
}
