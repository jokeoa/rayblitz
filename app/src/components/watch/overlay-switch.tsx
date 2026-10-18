import { Switch } from "@base-ui/react/switch";
import { useOverlayStore } from "@/stores/overlay-store";
import { cn } from "@/lib/utils";

export function OverlaySwitch({ className }: { className?: string }) {
	const visible = useOverlayStore((state) => state.visible);
	const setVisible = useOverlayStore((state) => state.setVisible);
	return (
		<label
			className={cn(
				"flex cursor-pointer items-center gap-3 rounded-xl border bg-background px-3 py-2 text-sm font-medium",
				className,
			)}
		>
			<span>Показывать рамки</span>
			<Switch.Root
				checked={visible}
				onCheckedChange={setVisible}
				aria-label="Показывать рамки"
				className="relative inline-flex h-6 w-11 shrink-0 items-center rounded-full bg-neutral-300 p-0.5 transition-colors data-checked:bg-neutral-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
			>
				<Switch.Thumb className="block size-5 rounded-full bg-white shadow-sm transition-transform data-checked:translate-x-5" />
			</Switch.Root>
			<span className="min-w-10 text-xs text-muted-foreground">
				{visible ? "Вкл." : "Выкл."}
			</span>
		</label>
	);
}
