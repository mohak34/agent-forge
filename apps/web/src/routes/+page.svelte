<script lang="ts">
	import { onMount, tick } from "svelte";
	import {
		createRun,
		decideApproval,
		getRun,
		getRunTasks,
		getRunTimeline,
		listApprovals,
		listTemplates,
	} from "$lib/api";

	import { cn } from "$lib/utils";

	import Badge from "$lib/components/Badge.svelte";
	import Button from "$lib/components/Button.svelte";
	import Card from "$lib/components/Card.svelte";
	import TaskGraphNode from "$lib/components/TaskGraphNode.svelte";
	import AgentTimelineItem from "$lib/components/AgentTimelineItem.svelte";
	import ApprovalGateCard from "$lib/components/ApprovalGateCard.svelte";

	// -- State --
	let mode = $state<"simple" | "power">("power");
	let goal = $state("");
	let loading = $state(false);
	let error = $state("");
	let runId = $state<string | null>(null);

	// Complex objects
	let run = $state<any>(null);
	let timeline = $state<any[]>([]);
	let tasks = $state<any[]>([]);
	let approvals = $state<any[]>([]);
	let templates = $state<any[]>([]);
	let memoryEnabled = $state(false);
	let selectedTemplateId = $state("");
	let isRightSidebarOpen = $state(false);
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
		updateApprovalPolling();
		scrollToBottom();
	}

	async function submitGoal() {
		if (!goal.trim()) return;
		loading = true;
		error = "";
		timeline = [];
		tasks = [];

		try {
			const createdRun = await createRun(goal, memoryEnabled);
			runId = createdRun.id;
			await refreshRunState(createdRun.id);
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

		return () => stopApprovalPolling();
	});

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			submitGoal();
		}
	}
</script>

<svelte:head>
	<title>Agent-Forge</title>
</svelte:head>

<div class="flex h-screen w-full flex-col bg-background text-foreground font-sans antialiased">
	<!-- Topbar -->
	<header class="flex h-14 shrink-0 items-center justify-between border-b border-border bg-background px-4 lg:px-6">
		<div class="flex items-center gap-3">
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
					onclick={() => mode = "power"}
				>Power</button>
			</div>

			<Button variant="outline" size="sm" class="lg:hidden" onclick={() => isRightSidebarOpen = !isRightSidebarOpen}>
				Menu
			</Button>
		</div>
	</header>

	<div class="flex flex-1 overflow-hidden relative">
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
											<p class="whitespace-pre-wrap">{run.output_text}</p>
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
							{#if mode === "power" && !run}
								<select
									class="max-w-[120px] rounded-md border border-border bg-background px-2 py-1.5 text-xs text-muted-foreground focus:outline-none hidden sm:block"
									bind:value={selectedTemplateId}
								>
									<option value="">Standard</option>
									{#each templates as t}
										<option value={t.id}>{t.name}</option>
									{/each}
								</select>
							{/if}

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
				<div class="flex-1 overflow-y-auto p-4">
					
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
								<div class="space-y-4 relative">
									{#each tasks as task, i}
										<TaskGraphNode {task} active={task.status === 'running'} />
										{#if i < tasks.length - 1}
											<div class="ml-8 h-4 w-px bg-border"></div>
										{/if}
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
