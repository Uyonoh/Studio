import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const { origin } = new URL(request.url);
  const supabase = createClient();
  await supabase.auth.signOut();
  return NextResponse.redirect(`${origin}/login`, {
    status: 302,
  });
}
