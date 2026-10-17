import { ExternalLink } from "lucide-react";
import { EvidenceFrames } from "@/components/watch/evidence-frames";
import type { Violation } from "@/lib/api/contracts";

/** Body of one accordion item: what was seen, which rule applies, and the frames. */
export function ViolationCard({
	jobId,
	violation,
}: {
	jobId: string;
	violation: Violation;
}) {
	return (
		<div className="flex flex-col gap-4">
			<p className="text-sm leading-relaxed whitespace-pre-line">
				{violation.description}
			</p>

			<div className="flex flex-col gap-2 rounded-xl bg-secondary p-3">
				<p className="text-xs font-medium text-muted-foreground">Правило</p>
				<p className="text-sm leading-relaxed">{violation.rule.text}</p>
				<ul className="flex flex-col gap-1">
					{violation.rule.sources.map((source) => (
						<li key={`${source.url}-${source.section ?? ""}`}>
							<a
								href={source.url}
								target="_blank"
								rel="noopener noreferrer"
								className="inline-flex items-start gap-1 text-xs text-info underline underline-offset-2 hover:text-foreground"
							>
								<span>
									{source.document_title}
									{source.section ? `, ${source.section}` : ""}
								</span>
								<ExternalLink className="mt-0.5 size-3 shrink-0" aria-hidden />
							</a>
						</li>
					))}
				</ul>
			</div>

			<EvidenceFrames
				jobId={jobId}
				violationId={violation.id}
				frames={violation.evidence_frames}
			/>
		</div>
	);
}
