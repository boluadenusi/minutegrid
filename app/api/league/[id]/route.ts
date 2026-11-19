import { NextRequest, NextResponse } from "next/server";
import { getLeague } from "@/lib/data";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const league = getLeague(id);
  if (!league) {
    return NextResponse.json({ error: "League not found" }, { status: 404 });
  }
  return NextResponse.json(league);
}
