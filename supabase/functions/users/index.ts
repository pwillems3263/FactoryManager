/**
 * Edge Function: users
 * GET /functions/v1/users
 *
 * Returns the list of active users for the kiosk combo box.
 * Only id_user and full_name (or username) are exposed — no password data.
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const { data, error } = await supabase
      .from("user")
      .select("id_user, username, full_name")
      .eq("actif", true)
      .order("full_name", { ascending: true });

    if (error) throw error;

    // Return display_name = full_name if set, else username
    const users = data.map((u: any) => ({
      id_user:      u.id_user,
      display_name: u.full_name || u.username,
    }));

    return new Response(JSON.stringify(users), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 200,
    });

  } catch (err) {
    return new Response(JSON.stringify({ error: String(err) }), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
      status: 500,
    });
  }
});
