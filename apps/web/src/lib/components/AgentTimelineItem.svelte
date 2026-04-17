<script lang="ts">
	import Badge from "./Badge.svelte";
	import { cn } from "$lib/utils";

	let {
		event,
	} = $props<{
		event: any;
	}>();

	const statusColors: Record<string, string> = {
		info: "text-muted-foreground",
		success: "text-emerald-500",
		warning: "text-amber-500",
		error: "text-red-500",
		active: "text-foreground",
	};

	let colorClass = $derived(statusColors[event.status] || "text-muted-foreground");
</script>

<div class="relative flex gap-4 pb-8 last:pb-0">
	<!-- Connecting Line -->
	<div class="absolute bottom-0 left-[11px] top-6 w-px bg-border last:hidden"></div>

	<!-- Timeline Node -->
	<div class={cn(
		"relative z-10 mt-1.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-border bg-background",
		event.status === 'active' && "border-zinc-500"
	)}>
		<div class={cn("h-1.5 w-1.5 rounded-full", event.status === 'active' ? "bg-foreground" : "bg-zinc-600")}></div>
	</div>

	<!-- Content -->
	<div class="flex-1 space-y-2">
		<div class="flex items-center gap-2">
			<span class={cn("text-sm font-medium tracking-wide", colorClass)}>
				{event.event_type}
			</span>
			<span class="text-xs font-mono text-muted-foreground">[{new Date(event.created_at).toLocaleTimeString()}]</span>
			{#if event.actor}
				<Badge variant="outline" class="ml-auto text-[10px] font-mono">{event.actor}</Badge>
			{/if}
		</div>

		<p class="text-sm text-zinc-300 leading-relaxed">
			{event.detail}
		</p>
	</div>
</div>
