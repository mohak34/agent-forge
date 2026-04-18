<script lang="ts">
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

<div class="flex items-start gap-3 py-2 text-sm hover:bg-secondary/30 px-2 rounded -mx-2 transition-colors">
	<!-- Time -->
	<span class="text-[10px] font-mono text-zinc-500 shrink-0 w-16 pt-[2px]">
		{new Date(event.created_at).toLocaleTimeString([], { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })}
	</span>
	
	<!-- Message -->
	<div class="flex-1 min-w-0 break-words space-y-1">
		<div class="flex items-center gap-2">
			<span class={cn("font-mono text-[11px] font-medium leading-tight", colorClass)}>
				{event.event_type}
			</span>
		</div>
		<p class="text-[13px] text-zinc-300 leading-snug">
			{event.detail}
		</p>
	</div>
	
	<!-- Actor -->
	{#if event.actor}
		<span class="text-[10px] font-mono uppercase text-muted-foreground shrink-0 pt-[2px]">{event.actor}</span>
	{/if}
</div>
