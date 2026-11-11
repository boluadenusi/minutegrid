import { getIndex } from "@/lib/data";
import { NextResponse } from "next/server";

export const dynamic = "force-static";

export function GET() {
  const data = getIndex();
  return NextResponse.json(data);
}
