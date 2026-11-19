import type { Metadata } from "next";
import { getPlayerData } from "@/lib/data";
import { parsePlayerId } from "@/lib/compare";
import CompareView from "@/components/CompareView";

interface Props {
  searchParams: Promise<{ a?: string | string[]; b?: string | string[] }>;
}

async function players(searchParams: Props["searchParams"]) {
  const { a, b } = await searchParams;
  const idA = parsePlayerId(a);
  const idB = parsePlayerId(b);
  return [idA ? getPlayerData(idA) : null, idB ? getPlayerData(idB) : null] as const;
}

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const [a, b] = await players(searchParams);
  const title = a && b ? `${a.name} vs ${b.name} | Minute Grid` : "Compare players | Minute Grid";
  return { title, description: "Compare which minutes two footballers have scored in." };
}

export default async function ComparePage({ searchParams }: Props) {
  const [a, b] = await players(searchParams);
  return <CompareView initialA={a} initialB={b} />;
}
