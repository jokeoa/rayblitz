import { Skeleton } from "@/components/ui/skeleton";

/** Shown while the session is being checked, shaped like the real shell. */
export function AppShellSkeleton() {
	return (
		<div className="flex min-h-dvh w-full">
			<div className="hidden w-64 shrink-0 flex-col gap-3 border-r bg-sidebar p-3 md:flex">
				<Skeleton className="h-8 w-36" />
				<Skeleton className="h-9 w-full" />
				<Skeleton className="h-9 w-full" />
				<Skeleton className="h-9 w-full" />
				<div className="mt-auto">
					<Skeleton className="h-14 w-full rounded-2xl" />
				</div>
			</div>
			<div className="flex-1 p-6">
				<Skeleton className="h-8 w-48" />
				<Skeleton className="mt-6 h-40 w-full rounded-2xl" />
			</div>
		</div>
	);
}
