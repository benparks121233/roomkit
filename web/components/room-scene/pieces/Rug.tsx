import { FILL, RADIUS, strokeProps } from "../constants";

export default function Rug() {
  return (
    <g>
      {/* Main rug shape */}
      <rect x={100} y={370} width={380} height={95} rx={RADIUS.lg} fill={FILL.warm2} {...strokeProps} />
      {/* Inner border */}
      <rect x={115} y={382} width={350} height={71} rx={RADIUS.md} fill={FILL.warm1} {...strokeProps} strokeWidth={1} />
      {/* Fringe hints (left) */}
      <line x1={105} y1={370} x2={105} y2={365} {...strokeProps} strokeWidth={1} />
      <line x1={115} y1={370} x2={115} y2={365} {...strokeProps} strokeWidth={1} />
      <line x1={125} y1={370} x2={125} y2={365} {...strokeProps} strokeWidth={1} />
      {/* Fringe hints (right) */}
      <line x1={455} y1={370} x2={455} y2={365} {...strokeProps} strokeWidth={1} />
      <line x1={465} y1={370} x2={465} y2={365} {...strokeProps} strokeWidth={1} />
      <line x1={475} y1={370} x2={475} y2={365} {...strokeProps} strokeWidth={1} />
    </g>
  );
}
