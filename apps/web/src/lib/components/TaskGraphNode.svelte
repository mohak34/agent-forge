<script lang="ts">
	import Badge from "./Badge.svelte";
	import { cn } from "$lib/utils";

	let {
		task,
		active = false,
	} = $props<{
		task: any;
		active?: boolean;
	}>();

	// Computed status variants
	const statusMap: Record<string, "outline" | "default" | "success" | "destructive" | "warning"> = {
		pending: "outline",
		running: "default",
		completed: "success",
		failed: "destructive",
		waiting_approval: "warning",
	};

	let badgeVariant = $derived(statusMap[task.status] || "outline");
</script>

<div class={cn(
	"relative flex items-start gap-4 rounded-lg border bg-zinc-950 p-4 transition-all duration-300",
	active ? "border-zinc-500 shadow-sm" : "border-border"
)}>
	<!-- Status Indicator Dot -->
	<div class="mt-1 flex h-2 w-2 shrink-0 rounded-full bg-zinc-600"
		class:bg-zinc-300={task.status === "running"}
		class:bg-emerald-500={task.status === "completed"}
		class:bg-amber-500={task.status === "waiting_approval"}
		class:bg-red-500={task.status === "failed"}
	></div>

	<div class="flex-1 space-y-2">
		<div class="flex items-center justify-between">
			<h4 class="text-sm font-medium text-foreground">{task.title}</h4>
			<Badge variant={badgeVariant}>{task.status}</Badge>
		</div>
		
		<div class="flex items-center gap-3 text-xs font-mono text-muted-foreground">
			<span>[{task.id.slice(0, 8)}]</span>
			<span>kind: {task.kind}</span>
			{#if task.depends_on}
				<span>deps: {task.depends_on}</span>
			{/if}
		</div>

		{#if task.output_text && task.status === "completed"}
			<div class="mt-2 rounded-md bg-zinc-900 p-2.5 text-xs text-zinc-300 font-mono line-clamp-2 border border-border">
				{task.output_text}
			</div>
		{/if}
	</div>
</div>
