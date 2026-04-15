<script lang="ts">
  import { onMount } from "svelte";
  import { createRun, getRun, getRunTasks, getRunTimeline, listMemory } from "../lib/api";

  type RunResponse = {
    id: string;
    goal: string;
    memory_enabled: boolean;
    status: string;
    budget_limit_usd: number;
    budget_used_usd: number;
    budget_exceeded: boolean;
    provider: string;
    model: string;
    output_text: string;
    token_estimate: number;
    created_at: string;
    updated_at: string;
  };

  type TimelineEvent = {
    id: string;
    run_id: string;
    event_type: string;
    actor: string;
    status: string;
    detail: string;
    created_at: string;
  };

  type TaskNode = {
    id: string;
    run_id: string;
    title: string;
    kind: string;
    sequence: number;
    depends_on: string;
    routed_provider: string;
    routed_model: string;
    token_estimate: number;
    cost_estimate_usd: number;
    status: string;
    output_text: string;
    created_at: string;
    updated_at: string;
  };

  type ToolInfo = {
    name: string;
    description: string;
    risk_level: string;
  };

  type ApprovalItem = {
    id: string;
    run_id: string;
    action_type: string;
    reason: string;
    payload: string;
    status: string;
    decision_reason: string;
    created_at: string;
    updated_at: string;
  };

  type MemoryItem = {
    id: string;
    scope_key: string;
    run_id: string;
    kind: string;
    content: string;
    created_at: string;
  };

  let goal = "Research top 5 competitors and provide a summary table.";
  let run: RunResponse | null = null;
  let timeline: any[] = [];
  let tasks: any[] = [];
  let tools: any[] = [];
  let approvals: any[] = [];
  let loading = false;
  let error = "";
  let approvalPollId: ReturnType<typeof setInterval> | null = null;
  let memoryEnabled = false;
  let memoryItems: any[] = [];

  function asTimelineEvent(value: any): TimelineEvent {
    return value as TimelineEvent;
  }

  function asTaskNode(value: any): TaskNode {
    return value as TaskNode;
  }

  function asToolInfo(value: any): ToolInfo {
    return value as ToolInfo;
  }

  function asApprovalItem(value: any): ApprovalItem {
    return value as ApprovalItem;
  }

  function asMemoryItem(value: any): MemoryItem {
    return value as MemoryItem;
  }

  async function submitGoal() {
    loading = true;
    error = "";
    timeline = [];
    tasks = [];

    try {
      const createdRun = (await createRun(goal, memoryEnabled)) as RunResponse;
      run = createdRun;
      timeline = (await getRunTimeline(createdRun.id)) as TimelineEvent[];
      tasks = (await getRunTasks(createdRun.id)) as TaskNode[];
      await loadApprovals();
      await loadMemory();
      updateApprovalPolling();
    } catch (e) {
      error = e instanceof Error ? e.message : "Unknown error";
    } finally {
      loading = false;
    }
  }

  async function loadTools() {
    try {
      const response = await fetch("http://localhost:8000/api/v0/tools");
      if (!response.ok) {
        throw new Error("Failed to fetch tools");
      }
      tools = (await response.json()) as ToolInfo[];
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load tools";
    }
  }

  async function loadApprovals() {
    try {
      const response = await fetch("http://localhost:8000/api/v0/approvals");
      if (!response.ok) {
        throw new Error("Failed to fetch approvals");
      }
      approvals = (await response.json()) as ApprovalItem[];
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load approvals";
    }
  }

  async function loadMemory() {
    try {
      memoryItems = (await listMemory()) as MemoryItem[];
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load memory";
    }
  }

  async function decide(approvalId: string, decision: "approve" | "reject") {
    try {
      const response = await fetch(`http://localhost:8000/api/v0/approvals/${approvalId}/decision`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ decision, reason: "manual decision from dashboard" })
      });
      if (!response.ok) {
        throw new Error("Failed to submit approval decision");
      }
      if (run) {
        run = (await getRun(run.id)) as RunResponse;
      }
      if (run?.id) {
        timeline = (await getRunTimeline(run.id)) as TimelineEvent[];
        tasks = (await getRunTasks(run.id)) as TaskNode[];
      }
      await loadApprovals();
      await loadMemory();
      updateApprovalPolling();
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to submit approval decision";
    }
  }

  function stopApprovalPolling() {
    if (approvalPollId) {
      clearInterval(approvalPollId);
      approvalPollId = null;
    }
  }

  function updateApprovalPolling() {
    stopApprovalPolling();
    if (run?.status !== "waiting_approval") {
      return;
    }
    approvalPollId = setInterval(async () => {
      await loadApprovals();
      if (run?.id) {
        try {
          run = (await getRun(run.id)) as RunResponse;
          if (run.status !== "waiting_approval") {
            timeline = (await getRunTimeline(run.id)) as TimelineEvent[];
            tasks = (await getRunTasks(run.id)) as TaskNode[];
            stopApprovalPolling();
          }
        } catch {
          stopApprovalPolling();
        }
      }
    }, 5000);
  }

  onMount(() => {
    loadTools();
    loadApprovals();
    loadMemory();

    return () => {
      stopApprovalPolling();
    };
  });
</script>

<main class="mx-auto flex min-h-screen w-full max-w-5xl flex-col gap-6 p-6 md:p-10">
  <section class="rounded-xl border border-slate-200 bg-white/80 p-6 shadow-sm backdrop-blur">
    <h1 class="text-2xl font-semibold">agent-forge</h1>
    <p class="mt-2 text-sm text-slate-600">
      Phase E baseline: goal intake, specialist orchestration, tools, policy checks, and timeline.
    </p>
    <div class="mt-4 flex flex-col gap-3">
      <textarea
        bind:value={goal}
        class="min-h-28 rounded-lg border border-slate-300 p-3 text-sm outline-none ring-blue-300 focus:ring"
      ></textarea>
      <button
        class="w-fit rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        on:click={submitGoal}
        disabled={loading || !goal.trim()}
      >
        {loading ? "Running..." : "Create Run"}
      </button>
      <label class="flex items-center gap-2 text-sm text-slate-700">
        <input type="checkbox" bind:checked={memoryEnabled} />
        Enable persistent memory for this run
      </label>
      {#if error}
        <p class="text-sm text-red-600">{error}</p>
      {/if}
    </div>
  </section>

  {#if run}
    <section class="rounded-xl border border-slate-200 bg-white/90 p-6 shadow-sm">
      <h2 class="text-lg font-semibold">Run</h2>
      <div class="mt-3 grid gap-2 text-sm text-slate-700">
        <p><span class="font-medium">ID:</span> {run.id}</p>
        <p><span class="font-medium">Status:</span> {run.status}</p>
        <p><span class="font-medium">Memory enabled:</span> {run.memory_enabled ? "yes" : "no"}</p>
        <p><span class="font-medium">Budget limit:</span> ${run.budget_limit_usd.toFixed(4)}</p>
        <p><span class="font-medium">Budget used:</span> ${run.budget_used_usd.toFixed(4)}</p>
        <p><span class="font-medium">Budget exceeded:</span> {run.budget_exceeded ? "yes" : "no"}</p>
        <p><span class="font-medium">Provider:</span> {run.provider || "n/a"}</p>
        <p><span class="font-medium">Model:</span> {run.model || "n/a"}</p>
        <p><span class="font-medium">Token estimate:</span> {run.token_estimate}</p>
        <p><span class="font-medium">Goal:</span> {run.goal}</p>
        <p><span class="font-medium">Output:</span> {run.output_text || "No output"}</p>
      </div>
    </section>

    <section class="rounded-xl border border-slate-200 bg-white/90 p-6 shadow-sm">
      <h2 class="text-lg font-semibold">Timeline</h2>
      <ul class="mt-3 space-y-3">
        {#each timeline as event}
          {@const item = asTimelineEvent(event)}
          <li class="rounded-lg border border-slate-200 p-3 text-sm">
            <p class="font-medium">{item.event_type}</p>
            <p class="text-slate-600">{item.detail}</p>
            <p class="mt-1 text-xs text-slate-500">{item.actor} · {item.status}</p>
          </li>
        {/each}
      </ul>
    </section>

    <section class="rounded-xl border border-slate-200 bg-white/90 p-6 shadow-sm">
      <h2 class="text-lg font-semibold">Task Graph</h2>
      <ul class="mt-3 space-y-3">
        {#each tasks as node}
          {@const item = asTaskNode(node)}
          <li class="rounded-lg border border-slate-200 p-3 text-sm">
            <p class="font-medium">{item.sequence}. {item.title}</p>
            <p class="text-slate-600">kind={item.kind} depends_on={item.depends_on || "none"}</p>
            <p class="text-slate-600">
              route={item.routed_provider || "n/a"}/{item.routed_model || "n/a"}
            </p>
            <p class="text-slate-600">
              est_tokens={item.token_estimate} est_cost=${item.cost_estimate_usd.toFixed(6)}
            </p>
            <p class="mt-1 text-xs text-slate-500">status={item.status}</p>
          </li>
        {/each}
      </ul>
    </section>

    <section class="rounded-xl border border-slate-200 bg-white/90 p-6 shadow-sm">
      <h2 class="text-lg font-semibold">Tools</h2>
      <ul class="mt-3 space-y-3">
        {#each tools as tool}
          {@const item = asToolInfo(tool)}
          <li class="rounded-lg border border-slate-200 p-3 text-sm">
            <p class="font-medium">{item.name}</p>
            <p class="text-slate-600">{item.description}</p>
            <p class="mt-1 text-xs text-slate-500">risk={item.risk_level}</p>
          </li>
        {/each}
      </ul>
    </section>

    <section class="rounded-xl border border-slate-200 bg-white/90 p-6 shadow-sm">
      <h2 class="text-lg font-semibold">Approval Inbox</h2>
      <ul class="mt-3 space-y-3">
        {#if approvals.length === 0}
          <li class="rounded-lg border border-slate-200 p-3 text-sm text-slate-600">No pending approvals.</li>
        {:else}
          {#each approvals as approval}
            {@const item = asApprovalItem(approval)}
            <li class="rounded-lg border border-slate-200 p-3 text-sm">
              <p class="font-medium">{item.action_type}</p>
              <p class="text-slate-600">{item.reason}</p>
              <p class="mt-1 text-xs text-slate-500">run={item.run_id}</p>
              <div class="mt-2 flex gap-2">
                <button
                  class="rounded bg-emerald-700 px-3 py-1 text-xs font-medium text-white"
                  on:click={() => decide(item.id, "approve")}
                >
                  Approve
                </button>
                <button
                  class="rounded bg-rose-700 px-3 py-1 text-xs font-medium text-white"
                  on:click={() => decide(item.id, "reject")}
                >
                  Reject
                </button>
              </div>
            </li>
          {/each}
        {/if}
      </ul>
    </section>

    <section class="rounded-xl border border-slate-200 bg-white/90 p-6 shadow-sm">
      <h2 class="text-lg font-semibold">Memory</h2>
      <ul class="mt-3 space-y-3">
        {#if memoryItems.length === 0}
          <li class="rounded-lg border border-slate-200 p-3 text-sm text-slate-600">No memory items yet.</li>
        {:else}
          {#each memoryItems as memory}
            {@const item = asMemoryItem(memory)}
            <li class="rounded-lg border border-slate-200 p-3 text-sm">
              <p class="font-medium">{item.kind}</p>
              <p class="text-slate-600">{item.content}</p>
              <p class="mt-1 text-xs text-slate-500">scope={item.scope_key} run={item.run_id}</p>
            </li>
          {/each}
        {/if}
      </ul>
    </section>
  {/if}
</main>
