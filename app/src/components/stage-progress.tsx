import {
	CircleAlert,
	CircleCheck,
	CircleDashed,
	LoaderCircle,
} from "lucide-react";
import { Progress } from "@/components/ui/progress";
import type { Progress as ProgressData } from "@/lib/api/contracts";
import { cn } from "@/lib/utils";

const ICON = {
	done: CircleCheck,
	running: LoaderCircle,
	failed: CircleAlert,
	pending: CircleDashed,
} as const;

/**
 * Renders whatever stage plan the backend sends. Labels, descriptions, count
 * and order are data; nothing here switches on stage ids.
 */
export function StageProgress({ progress }: { progress: ProgressData }) {
	return (
		<div className="flex flex-col gap-4">
			<Progress value={progress.percent} className="gap-2">
				<div className="flex w-full items-baseline justify-between text-sm">
					<span className="font-medium">Общий прогресс</span>
					<span className="font-mono tabular text-muted-foreground">
						{Math.floor(progress.percent)}%
					</span>
				</div>
			</Progress>
			<ol className="flex flex-col gap-3">
				{progress.stages.map((stage) => {
					const Icon = ICON[stage.status];
					return (
						<li key={stage.id} className="flex items-start gap-3">
							<Icon
								aria-hidden
								className={cn(
									"mt-0.5 size-4 shrink-0",
									stage.status === "done" && "text-success",
									stage.status === "running" && "animate-spin text-info",
									stage.status === "failed" && "text-destructive",
									stage.status === "pending" && "text-muted-foreground",
								)}
							/>
							<div className="min-w-0 flex-1">
								<div className="flex items-baseline justify-between gap-3">
									<p
										className={cn(
											"text-sm font-medium",
											stage.status === "pending" && "text-muted-foreground",
										)}
									>
										{stage.label}
									</p>
									{stage.status === "running" || stage.status === "failed" ? (
										<span className="font-mono text-xs tabular text-muted-foreground">
											{Math.floor(stage.percent)}%
										</span>
									) : null}
								</div>
								<p className="text-xs text-muted-foreground">
									{stage.description}
								</p>
							</div>
						</li>
					);
				})}
			</ol>
		</div>
	);
}
