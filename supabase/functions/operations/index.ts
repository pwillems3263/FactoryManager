/**
 * Edge Function: operations
 * GET /functions/v1/operations?id_machine=X
 *
 * Returns today's planned and in-progress operations for a given machine,
 * including work order, component name, operation description, and planned time.
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
    const url        = new URL(req.url);
    const id_machine = url.searchParams.get("id_machine");

    if (!id_machine) {
      return new Response(
        JSON.stringify({ error: "id_machine query parameter is required." }),
        { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
      );
    }

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const today    = new Date();
    const dayStart = new Date(today.getFullYear(), today.getMonth(), today.getDate(),  0,  0,  0).toISOString();
    const dayEnd   = new Date(today.getFullYear(), today.getMonth(), today.getDate(), 23, 59, 59).toISOString();

    // Fetch operations with related data in a single query
    const { data, error } = await supabase
      .from("operationplanifiee")
      .select(`
        id_op_plan,
        statut,
        date_debut,
        date_fin,
        date_debut_reelle,
        operation (
          id_operation,
          description,
          ordre,
          tps_preparation,
          tps_execution
        ),
        of:ordrefabrication (
          id_of,
          code_of,
          quantite,
          composant (
            nom
          )
        )
      `)
      .eq("id_machine", parseInt(id_machine))
      .in("statut", ["planifiee", "en_cours"])
      .gte("date_debut", dayStart)
      .lte("date_debut", dayEnd)
      .order("date_debut");

    if (error) throw error;

    // Shape the response for the kiosk UI
    const ops = (data ?? []).map((op: any) => {
      const qty         = parseFloat(op.of?.quantite ?? 1);
      const tps_prep    = op.operation?.tps_preparation ?? 0;
      const tps_exec    = op.operation?.tps_execution   ?? 0;
      const planned_min = Math.round(tps_prep + tps_exec * qty);

      return {
        id_op_plan:   op.id_op_plan,
        statut:       op.statut,                              // "planifiee" | "en_cours"
        operation:    op.operation?.description ?? `OP-${op.operation?.ordre ?? "?"}`,
        work_order:   op.of?.code_of ?? `WO-${op.of?.id_of}`,
        component:    op.of?.composant?.nom ?? "—",
        planned_min,
        date_debut:   op.date_debut,
        date_debut_reelle: op.date_debut_reelle ?? null,
      };
    });

    return new Response(JSON.stringify(ops), {
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
