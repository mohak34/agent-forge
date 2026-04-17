<script lang="ts">
	import { cn } from "$lib/utils";
	let { children, class: className = "", ...rest } = $props<{
		children: import("svelte").Snippet;
		class?: string;
		[key: string]: any;
	}>();
</script>

<div class={cn("rounded-lg border bg-card text-card-foreground shadow-sm", className)} {...rest}>
	{@render children()}
</div>
