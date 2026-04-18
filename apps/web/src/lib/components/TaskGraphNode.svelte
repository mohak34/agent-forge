<script lang="ts">
	import Badge from "./Badge.svelte";
	import { cn } from "$lib/utils";
	import { parseMarkdown } from "$lib/markdown";

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
	let expanded = $state(false);
</script>

<div class="relative flex items-start gap-4 group pb-4">
	<!-- Vertical line connecting nodes -->
	<div class="absolute left-[7px] top-5 bottom-0 w-px bg-border group-last:hidden"></div>

	<!-- Status Node / Circle -->
	<div class="relative z-10 mt-1 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-background border-[2px]"
		class:border-zinc-300={task.status === "running"}
		class:border-emerald-500={task.status === "completed"}
		class:border-amber-500={task.status === "waiting_approval"}
		class:border-red-500={task.status === "failed"}
		class:border-zinc-700={task.status === "pending"}
	>
		{#if task.status === "running"}
			<div class="h-1.5 w-1.5 rounded-full bg-zinc-300 animate-pulse"></div>
		{/if}
	</div>

	<!-- Content -->
	<div class={cn(
		"flex-1 min-w-0 transition-opacity",
		task.status === "pending" ? "opacity-60" : "opacity-100"
	)}>
		<div class="flex items-center justify-between">
			<h4 class="text-sm font-medium text-foreground leading-none">{task.title}</h4>
			<Badge variant={badgeVariant} class="text-[10px] h-5 px-1.5 py-0 uppercase">{task.status}</Badge>
		</div>
		
		<div class="mt-1.5 flex flex-wrap items-center gap-2 text-xs font-mono text-muted-foreground">
			<span class="rounded bg-secondary/50 px-1.5 py-0.5">{task.kind}</span>
			{#if task.depends_on}
				<span class="rounded bg-secondary/50 px-1.5 py-0.5 text-zinc-500">deps: {task.depends_on}</span>
			{/if}
		</div>

		{#if task.output_text && task.status === "completed"}
			<div class="mt-3 flex flex-col items-start gap-1.5 w-full">
				<div 
					class={cn(
						"w-full rounded border border-border bg-secondary/30 p-3 text-[12px] text-zinc-300 font-sans leading-relaxed prose prose-sm prose-invert max-w-none prose-table:block prose-table:overflow-x-auto prose-table:w-full",
						!expanded ? "max-h-[120px] overflow-hidden" : "max-h-[350px] overflow-y-auto"
					)}
					style={!expanded ? "mask-image: linear-gradient(to bottom, black 60%, transparent 100%); -webkit-mask-image: linear-gradient(to bottom, black 60%, transparent 100%);" : ""}
				>
					{@html parseMarkdown(task.output_text)}
				</div>
				<button 
					class="text-[10px] font-medium uppercase tracking-widest text-muted-foreground hover:text-foreground transition-colors"
					onclick={() => expanded = !expanded}
				>
					{expanded ? "Show less" : "Read more"}
				</button>
			</div>
		{/if}
	</div>
</div>
