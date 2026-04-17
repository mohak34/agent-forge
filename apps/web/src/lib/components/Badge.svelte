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
		variant?: "default" | "success" | "warning" | "destructive" | "outline";
		[key: string]: any;
	}>();

	const variants: Record<string, string> = {
		default: "bg-zinc-800 text-zinc-100 border-zinc-700",
		success: "border-emerald-500/50 bg-emerald-500/10 text-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.15)]",
		warning: "border-neon-amber/50 bg-neon-amber/10 text-neon-amber shadow-[0_0_8px_rgba(255,191,0,0.15)]",
		destructive: "border-neon-crimson/50 bg-neon-crimson/10 text-neon-crimson shadow-[0_0_8px_rgba(255,0,60,0.15)]",
		outline: "text-zinc-400 border-zinc-800",
	};
</script>

<div
	class={cn(
		"inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2",
		variants[variant],
		className
	)}
	{...rest}
>
	{@render children()}
</div>
