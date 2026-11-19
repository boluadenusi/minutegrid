export const CHAIN_NODE_WIDTH = 40;
export const CHAIN_NODE_HEIGHT = 30;
export const CHAIN_NODE_RADIUS = 6;

export function chainLinkGeometry(minute: number, columnWidth: number, rowHeight: number) {
  const column = (minute - 1) % 10;
  const row = Math.floor((minute - 1) / 10);
  const x = column * columnWidth + columnWidth / 2;
  const y = row * rowHeight + rowHeight / 2;
  const gap = 3;

  if (column === 9) {
    const targetX = columnWidth / 2;
    const targetY = y + rowHeight - CHAIN_NODE_HEIGHT / 2 - gap;
    return {
      path: `M ${x} ${y + CHAIN_NODE_HEIGHT / 2} V ${y + rowHeight / 2} H ${targetX} V ${targetY}`,
      arrowPath: `M ${targetX - 3} ${targetY - 6} L ${targetX} ${targetY} L ${targetX + 3} ${targetY - 6} Z`,
    };
  }

  const targetX = x + columnWidth - CHAIN_NODE_WIDTH / 2 - gap;
  return {
    path: `M ${x + CHAIN_NODE_WIDTH / 2} ${y} H ${targetX}`,
    arrowPath: `M ${targetX - 6} ${y - 3} L ${targetX} ${y} L ${targetX - 6} ${y + 3} Z`,
  };
}
