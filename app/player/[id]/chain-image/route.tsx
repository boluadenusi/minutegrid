import { ImageResponse } from "next/og";
import { getChains, getPlayerData } from "@/lib/data";
import { chainLinkGeometry, CHAIN_NODE_HEIGHT, CHAIN_NODE_RADIUS, CHAIN_NODE_WIDTH } from "@/lib/chain-geometry";
import { shareHeat, shareTheme } from "@/lib/share-theme";

export const runtime = "nodejs";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const player = getPlayerData(Number(id));
  if (!player) return new Response("Player not found", { status: 404 });

  const chains = getChains(player.minuteGoalCounts);
  const longest = chains.reduce<(typeof chains)[number] | null>(
    (best, chain) => !best || chain.length > best.length ? chain : best,
    null
  );
  const rows = Array.from({ length: 9 }, (_, row) =>
    Array.from({ length: 10 }, (_, col) => row * 10 + col + 1)
  );
  const links = Array.from({ length: 89 }, (_, index) => index + 1).filter(
    (minute) => (player.minuteGoalCounts[String(minute)] ?? 0) > 0 &&
      (player.minuteGoalCounts[String(minute + 1)] ?? 0) > 0
  );

  return new ImageResponse(
    <div style={{ display: "flex", flexDirection: "column", width: "100%", height: "100%", background: shareTheme.background, padding: "38px 80px", fontFamily: shareTheme.bodyFont, color: shareTheme.foreground }}>
      <div style={{ display: "flex", color: shareTheme.accent, fontFamily: shareTheme.displayFont, fontSize: 18, fontWeight: 700, letterSpacing: "0.1em" }}>MINUTE GRID / CHAIN</div>
      <div style={{ display: "flex", fontFamily: shareTheme.displayFont, fontSize: 46, fontWeight: 700, marginTop: 8 }}>{player.name}</div>
      <div style={{ display: "flex", color: shareTheme.muted, fontSize: 20, marginTop: 8 }}>
        {chains.length} separate {chains.length === 1 ? "chain" : "chains"}
        {" · "}{longest ? `Longest: minutes ${longest.start} to ${longest.end}, ${longest.length} long` : "No scored minutes"}
      </div>
      <div style={{ position: "relative", display: "flex", width: 1000, height: 414, marginTop: 26 }}>
        <svg width="1000" height="414" viewBox="0 0 1000 414" style={{ position: "absolute", left: 0, top: 0 }}>
          {links.map((minute) => {
            const { path, arrowPath } = chainLinkGeometry(minute, 100, 46);
            return <g key={minute}>
              <path d={path} fill="none" stroke={shareTheme.accent} strokeWidth="2" />
              <path d={arrowPath} fill={shareTheme.accent} />
            </g>;
          })}
          {chains.map(({ start }) => {
            const x = ((start - 1) % 10) * 100 + 50;
            const y = Math.floor((start - 1) / 10) * 46 + 23;
            return <rect key={start} x={x - 23} y={y - 18} width="46" height="36" rx={CHAIN_NODE_RADIUS} fill="none" stroke={shareTheme.accent} strokeWidth="2" />;
          })}
        </svg>
        <div style={{ display: "flex", flexDirection: "column", width: 1000, height: 414 }}>
          {rows.map((row, index) => <div key={index} style={{ display: "flex", width: 1000, height: 46 }}>
            {row.map((minute) => {
              const count = player.minuteGoalCounts[String(minute)] ?? 0;
              const scored = count > 0;
              const heat = shareHeat(count);
              return <div key={minute} style={{ display: "flex", width: 100, height: 46, alignItems: "center", justifyContent: "center" }}>
                <div style={{ display: "flex", width: CHAIN_NODE_WIDTH, height: CHAIN_NODE_HEIGHT, alignItems: "center", justifyContent: "center", borderRadius: CHAIN_NODE_RADIUS, background: heat.background, border: scored ? `1px solid ${heat.background}` : `1px dashed ${shareTheme.gap}`, color: heat.color, fontSize: 12, fontWeight: 700 }}>
                  {minute}
                </div>
              </div>;
            })}
          </div>)}
        </div>
      </div>
    </div>,
    { width: 1200, height: 630, fonts: shareTheme.fonts }
  );
}
