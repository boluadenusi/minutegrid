import { getIndex } from "@/lib/data";
import { NextResponse } from "next/server";

export const dynamic = "force-static";
// The 10-year window moves every day; rebuild at most hourly.
export const revalidate = 3600;

export function GET() {
  const data = getIndex();
  return NextResponse.json(data);
}

