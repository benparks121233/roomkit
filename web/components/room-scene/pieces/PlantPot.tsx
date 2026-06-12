import { FILL, RADIUS, strokeProps } from "../constants";

interface PlantPotProps {
  x: number;
  y: number;
  height?: number;
  variant?: 0 | 1 | 2; // 0=upright oval, 1=drooping round, 2=spiky narrow
}

export default function PlantPot({ x, y, height = 80, variant = 0 }: PlantPotProps) {
  const potW = 28;
  const potH = height * 0.35;
  const potX = x - potW / 2;
  const potY = y + height - potH;
  const foliageY = potY - 4;

  return (
    <g>
      {/* Pot (trapezoid) */}
      <path
        d={`M${potX + 2} ${potY} L${potX - 1} ${potY + potH}
            Q${x} ${potY + potH + 3} ${potX + potW + 1} ${potY + potH}
            L${potX + potW - 2} ${potY} Z`}
        fill={FILL.terracotta}
        {...strokeProps}
      />
      {/* Pot rim */}
      <rect x={potX - 1} y={potY - 3} width={potW + 2} height={5} rx={RADIUS.sm} fill={FILL.terracotta} {...strokeProps} />

      {/* Foliage — varies by variant */}
      {variant === 0 && (
        // Upright oval leaves
        <g>
          <ellipse cx={x} cy={foliageY - 18} rx={8} ry={14} fill={FILL.green} {...strokeProps} strokeWidth={1} />
          <ellipse cx={x - 10} cy={foliageY - 10} rx={7} ry={12} fill={FILL.greenLight} {...strokeProps} strokeWidth={1} />
          <ellipse cx={x + 10} cy={foliageY - 12} rx={7} ry={13} fill={FILL.green} {...strokeProps} strokeWidth={1} />
          <ellipse cx={x + 5} cy={foliageY - 24} rx={6} ry={10} fill={FILL.greenLight} {...strokeProps} strokeWidth={1} />
        </g>
      )}
      {variant === 1 && (
        // Drooping rounded leaves
        <g>
          <ellipse cx={x - 12} cy={foliageY - 6} rx={10} ry={8} fill={FILL.green} {...strokeProps} strokeWidth={1} />
          <ellipse cx={x + 12} cy={foliageY - 8} rx={10} ry={7} fill={FILL.greenLight} {...strokeProps} strokeWidth={1} />
          <ellipse cx={x} cy={foliageY - 14} rx={9} ry={9} fill={FILL.green} {...strokeProps} strokeWidth={1} />
          <ellipse cx={x - 5} cy={foliageY - 22} rx={7} ry={7} fill={FILL.greenLight} {...strokeProps} strokeWidth={1} />
        </g>
      )}
      {variant === 2 && (
        // Spiky narrow leaves
        <g>
          <ellipse cx={x} cy={foliageY - 20} rx={4} ry={16} fill={FILL.green} {...strokeProps} strokeWidth={1} />
          <ellipse cx={x - 8} cy={foliageY - 14} rx={3.5} ry={13} fill={FILL.greenLight} {...strokeProps} strokeWidth={1} transform={`rotate(-12 ${x - 8} ${foliageY - 14})`} />
          <ellipse cx={x + 8} cy={foliageY - 15} rx={3.5} ry={13} fill={FILL.green} {...strokeProps} strokeWidth={1} transform={`rotate(12 ${x + 8} ${foliageY - 15})`} />
          <ellipse cx={x + 4} cy={foliageY - 26} rx={3} ry={10} fill={FILL.greenLight} {...strokeProps} strokeWidth={1} transform={`rotate(5 ${x + 4} ${foliageY - 26})`} />
        </g>
      )}
    </g>
  );
}
