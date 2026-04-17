<script lang="ts">
	import { cn } from "$lib/utils";
	let {
		children,
		class: className = "",
		variant = "default",
		size = "default",
		...rest
	} = $props<{
		children: import("svelte").Snippet;
		class?: string;
		variant?: "default" | "outline" | "ghost" | "destructive" | "neon";
		size?: "default" | "sm" | "lg" | "icon";
		[key: string]: any;
	}>();

	const variants: Record<string, string> = {
		default: "bg-zinc-800 text-zinc-100 hover:bg-zinc-700",
		outline: "border border-zinc-700 bg-transparent hover:bg-zinc-800",
		ghost: "hover:bg-zinc-800 text-zinc-400 hover:text-zinc-100",
		destructive: "bg-neon-crimson text-white hover:opacity-90 shadow-[0_0_10px_rgba(255,0,60,0.5)]",
		neon: "bg-transparent border border-neon-cyan text-neon-cyan shadow-[0_0_10px_rgba(0,255,255,0.2)] hover:bg-neon-cyan hover:text-zinc-950",
	};

	const sizes: Record<string, string> = {
		default: "h-9 px-4 py-2",
		sm: "h-8 rounded-md px-3 text-xs",
		lg: "h-10 rounded-md px-8",
		icon: "h-9 w-9",
	};
</script>

<button
	class={cn(
		"inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50",
		variants[variant],
		sizes[size],
		className
	)}
	{...rest}
>
	{@render children()}
</button>
