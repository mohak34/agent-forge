<script lang="ts">
	import Badge from "./Badge.svelte";
	import { cn } from "$lib/utils";

	let {
		event,
	} = $props<{
		event: any;
	}>();

	const statusColors: Record<string, string> = {
		info: "text-zinc-500",
		success: "text-emerald-400",
		warning: "text-neon-amber",
		error: "text-neon-crimson",
		active: "text-neon-cyan",
	};

	let colorClass = $derived(statusColors[event.status] || "text-zinc-500");
</script>

<div class="relative flex gap-4 pb-8 last:pb-0">
	<!-- Connecting Line -->
	<div class="absolute bottom-0 left-[11px] top-6 w-[2px] bg-zinc-800 last:hidden"></div>

	<!-- Timeline Node -->
	<div class={cn(
		"relative z-10 mt-1.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-zinc-800 bg-zinc-950",
		event.status === 'active' && "border-neon-cyan shadow-[0_0_10px_rgba(0,255,255,0.4)]"
	)}>
		<div class={cn("h-2 w-2 rounded-full", event.status === 'active' ? "bg-neon-cyan" : "bg-zinc-700")}></div>
	</div>

	<!-- Content -->
	<div class="flex-1 space-y-2">
		<div class="flex items-center gap-2">
			<span class={cn("text-sm font-semibold tracking-wide", colorClass)}>
				{event.event_type}
			</span>
			<span class="text-xs font-mono text-zinc-600">[{new Date(event.created_at).toLocaleTimeString()}]</span>
			{#if event.actor}
				<Badge variant="outline" class="ml-auto text-[10px]">{event.actor}</Badge>
			{/if}
		</div>

		<p class="text-sm text-zinc-300 leading-relaxed">
			{event.detail}
		</p>
	</div>
</div>
