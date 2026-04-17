<script lang="ts">
	import { cn } from "$lib/utils";

	let {
		children,
		class: className = "",
		variant = "default",
		...rest
	} = $props<{
		children: import("svelte").Snippet;
		class?: string;
		variant?: "default" | "secondary" | "success" | "warning" | "destructive" | "outline";
		[key: string]: any;
	}>();

	const variants: Record<string, string> = {
		default: "bg-primary text-primary-foreground",
		secondary: "bg-secondary text-secondary-foreground",
		success: "bg-emerald-500/15 text-emerald-500",
		warning: "bg-amber-500/15 text-amber-500",
		destructive: "bg-red-500/15 text-red-500",
		outline: "text-muted-foreground border border-border",
	};
</script>

<div
	class={cn(
		"inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2",
		variant === "outline" ? "" : "border border-transparent",
		variants[variant],
		className
	)}
	{...rest}
>
	{@render children()}
</div>
