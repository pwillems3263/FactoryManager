/**
 * Edge Function: machines
 * GET /functions/v1/machines
 *
 * Returns all machines that are not hors_service,
 * with their current status and number of operations in progress today.
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    // Fetch active machines (exclude hors_service / out_of_service)
    const { data: machines, error } = await supabase
      .from("machine")
      .select("id_machine, nom, type, statut")
      .not("statut", "in", '("hors_service","out_of_service")')
      .order("nom");

    if (error) throw error;

    // For each machine, check if there are operations in progress today
    const today = new Date();
    const dayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 0, 0, 0).toISOString();
    const dayEnd   = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59).toISOString();

    const result = await Promise.all(
      machines.map(async (m: any) => {
        const { count } = await supabase
          .from("operationplanifiee")
          .select("id_op_plan", { count: "exact", head: true })
          .eq("id_machine", m.id_machine)
          .eq("statut", "en_cours")
          .gte("date_debut", dayStart)
          .lte("date_debut", dayEnd);

        return {
          id_machine: m.id_machine,
          nom:        m.nom,
          type:       m.type || null,
          statut:     m.statut,
          ops_en_cours: count ?? 0,
        };
      })
    );

    return new Response(JSON.stringify(result), {
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
