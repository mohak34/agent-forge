<script lang="ts">
  import { onMount, tick } from "svelte";
  import {
    createThread,
    decideApproval,
    getRun,
    getRunTasks,
    getRunTimeline,
    getThread,
    listApprovals,
    listTemplates,
    listThreads,
    sendThreadMessage,
    streamRunEvents,
    type ChatMessage,
    type ChatThread
  } from "$lib/api";
  import { parseMarkdown } from "$lib/markdown";
  import { cn } from "$lib/utils";

  import Badge from "$lib/components/Badge.svelte";
  import Button from "$lib/components/Button.svelte";
  import TaskGraphNode from "$lib/components/TaskGraphNode.svelte";
  import AgentTimelineItem from "$lib/components/AgentTimelineItem.svelte";
  import ApprovalGateCard from "$lib/components/ApprovalGateCard.svelte";

  type RunDetail = {
    id: string;
    goal: string;
    status: string;
    provider: string;
    model: string;
    output_text: string;
    budget_limit_usd: number;
    budget_used_usd: number;
    token_estimate: number;
  };

  let mode = $state<"simple" | "power">("power");
  let historySidebarOpen = $state(true);
  let rightSidebarOpen = $state(true);

  let threads = $state<ChatThread[]>([]);
  let activeThreadId = $state<string | null>(null);
  let messages = $state<ChatMessage[]>([]);
  let selectedRunId = $state<string | null>(null);

  let run = $state<RunDetail | null>(null);
  let timeline = $state<any[]>([]);
  let tasks = $state<any[]>([]);
  let approvals = $state<any[]>([]);

  let templates = $state<any[]>([]);
  let selectedTemplateId = $state("");
  let memoryEnabled = $state(false);
  let routeMode = $state<"auto" | "direct" | "orchestrated">("auto");

  let input = $state("");
  let loading = $state(false);
  let error = $state("");
  let activeTab = $state<"overview" | "graph" | "traceability">("overview");

  let streamingRunId = $state<string | null>(null);
  let streamingStatus = $state<string>("");
  let streamingMessages = $state<ChatMessage[]>([]);

  let chatFeedRef = $state<HTMLElement | null>(null);
  let approvalPollId: ReturnType<typeof setInterval> | null = null;

  let isWaitingApproval = $derived(run?.status === "waiting_approval");
  let latestRunApprovals = $derived(
    approvals.filter((item) => (selectedRunId ? item.run_id === selectedRunId : true))
  );

  function summarize(text: string) {
    const trimmed = (text || "").trim();
    if (!trimmed) return "New chat";
    if (trimmed.length <= 44) return trimmed;
    return `${trimmed.slice(0, 44)}...`;
  }

  function inferRunIdFromMessages(messageList: ChatMessage[]): string | null {
    for (let i = messageList.length - 1; i >= 0; i -= 1) {
      if (messageList[i].run_id) {
        return messageList[i].run_id;
      }
    }
    return null;
  }

  async function scrollToBottom() {
    await tick();
    if (chatFeedRef) {
      chatFeedRef.scrollTop = chatFeedRef.scrollHeight;
    }
  }

  async function loadThreads() {
    threads = await listThreads(75);
  }

  async function refreshRunPanels(runId: string | null) {
    stopApprovalPolling();
    if (!runId) {
      run = null;
      timeline = [];
      tasks = [];
      approvals = await listApprovals();
      return;
    }

    run = (await getRun(runId)) as RunDetail;
    timeline = await getRunTimeline(runId);
    tasks = await getRunTasks(runId);
    approvals = await listApprovals();
    updateApprovalPolling();
  }

  async function openThread(threadId: string) {
    error = "";
    activeThreadId = threadId;
    const detail = await getThread(threadId);
    messages = detail.messages;
    selectedRunId = detail.thread.last_run_id || inferRunIdFromMessages(detail.messages);
    await refreshRunPanels(selectedRunId);
    await scrollToBottom();
  }

  async function startNewChat() {
    error = "";
    const created = await createThread("New chat", memoryEnabled, selectedTemplateId || null);
    await loadThreads();
    await openThread(created.id);
  }

  async function submitMessage() {
    if (!input.trim()) return;
    loading = true;
    error = "";

    let threadId = activeThreadId;
    let sentContent = input;

    try {
      if (!threadId) {
        const created = await createThread(summarize(input), memoryEnabled, selectedTemplateId || null);
        threadId = created.id;
      }

      // Immediately show user message
      const userMsg: ChatMessage = {
        id: "temp-user-" + Date.now(),
        thread_id: threadId,
        role: "user",
        content: sentContent,
        turn_index: messages.length + 1,
        run_id: null,
        created_at: new Date().toISOString(),
      };
      messages = [...messages, userMsg];
      input = "";
      await scrollToBottom();

      const turn = await sendThreadMessage(threadId, sentContent, routeMode);
      activeThreadId = threadId;
      const threadDetail = await getThread(threadId);
      const runId = (turn.run?.id as string | undefined) || threadDetail.thread.last_run_id;

      if (runId) {
        streamingRunId = runId;
        streamingStatus = "Thinking...";

        streamRunEvents(runId, (event) => {
          if (event.event_type === "plan.generated") {
            streamingStatus = "Planning task graph...";
          } else if (event.event_type === "task.assigned") {
            streamingStatus = `Working on: ${event.detail}`;
          } else if (event.event_type === "tool.invoked") {
            if (event.detail.includes("research")) {
              streamingStatus = "Research agent: searching web...";
            } else if (event.detail.includes("search_web")) {
              streamingStatus = "Searching web...";
            } else if (event.detail.includes("fetch_url")) {
              streamingStatus = "Fetching sources...";
            }
          } else if (event.event_type === "tool.completed") {
            streamingStatus = "Analyzing sources...";
          } else if (event.event_type === "model.routed") {
            streamingStatus = "Processing with AI model...";
          } else if (event.event_type === "run.output") {
            streamingStatus = "Finalizing answer...";
          }
        }, async () => {
          streamingRunId = null;
          streamingStatus = "";
          await loadThreads();
          const detail = await getThread(threadId);
          messages = detail.messages;
          selectedRunId = runId;
          await refreshRunPanels(selectedRunId);
          await scrollToBottom();
        });
      }

      await loadThreads();
      if (mode === "power") {
        rightSidebarOpen = true;
      }
      await scrollToBottom();
    } catch (e) {
      error = e instanceof Error ? e.message : "Unknown error";
    } finally {
      loading = false;
    }
  }

  async function selectRunFromMessage(runId: string | null) {
    selectedRunId = runId;
    await refreshRunPanels(runId);
  }

  async function handleApprovalDecision(id: string, decision: "approve" | "reject") {
    try {
      await decideApproval(id, decision, "manual decision from dashboard");
      if (selectedRunId) {
        await refreshRunPanels(selectedRunId);
      }
      if (activeThreadId) {
        const detail = await getThread(activeThreadId);
        messages = detail.messages;
      }
      await loadThreads();
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
    if (!selectedRunId || run?.status !== "waiting_approval") {
      return;
    }

    approvalPollId = setInterval(async () => {
      try {
        await refreshRunPanels(selectedRunId);
        if (activeThreadId) {
          const detail = await getThread(activeThreadId);
          messages = detail.messages;
        }
      } catch {
        stopApprovalPolling();
      }
    }, 5000);
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submitMessage();
    }
  }

  onMount(() => {
    (async () => {
      templates = await listTemplates();
      if (templates.length > 0) {
        selectedTemplateId = templates[0].id;
      }
      approvals = await listApprovals();
      await loadThreads();
      if (threads.length > 0) {
        await openThread(threads[0].id);
      }
    })();

    return () => {
      stopApprovalPolling();
    };
  });
</script>

<div class="flex h-screen w-full flex-col bg-background text-foreground font-sans antialiased">
  <header class="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background px-4 lg:px-6">
    <div class="flex items-center gap-3">
      <Button variant="ghost" size="icon" class="h-8 w-8" onclick={() => (historySidebarOpen = !historySidebarOpen)}>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><path d="M3 6h18"/><path d="M3 12h18"/><path d="M3 18h18"/></svg>
      </Button>
      <div class="flex h-6 w-6 items-center justify-center rounded-md bg-foreground">
        <span class="font-mono text-xs font-bold text-background">AF</span>
      </div>
      <h1 class="text-sm font-semibold tracking-wide text-foreground">agent-forge</h1>
    </div>

    <div class="flex items-center gap-4">
      {#if run}
        <div class="hidden lg:flex items-center gap-4 text-xs font-mono">
          <div class="flex flex-col text-right">
            <span class="text-muted-foreground">BUDGET</span>
            <span class="text-foreground font-medium">${run.budget_used_usd.toFixed(4)}</span>
          </div>
          <div class="h-6 w-px bg-border"></div>
          <div class="flex flex-col text-right">
            <span class="text-muted-foreground">TOKENS</span>
            <span class="text-foreground font-medium">{run.token_estimate}</span>
          </div>
        </div>
      {/if}

      <div class="flex rounded-md border border-border bg-card p-0.5 text-xs font-medium shadow-sm">
        <button
          class={`rounded-sm px-3 py-1 transition-colors ${mode === "simple" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
          onclick={() => {
            mode = "simple";
            rightSidebarOpen = false;
          }}
        >Simple</button>
        <button
          class={`rounded-sm px-3 py-1 transition-colors ${mode === "power" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
          onclick={() => {
            mode = "power";
            rightSidebarOpen = true;
          }}
        >Power</button>
      </div>
    </div>
  </header>

  <div class="flex flex-1 overflow-hidden relative">
    {#if historySidebarOpen}
      <aside class="hidden md:flex w-[280px] shrink-0 flex-col border-r border-border bg-card/40">
        <div class="border-b border-border p-3">
          <Button variant="default" class="w-full justify-center" onclick={startNewChat}>New Chat</Button>
        </div>
        <div class="flex-1 overflow-y-auto p-3 space-y-2">
          {#if threads.length === 0}
            <p class="px-2 py-1 text-xs text-muted-foreground">No chats yet.</p>
          {:else}
            {#each threads as thread}
              <button
                class={cn(
                  "w-full rounded-md border px-3 py-2 text-left transition-colors",
                  activeThreadId === thread.id
                    ? "border-zinc-500 bg-zinc-900/70"
                    : "border-border bg-background/50 hover:bg-secondary/40"
                )}
                onclick={() => openThread(thread.id)}
              >
                <div class="truncate text-sm font-medium text-foreground">{summarize(thread.title)}</div>
                <div class="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
                  <span class="uppercase">{thread.last_run_id ? "active" : "new"}</span>
                  <span>{new Date(thread.updated_at).toLocaleDateString()}</span>
                </div>
              </button>
            {/each}
          {/if}
        </div>

        {#if mode === "power"}
          <div class="border-t border-border p-4 space-y-3 bg-background/50">
            <div class="space-y-2">
              <label for="template-select" class="text-xs text-muted-foreground block">Template</label>
              <select
                id="template-select"
                class="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground focus:outline-none"
                bind:value={selectedTemplateId}
              >
                <option value="">Standard Base</option>
                {#each templates as t}
                  <option value={t.id}>{t.name}</option>
                {/each}
              </select>
            </div>
            <label class="flex items-center gap-2 text-xs text-foreground">
              <input type="checkbox" bind:checked={memoryEnabled} /> Persistent memory
            </label>
            <label class="flex items-center gap-2 text-xs text-foreground">
              Route mode
              <select class="rounded border border-border bg-card px-2 py-1 text-xs" bind:value={routeMode}>
                <option value="auto">auto (AI decides)</option>
                <option value="direct">direct (fast)</option>
                <option value="orchestrated">orchestrated (deep)</option>
              </select>
            </label>
          </div>
        {/if}
      </aside>
    {/if}

    <main class="flex-1 flex flex-col relative">
      {#if error}
        <div class="m-4 rounded-md border border-red-500/50 bg-red-500/10 px-4 py-3 text-sm text-red-500">{error}</div>
      {/if}

      <div class="flex-1 overflow-y-auto p-4 lg:p-8 scroll-smooth" bind:this={chatFeedRef}>
        <div class="mx-auto max-w-3xl space-y-8 pb-8">
          {#if messages.length === 0}
            <div class="flex h-[50vh] flex-col items-center justify-center text-center space-y-4 opacity-50">
              <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-card border border-border">
                <span class="font-mono text-xl font-bold">AF</span>
              </div>
              <div>
                <h2 class="text-lg font-medium text-foreground">Welcome to Agent-Forge</h2>
                <p class="text-sm text-muted-foreground mt-1 max-w-sm">Start a chat and send follow-up questions in the same thread.</p>
              </div>
            </div>
          {:else}
            {#each messages as message}
              <div class="flex gap-4">
                <div class={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${message.role === "assistant" ? "bg-primary text-primary-foreground" : "bg-secondary border border-border"}`}>
                  {message.role === "assistant" ? "AF" : "U"}
                </div>
                <div class="mt-1 flex-1 min-w-0 space-y-2">
                  {#if message.role === "assistant"}
                    <div class="prose prose-invert prose-sm max-w-none text-[15px] leading-relaxed text-zinc-300">
                      <div class="whitespace-normal prose-table:block prose-table:overflow-x-auto prose-table:w-full">{@html parseMarkdown(message.content)}</div>
                    </div>
                    {#if message.run_id}
                      <button class="text-xs text-muted-foreground hover:text-foreground" onclick={() => selectRunFromMessage(message.run_id)}>
                        View run details ({message.run_id.slice(0, 8)})
                      </button>
                    {/if}
                  {:else}
                    <p class="text-[15px] font-medium text-foreground leading-relaxed">{message.content}</p>
                  {/if}
                </div>
              </div>
            {/each}

            {#if streamingRunId && streamingStatus}
              <div class="flex gap-4">
                <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold bg-primary text-primary-foreground">
                  AF
                </div>
                <div class="mt-1 flex-1 min-w-0">
                  <div class="flex items-center gap-3 text-sm text-muted-foreground">
                    <span class="relative flex h-2 w-2">
                      <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                      <span class="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                    </span>
                    <span>{streamingStatus}</span>
                  </div>
                </div>
              </div>
            {/if}
          {/if}
        </div>
      </div>

      <div class="p-4 lg:p-6 bg-gradient-to-t from-background via-background/95 to-transparent">
        <div class="mx-auto max-w-3xl relative">
          <div class="relative flex items-end rounded-xl border border-border bg-card shadow-sm focus-within:ring-1 focus-within:ring-zinc-600">
            <textarea
              bind:value={input}
              onkeydown={handleKeydown}
              class="max-h-[200px] min-h-[60px] w-full resize-none bg-transparent px-4 py-4 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none"
              placeholder="Ask follow-up questions in the same chat... (Shift+Enter newline)"
              disabled={loading}
            ></textarea>

            <div class="flex items-center gap-2 p-3 pb-3 shrink-0">
              <Button
                variant={loading || !input.trim() ? "secondary" : "default"}
                size="icon"
                class="h-8 w-8 rounded-lg"
                onclick={submitMessage}
                disabled={loading || !input.trim()}
              >
                {#if loading}
                  <span class="h-3 w-3 rounded-sm bg-current animate-pulse"></span>
                {:else}
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>
                {/if}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </main>

    {#if rightSidebarOpen}
      <aside class="absolute inset-y-0 right-0 z-20 w-full flex flex-col border-l border-border bg-card shadow-xl sm:w-[380px] lg:static lg:z-0">
        <div class="flex items-center justify-between border-b border-border p-2">
          <div class="flex gap-1 p-1">
            {#each ["overview", "graph", "traceability"] as tab}
              <button
                class={cn(
                  "rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors",
                  activeTab === tab ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                )}
                onclick={() => (activeTab = tab as "overview" | "graph" | "traceability")}
              >
                {tab}
              </button>
            {/each}
          </div>
          <Button variant="ghost" size="icon" class="h-8 w-8 lg:hidden" onclick={() => (rightSidebarOpen = false)}>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
          </Button>
        </div>

        <div class="flex-1 overflow-y-auto overflow-x-hidden p-4">
          {#if activeTab === "overview"}
            <div class="space-y-6">
              {#if isWaitingApproval || latestRunApprovals.length > 0}
                <div class="space-y-3">
                  <h3 class="text-xs font-bold tracking-widest text-muted-foreground uppercase">Action Center</h3>
                  <div class="space-y-3">
                    {#each latestRunApprovals as approval}
                      {#if approval.status === "pending"}
                        <ApprovalGateCard approval={approval} onDecide={handleApprovalDecision} />
                      {:else}
                        <div class="flex justify-between items-center rounded-md border border-border bg-background p-3 text-sm">
                          <span class="text-muted-foreground">Action: {approval.action_type}</span>
                          <Badge variant={approval.status === "approved" ? "success" : "destructive"}>{approval.status}</Badge>
                        </div>
                      {/if}
                    {/each}
                  </div>
                </div>
              {/if}

              <div class="space-y-3">
                <h3 class="text-xs font-bold tracking-widest text-muted-foreground uppercase">Run Details</h3>
                {#if run}
                  <div class="rounded-lg border border-border bg-background p-4 text-sm space-y-3">
                    <div class="flex justify-between"><span class="text-muted-foreground">Status</span><Badge variant="outline">{run.status}</Badge></div>
                    <div class="flex justify-between"><span class="text-muted-foreground">Provider</span><span class="font-mono text-foreground">{run.provider || "auto"}</span></div>
                    <div class="flex justify-between"><span class="text-muted-foreground">Model</span><span class="font-mono text-foreground">{run.model || "auto"}</span></div>
                    <div class="flex justify-between"><span class="text-muted-foreground">Budget Used</span><span class="font-mono text-foreground">${run.budget_used_usd.toFixed(4)}</span></div>
                  </div>
                {:else}
                  <p class="text-sm text-muted-foreground">Select a run-producing assistant message.</p>
                {/if}
              </div>
            </div>
          {:else if activeTab === "graph"}
            <div class="space-y-4">
              <h3 class="text-xs font-bold tracking-widest text-muted-foreground uppercase">Task Dependencies</h3>
              {#if tasks.length === 0}
                <p class="text-sm text-muted-foreground italic">No tasks planned for selected run.</p>
              {:else}
                <div class="relative">
                  {#each tasks as task}
                    <TaskGraphNode {task} active={task.status === "running"} />
                  {/each}
                </div>
              {/if}
            </div>
          {:else}
            <div class="space-y-4">
              <h3 class="text-xs font-bold tracking-widest text-muted-foreground uppercase">System Event Log</h3>
              {#if timeline.length === 0}
                <p class="text-sm text-muted-foreground italic">No events recorded.</p>
              {:else}
                <div class="space-y-0 p-2">
                  {#each timeline as event}
                    <AgentTimelineItem {event} />
                  {/each}
                </div>
              {/if}
            </div>
          {/if}
        </div>
      </aside>
    {/if}
  </div>
</div>

<style>
  ::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }
  ::-webkit-scrollbar-track {
    background: transparent;
  }
  ::-webkit-scrollbar-thumb {
    background: #27272a;
    border-radius: 3px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: #3f3f46;
  }
</style>
