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
	} from "$lib/api";

	import Badge from "$lib/components/Badge.svelte";
	import Button from "$lib/components/Button.svelte";
	import Card from "$lib/components/Card.svelte";
	import TaskGraphNode from "$lib/components/TaskGraphNode.svelte";
	import AgentTimelineItem from "$lib/components/AgentTimelineItem.svelte";
	import ApprovalGateCard from "$lib/components/ApprovalGateCard.svelte";

	// -- State --
	let mode = $state<"simple" | "power">("power");
	let goal = $state("Create an implementation checklist for shipping a safe research assistant MVP in two weeks.");
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
		} catch (e: any) {
			error = e.message || "Unknown error";
		} finally {
			loading = false;
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
				}
			} catch {
				stopApprovalPolling();
			}
		}, 5000);
	}

	onMount(() => {
		listTemplates().then(res => {
			templates = res;
			if (res.length > 0) selectedTemplateId = res[0].id;
		});
		listApprovals().then(res => approvals = res);

		return () => {
			stopApprovalPolling();
		};
	});

</script>

<svelte:head>
	<title>Agent-Forge Workbench</title>
</svelte:head>

<div class="flex h-screen w-full flex-col bg-background text-foreground overflow-hidden font-sans selection:bg-neon-cyan/30">
	<!-- Topbar -->
	<header class="flex h-14 shrink-0 items-center justify-between border-b border-border bg-zinc-950/50 px-6 backdrop-blur-md">
		<div class="flex items-center gap-4">
			<div class="h-4 w-4 bg-neon-cyan [clip-path:polygon(50%_0%,100%_25%,100%_75%,50%_100%,0%_75%,0%_25%)] shadow-[0_0_10px_#0ff]"></div>
			<h1 class="text-sm font-bold tracking-[0.25em] text-zinc-100">AGENT-FORGE <span class="text-neon-cyan">OS</span></h1>
		</div>
		
		<div class="flex items-center gap-6">
			{#if run}
				<div class="flex items-center gap-4 text-xs font-mono">
					<div class="flex flex-col text-right">
						<span class="text-zinc-500">BUDGET USED</span>
						<span class="text-neon-cyan font-bold">${run.budget_used_usd.toFixed(4)}</span>
					</div>
					<div class="h-6 w-px bg-zinc-800"></div>
					<div class="flex flex-col text-right">
						<span class="text-zinc-500">TOKENS</span>
						<span class="text-zinc-300">{run.token_estimate}</span>
					</div>
				</div>
			{/if}
			<div class="h-6 w-px bg-zinc-800"></div>
			<div class="flex rounded-md border border-zinc-800 bg-zinc-900 p-1 text-xs">
				<button
					class={`rounded px-3 py-1 transition-colors ${mode === "simple" ? "bg-zinc-800 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"}`}
					onclick={() => mode = "simple"}
				>Simple</button>
				<button
					class={`rounded px-3 py-1 transition-colors ${mode === "power" ? "bg-zinc-800 text-zinc-100" : "text-zinc-500 hover:text-zinc-300"}`}
					onclick={() => mode = "power"}
				>Power</button>
			</div>
		</div>
	</header>

	<div class="flex flex-1 overflow-hidden">
		<!-- Sidebar (Optional config/templates) -->
		<aside class="w-64 border-r border-border bg-zinc-950/30 p-4 flex flex-col gap-6 overflow-y-auto">
			<div class="space-y-3">
				<h3 class="text-xs font-bold tracking-widest text-zinc-500 uppercase">Initialization</h3>
				<select
					class="w-full rounded border border-zinc-800 bg-zinc-900 px-3 py-2 text-sm text-zinc-300 focus:border-neon-cyan focus:outline-none focus:ring-1 focus:ring-neon-cyan"
					bind:value={selectedTemplateId}
				>
					<option value="">Standard Mode</option>
					{#each templates as t}
						<option value={t.id}>{t.name} (v{t.version})</option>
					{/each}
				</select>
				
				<label class="flex items-center gap-3 rounded border border-zinc-800 bg-zinc-900/50 p-3 hover:bg-zinc-900 transition-colors cursor-pointer group">
					<div class="relative flex h-4 w-4 items-center justify-center rounded border border-zinc-600 bg-zinc-950 group-hover:border-neon-cyan transition-colors">
						{#if memoryEnabled}
							<div class="h-2 w-2 rounded-sm bg-neon-cyan shadow-[0_0_5px_#0ff]"></div>
						{/if}
						<input type="checkbox" class="absolute inset-0 opacity-0 cursor-pointer" bind:checked={memoryEnabled} />
					</div>
					<span class="text-xs font-medium text-zinc-300 group-hover:text-neon-cyan transition-colors">PERSISTENT MEMORY</span>
				</label>
			</div>

			<div class="space-y-3">
				<h3 class="text-xs font-bold tracking-widest text-zinc-500 uppercase">System Status</h3>
				<div class="flex items-center justify-between rounded border border-emerald-900/30 bg-emerald-950/10 px-3 py-2">
					<span class="text-xs font-mono text-zinc-400">CORE</span>
					<Badge variant="success" class="text-[10px] h-5">ONLINE</Badge>
				</div>
				<div class="flex items-center justify-between rounded border border-zinc-800 bg-zinc-900/20 px-3 py-2">
					<span class="text-xs font-mono text-zinc-400">POLICY ENG</span>
					<Badge variant="default" class="text-[10px] h-5">ACTIVE</Badge>
				</div>
			</div>
		</aside>

		<!-- Main Workspace -->
		<main class="flex-1 flex flex-col bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px]">
			
			<!-- Input Area -->
			<div class="border-b border-border bg-zinc-950/80 p-6 backdrop-blur-sm">
				<div class="mx-auto max-w-4xl space-y-4">
					{#if error}
						<div class="rounded border border-neon-crimson/50 bg-neon-crimson/10 px-4 py-3 text-sm text-neon-crimson font-mono">
							[ERROR]: {error}
						</div>
					{/if}

					<div class="relative group">
						<div class="absolute -inset-0.5 rounded bg-gradient-to-r from-neon-cyan/20 to-zinc-800 opacity-20 blur transition duration-500 group-focus-within:opacity-100"></div>
						<textarea
							bind:value={goal}
							class="relative w-full min-h-[100px] resize-none rounded bg-zinc-950 px-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-700 outline-none border border-zinc-800 focus:border-neon-cyan transition-colors"
							placeholder="> Define operational parameters or high-level goal..."
						></textarea>
						
						<div class="absolute bottom-3 right-3">
							<Button variant={loading ? "outline" : "neon"} size="sm" onclick={submitGoal} disabled={loading}>
								{loading ? 'EXECUTING...' : 'INITIATE RUN'}
							</Button>
						</div>
					</div>
				</div>
			</div>

			<!-- Dynamic Dashboard Grid -->
			<div class="flex-1 overflow-hidden p-6">
				<div class="mx-auto h-full max-w-7xl grid grid-cols-1 lg:grid-cols-2 gap-6">
					
					<!-- Left Column: Task Graph -->
					<Card class="flex flex-col overflow-hidden border-zinc-800/50 bg-zinc-950/50 backdrop-blur">
						<div class="border-b border-zinc-800 px-4 py-3 flex justify-between items-center bg-zinc-900/50">
							<h3 class="text-xs font-bold tracking-widest text-zinc-400 uppercase">Orchestration Graph</h3>
							{#if run}
								<Badge variant={run.status === 'completed' ? 'success' : run.status === 'failed' ? 'destructive' : 'default'} class="uppercase">{run.status}</Badge>
							{/if}
						</div>
						<div class="flex-1 overflow-y-auto p-4 space-y-4">
							{#if tasks.length === 0}
								<div class="flex h-full items-center justify-center text-xs font-mono text-zinc-600">
									[ Awaiting task definitions ]
								</div>
							{:else}
								{#each tasks as task, i}
									<TaskGraphNode {task} active={task.status === 'running'} />
									{#if i < tasks.length - 1}
										<div class="ml-8 h-4 w-[1px] bg-zinc-800"></div>
									{/if}
								{/each}
							{/if}
						</div>
					</Card>

					<!-- Right Column: Timeline & Approvals -->
					<div class="flex flex-col gap-6 overflow-hidden">
						
						<!-- Action Center (Approvals) -->
						{#if isWaitingApproval || latestRunApprovals.length > 0}
							<Card class="border-neon-amber/30 bg-zinc-950/80 shadow-[0_0_30px_rgba(255,191,0,0.05)] shrink-0 max-h-[50%] overflow-y-auto">
								<div class="border-b border-neon-amber/20 px-4 py-3 bg-neon-amber/5 flex items-center gap-2">
									<div class="h-2 w-2 rounded-full bg-neon-amber animate-pulse"></div>
									<h3 class="text-xs font-bold tracking-widest text-neon-amber uppercase">Action Center</h3>
								</div>
								<div class="p-4 space-y-4">
									{#each latestRunApprovals as approval}
										{#if approval.status === 'pending'}
											<ApprovalGateCard {approval} onDecide={decide} />
										{:else}
											<div class="flex justify-between items-center rounded border border-zinc-800 bg-zinc-900 p-3 text-sm">
												<span class="text-zinc-400">Action: {approval.action_type}</span>
												<Badge variant={approval.status === 'approved' ? 'success' : 'destructive'}>{approval.status}</Badge>
											</div>
										{/if}
									{/each}
								</div>
							</Card>
						{/if}

						<!-- Traceability Timeline -->
						<Card class="flex-1 flex flex-col overflow-hidden border-zinc-800/50 bg-zinc-950/50 backdrop-blur min-h-[300px]">
							<div class="border-b border-zinc-800 px-4 py-3 flex justify-between items-center bg-zinc-900/50">
								<h3 class="text-xs font-bold tracking-widest text-zinc-400 uppercase">System Traceability</h3>
								<span class="text-[10px] font-mono text-zinc-500">STREAMING...</span>
							</div>
							<div class="flex-1 overflow-y-auto p-6 bg-zinc-950">
								{#if timeline.length === 0}
									<div class="flex h-full items-center justify-center text-xs font-mono text-zinc-600">
										[ Log stream empty ]
									</div>
								{:else}
									<div class="space-y-0">
										{#each timeline as event}
											<AgentTimelineItem {event} />
										{/each}
									</div>
								{/if}
							</div>
						</Card>

					</div>
				</div>
			</div>
		</main>
	</div>
</div>

<style>
	/* Custom scrollbar for deep dark aesthetic */
	::-webkit-scrollbar {
		width: 8px;
		height: 8px;
	}
	::-webkit-scrollbar-track {
		background: #09090b; 
	}
	::-webkit-scrollbar-thumb {
		background: #27272a; 
		border-radius: 4px;
	}
	::-webkit-scrollbar-thumb:hover {
		background: #3f3f46; 
	}
</style>
