import { ImageResponse } from "next/og";
import { getPlayerData } from "@/lib/data";
import { shareHeat, shareTheme } from "@/lib/share-theme";

export const runtime = "nodejs";
export const contentType = "image/png";
export const size = { width: 1200, height: 630 };

interface Props {
  params: Promise<{ id: string }>;
}

export default async function OgImage({ params }: Props) {
  const { id } = await params;
  const player = getPlayerData(Number(id));

  if (!player) {
    return new ImageResponse(
      (
        <div
          style={{
            display: "flex",
            width: "100%",
            height: "100%",
            background: shareTheme.background,
            alignItems: "center",
            justifyContent: "center",
            color: shareTheme.muted,
            fontSize: 32,
            fontFamily: shareTheme.bodyFont,
          }}
        >
          Player not found
        </div>
      ),
      { ...size, fonts: shareTheme.fonts }
    );
  }

  const scoredSet = new Set(player.minutesScored);
  const cells = Array.from({ length: 90 }, (_, i) => i + 1);
  const hasNoGaps = player.missingMinutes.length === 0;

  return new ImageResponse(
    (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          width: "100%",
          height: "100%",
          background: shareTheme.background,
          padding: "40px 48px",
          fontFamily: shareTheme.bodyFont,
          gap: "18px",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            alignItems: "flex-start",
            justifyContent: "space-between",
            width: "100%",
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
            <div
              style={{
                display: "flex",
                color: shareTheme.accent,
                fontFamily: shareTheme.displayFont,
                fontSize: 18,
                fontWeight: 700,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
              }}
            >
              Minute Grid
            </div>
            <div
              style={{
                display: "flex",
                color: shareTheme.foreground,
                fontFamily: shareTheme.displayFont,
                fontSize: 44,
                fontWeight: 800,
                lineHeight: 1.1,
              }}
            >
              {player.name}
            </div>
            <div style={{ display: "flex", color: shareTheme.muted, fontSize: 18 }}>
              {player.minutesScoredCount} of 90 minutes · {player.totalGoals}{" "}
              total goals
            </div>
          </div>

          {/* Badge: No gaps vs Gap rings legend */}
          {hasNoGaps ? (
            <div
              style={{
                display: "flex",
                flexDirection: "row",
                alignItems: "center",
                gap: "8px",
                background: shareTheme.card,
                border: `2px solid ${shareTheme.accent}`,
                borderRadius: "9999px",
                padding: "8px 16px",
                color: shareTheme.foreground,
                fontSize: 14,
                fontWeight: 700,
              }}
            >
              <span>Every minute covered (added time in 45 and 90)</span>
            </div>
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "row",
                alignItems: "center",
                gap: "8px",
                background: shareTheme.card,
                border: `2px solid ${shareTheme.gap}`,
                borderRadius: "9999px",
                padding: "8px 16px",
                color: shareTheme.foreground,
                fontSize: 14,
                fontWeight: 700,
              }}
            >
              <div
                style={{
                  display: "flex",
                  width: "10px",
                  height: "10px",
                  borderRadius: "9999px",
                  background: shareTheme.gap,
                }}
              />
              <span>
                {player.missingMinutes.length} gap
                {player.missingMinutes.length !== 1 ? "s" : ""}:{" "}
                {player.missingMinutes.slice(0, 5).join(", ")}
                {player.missingMinutes.length > 5 ? "…" : ""}
              </span>
            </div>
          )}
        </div>

        {/* 90-Cell Grid with Gap Rings */}
        <div
          style={{
            display: "flex",
            flexDirection: "row",
            flexWrap: "wrap",
            gap: "5px",
            width: "100%",
            alignContent: "flex-start",
          }}
        >
          {cells.map((minute) => {
            const scored = scoredSet.has(minute);
            const heat = shareHeat(player.minuteGoalCounts[String(minute)] ?? 0);
            return (
              <div
                key={minute}
                style={{
                  width: "105px",
                  height: "44px",
                  borderRadius: "6px",
                  background: heat.background,
                  border: scored ? "none" : `2px dashed ${shareTheme.gap}`,
                  boxShadow: scored ? "none" : `0 0 0 2px ${shareTheme.gap}`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  color: heat.color,
                  fontSize: 13,
                  fontWeight: 700,
                }}
              >
                <span>{minute}</span>
              </div>
            );
          })}
        </div>
      </div>
    ),
    { ...size, fonts: shareTheme.fonts }
  );
}
