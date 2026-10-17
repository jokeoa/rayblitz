import { CircleCheck, TriangleAlert } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** Verdict wording is fixed by docs/api-contract.md; no third verdict exists. */
export const VERDICT_LABEL = {
	no_violation: "Нарушение не обнаружено",
	violation: "Обнаружены признаки возможных нарушений",
} as const;

export function VerdictBadge({
	verdict,
	className,
}: {
	verdict: keyof typeof VERDICT_LABEL;
	className?: string;
}) {
	const violation = verdict === "violation";
	const Icon = violation ? TriangleAlert : CircleCheck;
	return (
		<Badge
			variant="outline"
			className={cn(
				"h-auto min-h-5 whitespace-normal py-0.5 text-left",
				violation
					? "border-transparent bg-danger-soft text-destructive"
					: "border-transparent bg-success-soft text-success",
				className,
			)}
		>
			<Icon aria-hidden />
			{VERDICT_LABEL[verdict]}
		</Badge>
	);
}
