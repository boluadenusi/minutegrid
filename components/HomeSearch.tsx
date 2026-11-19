"use client";

import { useRouter } from "next/navigation";
import PlayerCommandSearch from "@/components/PlayerCommandSearch";

export default function HomeSearch() {
  const router = useRouter();
  return <PlayerCommandSearch
    onSelectPlayer={(id) => router.push(`/player/${id}`)}
    label="Search player…"
    className="flex w-full items-center justify-between gap-3 rounded-xl border border-tone-700 bg-tone-900 px-4 py-3 text-left text-sm text-tone-400 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-scored-400 hover:border-scored-500"
  />;
}
