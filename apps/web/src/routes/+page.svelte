<script lang="ts">
	import { onMount, tick } from "svelte";
	import {
		createRun,
		decideApproval,
		getRun,
		getRunTasks,
		getRunTimeline,
		listApprovals,
		listRuns,
		listTemplates,
		runFromTemplate
	} from "$lib/api";

	import { cn } from "$lib/utils";
	import { parseMarkdown } from "$lib/markdown";

	import Badge from "$lib/components/Badge.svelte";
	import Button from "$lib/components/Button.svelte";
	import TaskGraphNode from "$lib/components/TaskGraphNode.svelte";
	import AgentTimelineItem from "$lib/components/AgentTimelineItem.svelte";
	import ApprovalGateCard from "$lib/components/ApprovalGateCard.svelte";

	// -- State --
	let mode = $state<"simple" | "power">("power");
	let goal = $state("");
	let loading = $state(false);
	let error = $state("");
	let runId = $state<string | null>(null);
	let historySidebarOpen = $state(true);
	let runHistory = $state<any[]>([]);

	// Complex objects
	let run = $state<any>(null);
	let timeline = $state<any[]>([]);
	let tasks = $state<any[]>([]);
	let approvals = $state<any[]>([]);
	let templates = $state<any[]>([]);
	let memoryEnabled = $state(false);
	let selectedTemplateId = $state("");
	let isRightSidebarOpen = $state(true);
	let activeTab = $state<"overview" | "graph" | "traceability">("overview");

	// Auto-scroll chat feed
	let chatFeedRef = $state<HTMLElement | null>(null);

	// Polling state
	let approvalPollId: ReturnType<typeof setInterval> | null = null;

	// -- Derived --
	let isWaitingApproval = $derived(run?.status === "waiting_approval");
	let latestRunApprovals = $derived(approvals.filter((a) => a.run_id === run?.id));

	// -- API Logic --
	async function refreshRunState(id: string) {
		run = await getRun(id);
		timeline = await getRunTimeline(id);
		tasks = await getRunTasks(id);
		approvals = await listApprovals();
		runHistory = await listRuns(75);
		updateApprovalPolling();
		scrollToBottom();
	}

	async function loadRunHistory() {
		try {
			runHistory = await listRuns(75);
		} catch {
			runHistory = [];
		}
	}

	async function openRunFromHistory(id: string) {
		error = "";
		runId = id;
		await refreshRunState(id);
	}

	function startNewChat() {
		runId = null;
		run = null;
		timeline = [];
		tasks = [];
		error = "";
		goal = "";
		stopApprovalPolling();
	}

	async function submitGoal() {
		if (!goal.trim()) return;
		loading = true;
		error = "";
		timeline = [];
		tasks = [];

		try {
			let createdRun;
			if (selectedTemplateId) {
				createdRun = await runFromTemplate(selectedTemplateId, goal, memoryEnabled);
			} else {
				createdRun = await createRun(goal, memoryEnabled);
			}
			runId = createdRun.id;
			await refreshRunState(createdRun.id);
			await loadRunHistory();
			if (mode === "power") isRightSidebarOpen = true;
		} catch (e: any) {
			error = e.message || "Unknown error";
		} finally {
			loading = false;
			goal = "";
		}
	}

	async function decide(id: string, decision: "approve" | "reject") {
		try {
			await decideApproval(id, decision, "manual decision from dashboard");
			if (runId) {
				await refreshRunState(runId);
				await loadRunHistory();
			} else {
				approvals = await listApprovals();
			}
		} catch (e: any) {
			error = e.message || "Failed to submit approval decision";
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
		if (!isWaitingApproval) return;
		
		approvalPollId = setInterval(async () => {
			approvals = await listApprovals();
			if (!runId) return;
			try {
				run = await getRun(runId);
				if (run.status !== "waiting_approval") {
					timeline = await getRunTimeline(runId);
					tasks = await getRunTasks(runId);
					stopApprovalPolling();
					scrollToBottom();
				}
			} catch {
				stopApprovalPolling();
			}
		}, 5000);
	}

	async function scrollToBottom() {
		await tick();
		if (chatFeedRef) {
			chatFeedRef.scrollTop = chatFeedRef.scrollHeight;
		}
	}

	onMount(() => {
		listTemplates().then(res => {
			templates = res;
			if (res.length > 0) selectedTemplateId = res[0].id;
		});
		listApprovals().then(res => approvals = res);
		loadRunHistory();

		return () => stopApprovalPolling();
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			submitGoal();
		}
	}

	function summarizeGoal(text: string) {
		const trimmed = (text || "").trim();
		if (!trimmed) return "Untitled run";
		if (trimmed.length <= 54) return trimmed;
		return `${trimmed.slice(0, 54)}...`;
	}
</script>

<svelte:head>
	<title>Agent-Forge</title>
</svelte:head>

<div class="flex h-screen w-full flex-col bg-background text-foreground font-sans antialiased">
	<!-- Topbar -->
	<header class="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background px-4 lg:px-6">
		<div class="flex items-center gap-3">
			<Button variant="ghost" size="icon" class="h-8 w-8" onclick={() => historySidebarOpen = !historySidebarOpen}>
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
					onclick={() => { mode = "simple"; isRightSidebarOpen = false; }}
				>Simple</button>
				<button
					class={`rounded-sm px-3 py-1 transition-colors ${mode === "power" ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"}`}
					onclick={() => { mode = "power"; isRightSidebarOpen = true; }}
				>Power</button>
			</div>

			<Button variant="outline" size="sm" class="lg:hidden" onclick={() => isRightSidebarOpen = !isRightSidebarOpen}>
				Menu
			</Button>
		</div>
	</header>

	<div class="flex flex-1 overflow-hidden relative">
		{#if historySidebarOpen}
			<aside class="hidden md:flex w-[280px] shrink-0 flex-col border-r border-border bg-card/40 transition-all duration-300">
				<div class="border-b border-border p-3">
					<Button variant="default" class="w-full justify-center" onclick={startNewChat}>New Chat</Button>
				</div>
				<div class="flex-1 overflow-y-auto p-3 space-y-2">
					{#if runHistory.length === 0}
						<p class="px-2 py-1 text-xs text-muted-foreground">No runs yet.</p>
					{:else}
						{#each runHistory as item}
							<button
								class={cn(
									"w-full rounded-md border px-3 py-2 text-left transition-colors",
									runId === item.id
										? "border-zinc-500 bg-zinc-900/70"
										: "border-border bg-background/50 hover:bg-secondary/40"
								)}
								onclick={() => openRunFromHistory(item.id)}
							>
								<div class="truncate text-sm font-medium text-foreground">{summarizeGoal(item.goal)}</div>
								<div class="mt-1 flex items-center justify-between text-[11px] text-muted-foreground">
									<span class="uppercase">{item.status}</span>
									<span>{new Date(item.created_at).toLocaleDateString()}</span>
								</div>
							</button>
						{/each}
					{/if}
				</div>

				<!-- Moved Configuration here in Power Mode -->
				{#if mode === "power"}
					<div class="border-t border-border p-4 space-y-6 bg-background/50 mt-auto">
						<div class="space-y-3">
							<h3 class="text-[10px] font-bold tracking-[0.15em] text-muted-foreground uppercase">Configuration</h3>
							<div class="space-y-2">
								<label for="template-select" class="text-xs text-muted-foreground block">Template</label>
								<select
									id="template-select"
									class="w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-zinc-600 transition-shadow"
									bind:value={selectedTemplateId}
								>
									<option value="">Standard Base</option>
									{#each templates as t}
										<option value={t.id}>{t.name}</option>
									{/each}
								</select>
							</div>

							<label class="flex items-center gap-3 rounded-md border border-border bg-card p-3 hover:bg-secondary/50 transition-colors cursor-pointer group mt-2">
								<div class="relative flex h-4 w-4 items-center justify-center rounded border border-border bg-background group-hover:border-zinc-500 transition-colors">
									{#if memoryEnabled}
										<div class="h-2 w-2 rounded-sm bg-foreground"></div>
									{/if}
									<input type="checkbox" class="absolute inset-0 opacity-0 cursor-pointer" bind:checked={memoryEnabled} />
								</div>
								<span class="text-xs font-medium text-foreground">Persistent Memory</span>
							</label>
						</div>
					</div>
				{/if}
			</aside>
		{/if}

		<!-- Main Chat Area -->
		<main class="flex-1 flex flex-col relative transition-all duration-300">
			
			{#if error}
				<div class="m-4 rounded-md border border-red-500/50 bg-red-500/10 px-4 py-3 text-sm text-red-500">
					{error}
				</div>
			{/if}

			<!-- Chat Feed -->
			<div class="flex-1 overflow-y-auto p-4 lg:p-8 scroll-smooth" bind:this={chatFeedRef}>
				<div class="mx-auto max-w-3xl space-y-8 pb-8">
					{#if !run}
						<div class="flex h-[50vh] flex-col items-center justify-center text-center space-y-4 opacity-50">
							<div class="flex h-12 w-12 items-center justify-center rounded-xl bg-card border border-border">
								<span class="font-mono text-xl font-bold">AF</span>
							</div>
							<div>
								<h2 class="text-lg font-medium text-foreground">Welcome to Agent-Forge</h2>
								<p class="text-sm text-muted-foreground mt-1 max-w-sm">Describe your research goal below, and our agent swarm will handle the rest.</p>
							</div>
						</div>
					{:else}
						<!-- User Goal Message -->
						<div class="flex gap-4">
							<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary border border-border text-xs font-medium">U</div>
							<div class="space-y-2 mt-1 flex-1">
								<p class="text-[15px] font-medium text-foreground leading-relaxed">
									{run.goal}
								</p>
								<div class="flex gap-2">
									<Badge variant="outline" class="text-[10px] font-mono">ID: {run.id.slice(0, 8)}</Badge>
									<Badge variant={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'destructive' : run.status === 'waiting_approval' ? 'warning' : 'default'} class="text-[10px] uppercase">
										{run.status}
									</Badge>
								</div>
							</div>
						</div>

						<!-- Agent Processing/Output Message -->
						<div class="flex gap-4">
							<div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground font-bold text-xs">AF</div>
							<div class="mt-1 flex-1 min-w-0">
								{#if run.status === "queued" || run.status === "running"}
									<div class="flex items-center gap-3 text-muted-foreground text-sm">
										<div class="flex gap-1">
											<div class="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" style="animation-delay: 0ms"></div>
											<div class="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" style="animation-delay: 150ms"></div>
											<div class="h-1.5 w-1.5 rounded-full bg-zinc-500 animate-bounce" style="animation-delay: 300ms"></div>
										</div>
										Orchestrating agents...
									</div>
								{:else if run.status === "waiting_approval"}
									<div class="rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-500/90">
										<p class="font-medium">Action Required</p>
										<p class="mt-1 opacity-90">The agent encountered a policy check that requires human approval. Please check the action center.</p>
										{#if !isRightSidebarOpen}
											<Button variant="outline" size="sm" class="mt-3 bg-background" onclick={() => isRightSidebarOpen = true}>View Approvals</Button>
										{/if}
									</div>
									{:else if run.status === "completed"}
										<div class="prose prose-invert prose-sm max-w-none text-[15px] leading-relaxed text-zinc-300">
											{#if run.output_text}
												<div class="whitespace-normal prose-table:block prose-table:overflow-x-auto prose-table:w-full">{@html parseMarkdown(run.output_text)}</div>
											{:else}
												<p class="italic text-muted-foreground">Run completed with no final output.</p>
											{/if}
										</div>
									{:else if run.status === "failed"}
									<div class="rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-500/90">
										<p class="font-medium">Execution Failed</p>
										<p class="mt-1 opacity-90">{run.output_text || "The agent encountered an unrecoverable error."}</p>
									</div>
								{/if}
							</div>
						</div>
					{/if}
				</div>
			</div>

			<!-- Input Area -->
			<div class="p-4 lg:p-6 bg-gradient-to-t from-background via-background/95 to-transparent">
				<div class="mx-auto max-w-3xl relative">
					<div class="relative flex items-end rounded-xl border border-border bg-card shadow-sm focus-within:ring-1 focus-within:ring-zinc-600 transition-shadow">
						<textarea
							bind:value={goal}
							onkeydown={handleKeydown}
							class="max-h-[200px] min-h-[60px] w-full resize-none bg-transparent px-4 py-4 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none"
							placeholder="Type your high-level goal... (Shift+Enter for newline)"
							disabled={loading}
						></textarea>
						
						<div class="flex items-center gap-2 p-3 pb-3 shrink-0">
							<Button 
								variant={loading || !goal.trim() ? "secondary" : "default"} 
								size="icon" 
								class="h-8 w-8 rounded-lg" 
								onclick={submitGoal} 
								disabled={loading || !goal.trim()}
							>
								{#if loading}
									<span class="h-3 w-3 rounded-sm bg-current animate-pulse"></span>
								{:else}
									<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></svg>
								{/if}
							</Button>
						</div>
					</div>
					<div class="mt-2 text-center text-xs text-muted-foreground flex items-center justify-center gap-4">
						<span>Press <kbd class="rounded border border-border bg-secondary px-1 font-mono text-[10px]">Enter</kbd> to submit</span>
						{#if mode === "simple"}
							<button class="hover:text-foreground hover:underline transition-colors" onclick={() => isRightSidebarOpen = !isRightSidebarOpen}>
								Toggle Sidebar
							</button>
						{/if}
					</div>
				</div>
			</div>
		</main>

		<!-- Right Sidebar (Observability) -->
		{#if isRightSidebarOpen}
			<aside class="absolute inset-y-0 right-0 z-20 w-full flex flex-col border-l border-border bg-card shadow-xl transition-transform duration-300 sm:w-[380px] lg:static lg:z-0">
				
				<!-- Sidebar Header / Tabs -->
				<div class="flex items-center justify-between border-b border-border p-2">
					<div class="flex gap-1 p-1">
						{#each ["overview", "graph", "traceability"] as tab}
							<button
								class={cn(
									"rounded-md px-3 py-1.5 text-xs font-medium capitalize transition-colors",
									activeTab === tab ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
								)}
								onclick={() => activeTab = tab as any}
							>
								{tab}
							</button>
						{/each}
					</div>
					<Button variant="ghost" size="icon" class="h-8 w-8 lg:hidden" onclick={() => isRightSidebarOpen = false}>
						<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="h-4 w-4"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
					</Button>
				</div>

				<!-- Sidebar Content -->
				<div class="flex-1 overflow-y-auto overflow-x-hidden p-4">
					
					{#if activeTab === "overview"}
						<div class="space-y-6">
							<!-- Action Center (Approvals) -->
							{#if isWaitingApproval || latestRunApprovals.length > 0}
								<div class="space-y-3">
									<h3 class="text-xs font-bold tracking-widest text-muted-foreground uppercase">Action Center</h3>
									<div class="space-y-3">
										{#each latestRunApprovals as approval}
											{#if approval.status === 'pending'}
												<ApprovalGateCard {approval} onDecide={decide} />
											{:else}
												<div class="flex justify-between items-center rounded-md border border-border bg-background p-3 text-sm">
													<span class="text-muted-foreground">Action: {approval.action_type}</span>
													<Badge variant={approval.status === 'approved' ? 'success' : 'destructive'}>{approval.status}</Badge>
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
										<div class="flex justify-between"><span class="text-muted-foreground">Budget Limit</span><span class="font-mono text-foreground">${run.budget_limit_usd.toFixed(2)}</span></div>
									</div>
								{:else}
									<p class="text-sm text-muted-foreground">No active run.</p>
								{/if}
							</div>
						</div>

					{:else if activeTab === "graph"}
						<div class="space-y-4">
							<h3 class="text-xs font-bold tracking-widest text-muted-foreground uppercase">Task Dependencies</h3>
							{#if tasks.length === 0}
								<p class="text-sm text-muted-foreground italic">No tasks planned yet.</p>
							{:else}
								<div class="relative">
									{#each tasks as task, i}
										<TaskGraphNode {task} active={task.status === 'running'} />
									{/each}
								</div>
							{/if}
						</div>

					{:else if activeTab === "traceability"}
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
