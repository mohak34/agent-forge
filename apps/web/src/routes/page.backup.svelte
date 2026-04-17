<script lang="ts">
  import { onMount } from "svelte";
  import {
    createRun,
    createTemplate,
    decideApproval,
    exportTemplate,
    getRun,
    getRunTasks,
    getRunTimeline,
    getTools,
    importTemplate,
    listApprovals,
    listMemory,
    listTemplates,
    runFromTemplate
  } from "../lib/api";

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

  type AgentTemplate = {
    id: string;
    name: string;
    description: string;
    version: string;
    config_json: string;
    is_builtin: boolean;
    created_at: string;
    updated_at: string;
  };

  type Mode = "simple" | "power";

  const statusTone: Record<string, string> = {
    queued: "bg-slate-100 text-slate-700",
    running: "bg-sky-100 text-sky-700",
    waiting_approval: "bg-amber-100 text-amber-700",
    completed: "bg-emerald-100 text-emerald-700",
    failed: "bg-rose-100 text-rose-700"
  };

  const runPresets: string[] = [
    "Summarize the Transformers paper and explain why it changed NLP.",
    "Compare three open-source agent orchestration frameworks and recommend one for a startup team.",
    "Create an implementation checklist for shipping a safe research assistant MVP in two weeks."
  ];

  let mode: Mode = "simple";
  let goal = runPresets[0] || "";
  let run: RunResponse | null = null;
  let timeline: TimelineEvent[] = [];
  let tasks: TaskNode[] = [];
  let tools: ToolInfo[] = [];
  let approvals: ApprovalItem[] = [];
  let memoryItems: MemoryItem[] = [];
  let templates: AgentTemplate[] = [];

  let loading = false;
  let sidebarLoading = false;
  let error = "";
  let approvalPollId: ReturnType<typeof setInterval> | null = null;

  let memoryEnabled = false;
  let selectedTemplateId = "";

  let templateName = "Research Team";
  let templateDescription = "Reusable research-oriented orchestration settings";
  let templateVersion = "1.0.0";
  let templateConfigJson = '{"goal_prefix":"Use a research-first workflow with concise structured output."}';
  let exportedTemplateJson = "";

  function asTemplate(value: unknown): AgentTemplate {
    return value as AgentTemplate;
  }

  function asTask(value: unknown): TaskNode {
    return value as TaskNode;
  }

  function asEvent(value: unknown): TimelineEvent {
    return value as TimelineEvent;
  }

  function asApproval(value: unknown): ApprovalItem {
    return value as ApprovalItem;
  }

  function asTool(value: unknown): ToolInfo {
    return value as ToolInfo;
  }

  function asMemory(value: unknown): MemoryItem {
    return value as MemoryItem;
  }

  function asPreset(value: unknown): string {
    return String(value);
  }

  function runStatusClass(status: string) {
    return statusTone[status] || "bg-slate-100 text-slate-700";
  }

  function setPreset(value: string) {
    goal = value;
  }

  async function refreshRunState(runId: string) {
    run = (await getRun(runId)) as RunResponse;
    timeline = (await getRunTimeline(runId)) as TimelineEvent[];
    tasks = (await getRunTasks(runId)) as TaskNode[];
    await loadApprovals();
    await loadMemory();
    updateApprovalPolling();
  }

  async function submitGoal() {
    if (!goal.trim()) {
      return;
    }
    loading = true;
    error = "";
    timeline = [];
    tasks = [];

    try {
      const createdRun = (await createRun(goal, memoryEnabled)) as RunResponse;
      await refreshRunState(createdRun.id);
    } catch (e) {
      error = e instanceof Error ? e.message : "Unknown error";
    } finally {
      loading = false;
    }
  }

  async function submitGoalWithTemplate() {
    if (!selectedTemplateId || !goal.trim()) {
      error = "Select a template and enter a goal first";
      return;
    }
    loading = true;
    error = "";

    try {
      const createdRun = (await runFromTemplate(selectedTemplateId, goal, memoryEnabled)) as RunResponse;
      await refreshRunState(createdRun.id);
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to run with template";
    } finally {
      loading = false;
    }
  }

  async function loadTools() {
    try {
      tools = (await getTools()) as ToolInfo[];
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load tools";
    }
  }

  async function loadApprovals() {
    try {
      approvals = (await listApprovals()) as ApprovalItem[];
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

  async function loadTemplates() {
    try {
      templates = (await listTemplates()) as AgentTemplate[];
      if (!selectedTemplateId && templates.length > 0) {
        selectedTemplateId = templates[0].id;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to load templates";
    }
  }

  async function refreshSidebarData() {
    sidebarLoading = true;
    await Promise.all([loadTools(), loadApprovals(), loadMemory(), loadTemplates()]);
    sidebarLoading = false;
  }

  async function createTemplateItem() {
    try {
      await createTemplate(templateName, templateDescription, templateVersion, templateConfigJson);
      await loadTemplates();
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to create template";
    }
  }

  async function importTemplateItem() {
    try {
      await importTemplate(templateName, templateDescription, templateVersion, templateConfigJson);
      await loadTemplates();
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to import template";
    }
  }

  async function exportSelectedTemplate() {
    if (!selectedTemplateId) {
      error = "Select a template first";
      return;
    }
    try {
      const data = await exportTemplate(selectedTemplateId);
      exportedTemplateJson = JSON.stringify(data, null, 2);
    } catch (e) {
      error = e instanceof Error ? e.message : "Failed to export template";
    }
  }

  async function decide(approvalId: string, decision: "approve" | "reject") {
    try {
      await decideApproval(approvalId, decision, "manual decision from dashboard");
      if (run) {
        await refreshRunState(run.id);
      } else {
        await loadApprovals();
      }
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
      if (!run?.id) {
        return;
      }
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
    }, 5000);
  }

  onMount(() => {
    refreshSidebarData();
    return () => {
      stopApprovalPolling();
    };
  });
</script>

<main class="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 p-6 md:p-10">
  <section class="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div>
        <p class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">agent-forge</p>
        <h1 class="mt-1 text-3xl font-semibold text-slate-900">Run multi-step research with less noise</h1>
        <p class="mt-2 max-w-2xl text-sm text-slate-600">
          Pick a template, describe your goal, and get a structured result with timeline visibility. Advanced controls stay hidden unless you switch to Power mode.
        </p>
      </div>
      <div class="inline-flex rounded-xl border border-slate-300 bg-slate-50 p-1 text-sm">
        <button
          class={`rounded-lg px-3 py-1.5 transition ${
            mode === "simple" ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900"
          }`}
          on:click={() => (mode = "simple")}
          type="button"
        >
          Simple
        </button>
        <button
          class={`rounded-lg px-3 py-1.5 transition ${
            mode === "power" ? "bg-slate-900 text-white" : "text-slate-600 hover:text-slate-900"
          }`}
          on:click={() => (mode = "power")}
          type="button"
        >
          Power
        </button>
      </div>
    </div>

    <div class="mt-5 grid gap-4 md:grid-cols-[1.25fr_0.75fr]">
      <div class="space-y-3">
        <label class="text-sm font-medium text-slate-700" for="goal">Goal</label>
        <textarea
          id="goal"
          bind:value={goal}
          class="min-h-32 w-full rounded-xl border border-slate-300 bg-slate-50 p-3 text-sm text-slate-900 outline-none ring-sky-300 transition focus:ring"
          placeholder="Describe what you want the agent team to produce"
        ></textarea>
        <div class="flex flex-wrap gap-2">
          {#each runPresets as preset}
            {@const value = asPreset(preset)}
            <button
              class="rounded-full border border-slate-300 bg-white px-3 py-1 text-xs text-slate-700 transition hover:border-slate-500"
              on:click={() => setPreset(value)}
              type="button"
            >
              {value}
            </button>
          {/each}
        </div>
      </div>

      <div class="space-y-3 rounded-xl border border-slate-200 bg-slate-50 p-4">
        <label class="text-sm font-medium text-slate-700" for="template">Template</label>
        <select
          id="template"
          class="w-full rounded-lg border border-slate-300 bg-white p-2 text-sm"
          bind:value={selectedTemplateId}
        >
          <option value="">Select template</option>
          {#each templates as template}
            {@const item = asTemplate(template)}
            <option value={item.id}>{item.name} ({item.version})</option>
          {/each}
        </select>
        <label class="flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" bind:checked={memoryEnabled} />
          Enable persistent memory
        </label>
        <div class="flex flex-wrap gap-2 pt-1">
          <button
            class="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
            on:click={submitGoalWithTemplate}
            disabled={loading || !goal.trim() || !selectedTemplateId}
            type="button"
          >
            {loading ? "Running..." : "Run with Template"}
          </button>
          <button
            class="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
            on:click={submitGoal}
            disabled={loading || !goal.trim()}
            type="button"
          >
            Quick Run
          </button>
        </div>
      </div>
    </div>

    {#if error}
      <p class="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p>
    {/if}
  </section>

  {#if run}
    <section class="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <div class="space-y-4">
        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <h2 class="text-lg font-semibold text-slate-900">Latest Result</h2>
            <span class={`rounded-full px-3 py-1 text-xs font-medium ${runStatusClass(run.status)}`}>
              {run.status}
            </span>
          </div>
          <p class="mt-2 text-xs text-slate-500">Run ID: {run.id}</p>
          <p class="mt-4 whitespace-pre-wrap text-sm leading-6 text-slate-800">{run.output_text || "Run is in progress."}</p>
        </article>

        {#if mode === "power"}
          <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 class="text-base font-semibold text-slate-900">Run Details</h3>
            <div class="mt-3 grid gap-2 text-sm text-slate-700 md:grid-cols-2">
              <p><span class="font-medium">Goal:</span> {run.goal}</p>
              <p><span class="font-medium">Memory:</span> {run.memory_enabled ? "enabled" : "disabled"}</p>
              <p><span class="font-medium">Provider:</span> {run.provider || "n/a"}</p>
              <p><span class="font-medium">Model:</span> {run.model || "n/a"}</p>
              <p><span class="font-medium">Token estimate:</span> {run.token_estimate}</p>
              <p><span class="font-medium">Budget limit:</span> ${run.budget_limit_usd.toFixed(4)}</p>
              <p><span class="font-medium">Budget used:</span> ${run.budget_used_usd.toFixed(4)}</p>
              <p><span class="font-medium">Budget exceeded:</span> {run.budget_exceeded ? "yes" : "no"}</p>
            </div>
          </article>

          <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 class="text-base font-semibold text-slate-900">Task Graph</h3>
            <ul class="mt-3 space-y-2">
              {#each tasks as task}
                {@const item = asTask(task)}
                <li class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                  <p class="font-medium text-slate-900">{item.sequence}. {item.title}</p>
                  <p class="text-slate-600">kind={item.kind} depends_on={item.depends_on || "none"}</p>
                  <p class="text-slate-600">route={item.routed_provider || "n/a"}/{item.routed_model || "n/a"}</p>
                  <p class="mt-1 text-xs text-slate-500">status={item.status}</p>
                </li>
              {/each}
            </ul>
          </article>

          <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 class="text-base font-semibold text-slate-900">Timeline</h3>
            <ul class="mt-3 space-y-2">
              {#each timeline as event}
                {@const item = asEvent(event)}
                <li class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                  <p class="font-medium text-slate-900">{item.event_type}</p>
                  <p class="text-slate-600">{item.detail}</p>
                  <p class="mt-1 text-xs text-slate-500">{item.actor} · {item.status}</p>
                </li>
              {/each}
            </ul>
          </article>
        {/if}
      </div>

      <aside class="space-y-4">
        <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div class="flex items-center justify-between gap-2">
            <h3 class="text-base font-semibold text-slate-900">Approvals</h3>
            <button
              class="rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-700"
              on:click={refreshSidebarData}
              type="button"
            >
              {sidebarLoading ? "Refreshing..." : "Refresh"}
            </button>
          </div>
          {#if approvals.length === 0}
            <p class="mt-3 text-sm text-slate-600">No pending approvals.</p>
          {:else}
            <ul class="mt-3 space-y-2">
              {#each approvals as approval}
                {@const item = asApproval(approval)}
                <li class="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm">
                  <p class="font-medium text-amber-900">{item.action_type}</p>
                  <p class="mt-1 text-amber-800">{item.reason}</p>
                  <div class="mt-3 flex gap-2">
                    <button
                      class="rounded bg-emerald-700 px-3 py-1 text-xs font-medium text-white"
                      on:click={() => decide(item.id, "approve")}
                      type="button"
                    >
                      Approve
                    </button>
                    <button
                      class="rounded bg-rose-700 px-3 py-1 text-xs font-medium text-white"
                      on:click={() => decide(item.id, "reject")}
                      type="button"
                    >
                      Reject
                    </button>
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        </article>

        {#if mode === "power"}
          <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 class="text-base font-semibold text-slate-900">Tools</h3>
            <ul class="mt-3 space-y-2">
              {#each tools as tool}
                {@const item = asTool(tool)}
                <li class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                  <p class="font-medium text-slate-900">{item.name}</p>
                  <p class="text-slate-600">{item.description}</p>
                  <p class="mt-1 text-xs text-slate-500">risk={item.risk_level}</p>
                </li>
              {/each}
            </ul>
          </article>

          <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 class="text-base font-semibold text-slate-900">Memory</h3>
            {#if memoryItems.length === 0}
              <p class="mt-3 text-sm text-slate-600">No memory items yet.</p>
            {:else}
              <ul class="mt-3 space-y-2">
                {#each memoryItems as memory}
                  {@const item = asMemory(memory)}
                  <li class="rounded-lg border border-slate-200 bg-slate-50 p-3 text-sm">
                    <p class="font-medium text-slate-900">{item.kind}</p>
                    <p class="text-slate-600">{item.content}</p>
                  </li>
                {/each}
              </ul>
            {/if}
          </article>

          <article class="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 class="text-base font-semibold text-slate-900">Template Admin</h3>
            <div class="mt-3 grid gap-2 text-sm">
              <input class="rounded border border-slate-300 p-2" bind:value={templateName} placeholder="Template name" />
              <input
                class="rounded border border-slate-300 p-2"
                bind:value={templateDescription}
                placeholder="Template description"
              />
              <input class="rounded border border-slate-300 p-2" bind:value={templateVersion} placeholder="Version" />
              <textarea class="rounded border border-slate-300 p-2" bind:value={templateConfigJson}></textarea>
              <div class="flex flex-wrap gap-2">
                <button class="rounded bg-slate-900 px-3 py-2 text-white" on:click={createTemplateItem} type="button"
                  >Save</button>
                <button class="rounded bg-slate-700 px-3 py-2 text-white" on:click={importTemplateItem} type="button"
                  >Import</button>
                <button class="rounded bg-slate-600 px-3 py-2 text-white" on:click={exportSelectedTemplate} type="button"
                  >Export</button>
              </div>
              {#if exportedTemplateJson}
                <textarea class="rounded border border-slate-300 p-2 font-mono text-xs" readonly value={exportedTemplateJson}></textarea>
              {/if}
            </div>
          </article>
        {/if}
      </aside>
    </section>
  {/if}
</main>
