<script lang="ts">
	import Badge from "./Badge.svelte";
	import Button from "./Button.svelte";
	import { cn } from "$lib/utils";

	let {
		approval,
		onDecide,
	} = $props<{
		approval: any;
		onDecide: (id: string, decision: "approve" | "reject") => void;
	}>();
</script>

<div class="rounded-xl border border-neon-amber/50 bg-zinc-950 p-6 shadow-[0_0_20px_rgba(255,191,0,0.1)] relative overflow-hidden group">
	<!-- Scanning/Pulse Effect Background -->
	<div class="absolute inset-0 bg-[linear-gradient(rgba(255,191,0,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(255,191,0,0.05)_1px,transparent_1px)] bg-[size:20px_20px] [mask-image:radial-gradient(ellipse_at_center,black_50%,transparent_100%)] opacity-30"></div>
	
	<div class="relative z-10 space-y-4">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="h-3 w-3 rounded-full bg-neon-amber shadow-[0_0_8px_rgba(255,191,0,1)] animate-pulse"></div>
				<h3 class="text-lg font-bold tracking-widest text-neon-amber uppercase">Human Intervention Required</h3>
			</div>
			<Badge variant="warning">ID: {approval.id.slice(0, 6)}</Badge>
		</div>

		<div class="border-l-2 border-neon-amber/30 pl-4 py-2">
			<p class="font-mono text-sm text-zinc-400 mb-1">ACTION TYPE</p>
			<p class="text-base text-zinc-100">{approval.action_type}</p>
		</div>

		<div class="border border-zinc-800 bg-zinc-900 rounded px-4 py-3 font-mono text-sm text-zinc-300">
			<p class="text-neon-cyan mb-2">>> REASON FOR FLAG</p>
			<p>{approval.reason}</p>
		</div>

		{#if approval.payload}
			<details class="text-xs text-zinc-500 font-mono">
				<summary class="cursor-pointer hover:text-zinc-300">View Raw Payload</summary>
				<pre class="mt-2 rounded bg-zinc-950 p-3 overflow-x-auto border border-zinc-800">{JSON.stringify(JSON.parse(approval.payload), null, 2)}</pre>
			</details>
		{/if}

		<div class="flex items-center gap-4 pt-4 border-t border-zinc-800">
			<Button variant="neon" class="w-full font-bold tracking-wider" onclick={() => onDecide(approval.id, "approve")}>
				AUTHORIZE
			</Button>
			<Button variant="destructive" class="w-full font-bold tracking-wider" onclick={() => onDecide(approval.id, "reject")}>
				DENY
			</Button>
		</div>
	</div>
</div>
