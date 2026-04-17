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

<div class="rounded-xl border border-amber-500/30 bg-zinc-950 p-6 shadow-sm relative overflow-hidden group">
	<div class="relative z-10 space-y-4">
		<div class="flex items-center justify-between">
			<div class="flex items-center gap-3">
				<div class="h-2.5 w-2.5 rounded-full bg-amber-500 animate-pulse"></div>
				<h3 class="text-sm font-bold tracking-wide text-amber-500 uppercase">Human Intervention Required</h3>
			</div>
			<Badge variant="warning">ID: {approval.id.slice(0, 6)}</Badge>
		</div>

		<div class="border-l-2 border-amber-500/30 pl-4 py-2">
			<p class="font-mono text-xs text-muted-foreground mb-1">ACTION TYPE</p>
			<p class="text-sm font-medium text-foreground">{approval.action_type}</p>
		</div>

		<div class="rounded-md border border-border bg-zinc-900 px-4 py-3 font-mono text-xs text-zinc-300">
			<p class="text-muted-foreground mb-2">>> REASON FOR FLAG</p>
			<p>{approval.reason}</p>
		</div>

		{#if approval.payload}
			<details class="text-xs text-muted-foreground font-mono">
				<summary class="cursor-pointer hover:text-zinc-300">View Raw Payload</summary>
				<pre class="mt-2 rounded bg-zinc-950 p-3 overflow-x-auto border border-border">{JSON.stringify(JSON.parse(approval.payload), null, 2)}</pre>
			</details>
		{/if}

		<div class="flex items-center gap-4 pt-4 border-t border-border mt-2">
			<Button variant="default" class="w-full font-medium" onclick={() => onDecide(approval.id, "approve")}>
				Approve
			</Button>
			<Button variant="destructive" class="w-full font-medium" onclick={() => onDecide(approval.id, "reject")}>
				Reject
			</Button>
		</div>
	</div>
</div>
