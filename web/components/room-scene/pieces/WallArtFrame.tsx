import { FILL, RADIUS, strokeProps } from "../constants";

interface WallArtFrameProps {
  x: number;
  y: number;
  w: number;
  h: number;
  rotate?: number; // degrees, subtle (±1.5)
}

export default function WallArtFrame({ x, y, w, h, rotate = 0 }: WallArtFrameProps) {
  const cx = x + w / 2;
  const cy = y + h / 2;
  const inset = 6;

  return (
    <g transform={rotate ? `rotate(${rotate} ${cx} ${cy})` : undefined}>
      {/* Outer frame */}
      <rect x={x} y={y} width={w} height={h} rx={RADIUS.sm} fill={FILL.warm2} {...strokeProps} />
      {/* Inner canvas */}
      <rect
        x={x + inset}
        y={y + inset}
        width={w - inset * 2}
        height={h - inset * 2}
        rx={2}
        fill={FILL.surface}
        {...strokeProps}
        strokeWidth={0.75}
      />
      {/* Abstract deco mark */}
      <circle
        cx={x + w * 0.55}
        cy={y + h * 0.5}
        r={Math.min(w, h) * 0.12}
        fill="none"
        stroke={FILL.warm1}
        strokeWidth={1}
      />
    </g>
  );
}
