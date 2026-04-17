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
		variant?: "default" | "secondary" | "outline" | "ghost" | "destructive";
		size?: "default" | "sm" | "lg" | "icon";
		[key: string]: any;
	}>();

	const variants: Record<string, string> = {
		default: "bg-primary text-primary-foreground hover:bg-primary/90",
		secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
		outline: "border border-border bg-transparent hover:bg-accent hover:text-accent-foreground",
		ghost: "hover:bg-accent hover:text-accent-foreground text-muted-foreground",
		destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
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
