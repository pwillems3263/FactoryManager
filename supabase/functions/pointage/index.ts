/**
 * Edge Function: pointage
 * POST /functions/v1/pointage
 *
 * Body: { action, id_op_plan, id_user, motif? }
 *
 * action = "start"   → planifiee  → en_cours   (sets date_debut_reelle)
 * action = "pause"   → en_cours   → pause open  (creates PausePointage row)
 * action = "resume"  → closes open pause        (sets fin_pause + duree_min)
 * action = "finish"  → en_cours   → terminee    (sets date_fin_reelle, calculates times)
 *
 * All actions record id_user for full traceability
 * ("who did what and when" visible in FactoryManager).
 *
 * Mirrors the logic of Python's pointage_service.py.
 */
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

const VALID_ACTIONS  = ["start", "pause", "resume", "finish"];
const VALID_MOTIFS   = ["repas", "panne", "attente_matiere", "formation", "autre"];

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const body = await req.json();
    const { action, id_op_plan, id_user, motif } = body;

    // ── Basic validation ────────────────────────────────────────────────────
    if (!action || !id_op_plan || !id_user) {
      return err400("action, id_op_plan and id_user are required.");
    }
    if (!VALID_ACTIONS.includes(action)) {
      return err400(`Invalid action. Must be one of: ${VALID_ACTIONS.join(", ")}`);
    }
    if (action === "pause" && motif && !VALID_MOTIFS.includes(motif)) {
      return err400(`Invalid motif. Must be one of: ${VALID_MOTIFS.join(", ")}`);
    }

    const supabase = createClient(
      Deno.env.get("SUPABASE_URL")!,
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!
    );

    const now = new Date().toISOString();

    // ── Fetch the operation ─────────────────────────────────────────────────
    const { data: op, error: opErr } = await supabase
      .from("operationplanifiee")
      .select(`
        id_op_plan, statut, date_debut_reelle, id_of, id_machine,
        operation ( tps_preparation, tps_execution, ordre ),
        of:ordrefabrication ( id_of, quantite, statut, id_of_assemblage,
          ofassemblage:ofassemblage ( id_of_assemblage, statut )
        )
      `)
      .eq("id_op_plan", id_op_plan)
      .single();

    if (opErr || !op) return err404("Operation not found.");

    // ── ACTION: start ───────────────────────────────────────────────────────
    if (action === "start") {
      if (op.statut !== "planifiee") {
        return err409(`Cannot start: current status is '${op.statut}'.`);
      }

      const { error } = await supabase
        .from("operationplanifiee")
        .update({
          statut:            "en_cours",
          date_debut_reelle: now,
          id_user_pointage:  id_user,       // traceability field (see note below)
        })
        .eq("id_op_plan", id_op_plan);
      if (error) throw error;

      // Cascade: set OF → en_cours if needed
      await cascadeOFStart(supabase, op);

      return ok({ action: "start", id_op_plan, started_at: now });
    }

    // ── ACTION: pause ───────────────────────────────────────────────────────
    if (action === "pause") {
      if (op.statut !== "en_cours") {
        return err409(`Cannot pause: current status is '${op.statut}'.`);
      }

      // Safety: close any previously open pause
      await closeOpenPause(supabase, id_op_plan, now);

      const { error } = await supabase
        .from("pausepointage")
        .insert({
          id_op_plan,
          debut_pause: now,
          motif:       motif ?? "autre",
        });
      if (error) throw error;

      return ok({ action: "pause", id_op_plan, paused_at: now, motif: motif ?? "autre" });
    }

    // ── ACTION: resume ──────────────────────────────────────────────────────
    if (action === "resume") {
      const pause = await getOpenPause(supabase, id_op_plan);
      if (!pause) return err409("No open pause found for this operation.");

      const duree_min = Math.max(
        1,
        Math.round((new Date(now).getTime() - new Date(pause.debut_pause).getTime()) / 60000)
      );

      const { error } = await supabase
        .from("pausepointage")
        .update({ fin_pause: now, duree_min })
        .eq("id_pause", pause.id_pause);
      if (error) throw error;

      return ok({ action: "resume", id_op_plan, resumed_at: now, pause_duration_min: duree_min });
    }

    // ── ACTION: finish ──────────────────────────────────────────────────────
    if (action === "finish") {
      if (op.statut !== "en_cours") {
        return err409(`Cannot finish: current status is '${op.statut}'.`);
      }

      // Close any open pause automatically
      await closeOpenPause(supabase, id_op_plan, now);

      // Calculate real working time (gross elapsed − total pauses)
      const startedAt   = op.date_debut_reelle ? new Date(op.date_debut_reelle) : new Date(now);
      const elapsedMin  = Math.round((new Date(now).getTime() - startedAt.getTime()) / 60000);
      const pausesMin   = await getTotalPausesMin(supabase, id_op_plan);
      const workedMin   = Math.max(1, elapsedMin - pausesMin);
      const tps_prep    = Math.max(1, Math.round(workedMin * 0.1));  // 10% setup heuristic
      const tps_exec    = workedMin - tps_prep;

      const { error } = await supabase
        .from("operationplanifiee")
        .update({
          statut:          "terminee",
          date_fin_reelle: now,
          tps_prep_reel:   tps_prep,
          tps_exec_reel:   tps_exec,
          duree_reelle_min: workedMin,
        })
        .eq("id_op_plan", id_op_plan);
      if (error) throw error;

      // Cascade: check if all ops of the OF are done → OF terminé
      await cascadeOFFinish(supabase, op);

      return ok({
        action:          "finish",
        id_op_plan,
        finished_at:     now,
        worked_min:      workedMin,
        pauses_min:      pausesMin,
        tps_prep_reel:   tps_prep,
        tps_exec_reel:   tps_exec,
      });
    }

    return err400("Unknown action.");

  } catch (err) {
    return new Response(
      JSON.stringify({ ok: false, error: String(err) }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 500 }
    );
  }
});


// ── Helpers ─────────────────────────────────────────────────────────────────

function ok(data: object) {
  return new Response(
    JSON.stringify({ ok: true, ...data }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 200 }
  );
}
function err400(msg: string) {
  return new Response(
    JSON.stringify({ ok: false, error: msg }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 400 }
  );
}
function err404(msg: string) {
  return new Response(
    JSON.stringify({ ok: false, error: msg }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 404 }
  );
}
function err409(msg: string) {
  return new Response(
    JSON.stringify({ ok: false, error: msg }),
    { headers: { ...corsHeaders, "Content-Type": "application/json" }, status: 409 }
  );
}

async function getOpenPause(supabase: any, id_op_plan: number) {
  const { data } = await supabase
    .from("pausepointage")
    .select("id_pause, debut_pause")
    .eq("id_op_plan", id_op_plan)
    .is("fin_pause", null)
    .single();
  return data ?? null;
}

async function closeOpenPause(supabase: any, id_op_plan: number, now: string) {
  const pause = await getOpenPause(supabase, id_op_plan);
  if (!pause) return;
  const duree_min = Math.max(
    1,
    Math.round((new Date(now).getTime() - new Date(pause.debut_pause).getTime()) / 60000)
  );
  await supabase
    .from("pausepointage")
    .update({ fin_pause: now, duree_min })
    .eq("id_pause", pause.id_pause);
}

async function getTotalPausesMin(supabase: any, id_op_plan: number): Promise<number> {
  const { data } = await supabase
    .from("pausepointage")
    .select("duree_min")
    .eq("id_op_plan", id_op_plan)
    .not("fin_pause", "is", null);
  return (data ?? []).reduce((sum: number, p: any) => sum + (p.duree_min ?? 0), 0);
}

async function cascadeOFStart(supabase: any, op: any) {
  const of = op.of;
  if (!of) return;
  if (["a_planifier", "planifie"].includes(of.statut)) {
    await supabase
      .from("ordrefabrication")
      .update({ statut: "en_cours" })
      .eq("id_of", of.id_of);

    if (of.ofassemblage?.statut === "planifie") {
      await supabase
        .from("ofassemblage")
        .update({ statut: "en_cours" })
        .eq("id_of_assemblage", of.id_of_assemblage);
    }
  }
}

async function cascadeOFFinish(supabase: any, op: any) {
  const of = op.of;
  if (!of) return;

  // Count remaining non-finished operations for this OF
  const { count } = await supabase
    .from("operationplanifiee")
    .select("id_op_plan", { count: "exact", head: true })
    .eq("id_of", of.id_of)
    .not("statut", "in", '("terminee","rebutee")');

  if ((count ?? 1) === 0) {
    const now = new Date().toISOString();
    await supabase
      .from("ordrefabrication")
      .update({ statut: "termine", date_fin_reelle: now })
      .eq("id_of", of.id_of);

    // Check if all OFs of the OFAssemblage are done
    if (of.id_of_assemblage) {
      const { count: remaining } = await supabase
        .from("ordrefabrication")
        .select("id_of", { count: "exact", head: true })
        .eq("id_of_assemblage", of.id_of_assemblage)
        .not("statut", "in", '("termine","rebute","annule")');

      if ((remaining ?? 1) === 0) {
        await supabase
          .from("ofassemblage")
          .update({ statut: "termine" })
          .eq("id_of_assemblage", of.id_of_assemblage);
      }
    }
  }
}
