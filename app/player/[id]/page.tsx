import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { getPlayerData } from "@/lib/data";
import PlayerView from "@/components/PlayerView";
import { getInitialMinute } from "@/lib/minute";

interface Props {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ view?: string | string[]; minute?: string | string[] }>;
}

// ---------------------------------------------------------------------------
// Metadata / link previews
// ---------------------------------------------------------------------------
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params;
  const player = getPlayerData(Number(id));
  if (!player) return { title: "Player not found | Minute Grid" };

  const description = `${player.name} has scored in ${player.minutesScoredCount} of 90 minutes · ${player.totalGoals} total goals`;
  const chainImage = `/player/${id}/chain-image`;
  return {
    title: `${player.name} | Minute Grid`,
    description,
    openGraph: {
      title: `${player.name} | Minute Grid`,
      description,
      images: [chainImage],
    },
    twitter: {
      card: "summary_large_image",
      title: `${player.name} | Minute Grid`,
      description,
      images: [chainImage],
    },
  };
}

// ---------------------------------------------------------------------------
// Page (Server Component)
// ---------------------------------------------------------------------------
export default async function PlayerPage({ params, searchParams }: Props) {
  const { id } = await params;
  const { minute } = await searchParams;
  const player = getPlayerData(Number(id));
  if (!player) notFound();

  const initialMinute = getInitialMinute(minute);
  return <PlayerView initialPlayer={player} initialMinute={initialMinute} />;
}
