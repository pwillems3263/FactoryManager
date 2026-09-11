/**
 * Edge Function: login
 * POST /functions/v1/login
 *
 * Security:
 * - PIN verified server-side with SHA-256 + salt
 * - Blocked after 3 failed attempts for 15 minutes
 * - Admin can unblock manually via FactoryManager
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const MAX_ATTEMPTS  = 3;
const BLOCK_MINUTES = 15;

async function sha256hex(text: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function fail(status: number, error: string) {
  return new Response(
    JSON.stringify({ ok: false, error }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" }, status }
  );
}

async function clearAttempts(supabase: any, id_user: number) {
  await supabase.from("login_attempts").delete().eq("id_user", id_user);
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  try {
    const { id_user, pin } = await req.json();

    if (!id_user || !pin)          return fail(400, "id_user and pin are required.");
    if (!/^\d{4}$/.test(String(pin))) return fail(400, "PIN must be 4 digits.");

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const { data: u, error } = await supabase
      .from("user")
      .select("id_user, username, full_name, niveau, actif, pin_hash, pin_salt, kiosk_blocked_until")
      .eq("id_user", id_user)
      .single();

    if (error || !u)             return fail(401, "User not found.");
    if (!u.actif)                return fail(401, "Account is disabled.");
    if (!u.pin_hash || !u.pin_salt) return fail(401, "No PIN set. Contact your administrator.");

    // Check if blocked
    if (u.kiosk_blocked_until) {
      const blockedUntil = new Date(u.kiosk_blocked_until);
      if (blockedUntil > new Date()) {
        const remaining = Math.ceil((blockedUntil.getTime() - Date.now()) / 60000);
        return fail(403, `Account locked. Try again in ${remaining} minute${remaining > 1 ? "s" : ""} or contact your administrator.`);
      }
      // Block expired — clear
      await supabase.from("user").update({ kiosk_blocked_until: null }).eq("id_user", id_user);
      await clearAttempts(supabase, id_user);
    }

    // Verify PIN
    const ip = req.headers.get("x-forwarded-for") ?? "unknown";
    const computed = await sha256hex(u.pin_salt + String(pin));

    if (computed !== u.pin_hash) {
      // Record failed attempt
      await supabase.from("login_attempts").insert({
        id_user,
        attempted_at: new Date().toISOString(),
        ip_address: ip,
      });

      // Count recent attempts
      const since = new Date(Date.now() - BLOCK_MINUTES * 60000).toISOString();
      const { count } = await supabase
        .from("login_attempts")
        .select("id", { count: "exact", head: true })
        .eq("id_user", id_user)
        .gte("attempted_at", since);

      const attempts = count ?? 0;

      if (attempts >= MAX_ATTEMPTS) {
        const blockedUntil = new Date(Date.now() + BLOCK_MINUTES * 60000).toISOString();
        await supabase.from("user").update({ kiosk_blocked_until: blockedUntil }).eq("id_user", id_user);
        return fail(403, `Account locked after ${MAX_ATTEMPTS} failed attempts. Try again in ${BLOCK_MINUTES} minutes or contact your administrator.`);
      }

      const left = MAX_ATTEMPTS - attempts;
      return fail(401, `Incorrect PIN. ${left} attempt${left > 1 ? "s" : ""} remaining.`);
    }

    // Success — clear attempts
    await clearAttempts(supabase, id_user);
    await supabase.from("user").update({ kiosk_blocked_until: null }).eq("id_user", id_user);

    return new Response(
      JSON.stringify({ ok: true, id_user: u.id_user, display_name: u.full_name || u.username, niveau: u.niveau }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
    );

  } catch (err) {
    return fail(500, String(err));
  }
});
