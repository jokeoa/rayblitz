import {
	CircleAlert,
	CircleCheck,
	CircleHelp,
	CircleX,
	RefreshCw,
} from "lucide-react";
import { Line, LineChart, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardAction,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import {
	type ChartConfig,
	ChartContainer,
	ChartTooltip,
	ChartTooltipContent,
} from "@/components/ui/chart";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { type HealthKind, useHealth } from "@/hooks/use-health";
import type { ServiceHealth } from "@/lib/api/health-contracts";
import { DEV_TOOLS, IS_MOCK } from "@/lib/app-mode";
import { formatClock } from "@/lib/format";
import { cn } from "@/lib/utils";
import { type HealthSample, useHealthStore } from "@/stores/health-store";

type ServiceStatus = ServiceHealth["status"];

const STATUS = {
	ok: {
		label: "Работает",
		Icon: CircleCheck,
		tone: "text-success",
		fill: "bg-success",
	},
	error: {
		label: "Сбой",
		Icon: CircleX,
		tone: "text-destructive",
		fill: "bg-destructive",
	},
	unknown: {
		label: "Нет данных",
		Icon: CircleHelp,
		tone: "text-warning",
		fill: "bg-warning",
	},
} as const;

const OVERALL: Record<HealthKind, { title: string; hint: string }> = {
	checking: {
		title: "Проверяем сервисы",
		hint: "Это займёт несколько секунд.",
	},
	ok: { title: "Все сервисы работают", hint: "Можно загружать новые видео." },
	degraded: {
		title: "Часть сервисов недоступна",
		hint: "Загрузка новых видео отключена. Готовые результаты доступны.",
	},
	unavailable: {
		title: "Сервис недоступен",
		hint: "Загрузка новых видео отключена. Готовые результаты доступны.",
	},
	unknown: {
		title: "Статус неизвестен",
		hint: "Нет связи с сервером. Последний известный статус не показывается как актуальный.",
	},
};

const chartConfig = {
	latencyMs: { label: "Отклик, мс", color: "var(--chart-1)" },
} satisfies ChartConfig;

const median = (values: number[]) => {
	if (values.length === 0) return null;
	const sorted = [...values].sort((a, b) => a - b);
	return sorted[Math.floor(sorted.length / 2)];
};

function AvailabilityStrip({
	samples,
	pick,
}: {
	samples: HealthSample[];
	pick: (sample: HealthSample) => ServiceStatus | "unreachable";
}) {
	const recent = samples.slice(-24);
	const ok = recent.filter((sample) => pick(sample) === "ok").length;
	return (
		<div
			role="img"
			aria-label={`Последние проверки: ${ok} из ${recent.length} успешных`}
			className="flex h-4 items-end gap-0.5"
		>
			{recent.map((sample) => {
				const status = pick(sample);
				return (
					<span
						key={sample.at}
						className={cn(
							"h-full w-1 rounded-full",
							status === "ok" && "bg-success",
							status === "error" && "bg-destructive",
							status === "unknown" && "bg-warning",
							status === "unreachable" && "bg-input",
						)}
					/>
				);
			})}
		</div>
	);
}

function ServiceRow({
	name,
	service,
	samples,
	pick,
}: {
	name: string;
	service: ServiceHealth | null;
	samples: HealthSample[];
	pick: (sample: HealthSample) => ServiceStatus | "unreachable";
}) {
	const status = service?.status ?? "unknown";
	const { label, Icon, tone } = STATUS[status];
	return (
		<div className="flex flex-col gap-2">
			<div className="flex items-center justify-between gap-3">
				<div className="flex items-center gap-2">
					<Icon className={cn("size-4", tone)} aria-hidden />
					<span className="text-sm font-medium">{name}</span>
				</div>
				<Badge variant="outline" className={tone}>
					{service ? label : "Нет данных"}
				</Badge>
			</div>
			<p className="text-sm text-muted-foreground">
				{service?.message ?? "Нет связи с сервером, статус не подтверждён."}
			</p>
			<AvailabilityStrip samples={samples} pick={pick} />
		</div>
	);
}

function Metric({
	label,
	value,
	unit,
}: {
	label: string;
	value: string;
	unit?: string;
}) {
	return (
		<div className="flex flex-col gap-0.5">
			<dt className="text-xs text-muted-foreground">{label}</dt>
			<dd className="font-mono text-lg tabular leading-tight">
				{value}
				{unit ? (
					<span className="ml-1 text-xs text-muted-foreground">{unit}</span>
				) : null}
			</dd>
		</div>
	);
}

export function HealthPanel() {
	const { kind, health, latencyMs, isFetching, refetch } = useHealth();
	const samples = useHealthStore((state) => state.samples);

	const overall = OVERALL[kind];
	const OverallIcon =
		kind === "ok"
			? CircleCheck
			: kind === "checking"
				? RefreshCw
				: kind === "unknown"
					? CircleHelp
					: CircleAlert;
	const overallTone =
		kind === "ok"
			? "text-success"
			: kind === "unavailable"
				? "text-destructive"
				: kind === "checking"
					? "text-muted-foreground"
					: "text-warning";

	const reachable = samples.filter((sample) => sample.reachable);
	const latencies = reachable
		.map((sample) => sample.latencyMs)
		.filter((value): value is number => value !== null);
	const availability =
		samples.length === 0
			? null
			: Math.round(
					(samples.filter((sample) => sample.overall === "ok").length /
						samples.length) *
						100,
				);
	const chartData = samples.map((sample) => ({
		at: sample.at,
		latencyMs: sample.latencyMs,
	}));

	return (
		<section aria-labelledby="health-title" className="flex flex-col gap-3">
			<div className="flex items-center justify-between gap-3">
				<h2
					id="health-title"
					className="text-base font-semibold tracking-tight"
				>
					Состояние сервисов
				</h2>
				<div className="flex items-center gap-2">
					{health ? (
						<span className="text-xs tabular text-muted-foreground">
							Проверено {formatClock(health.checked_at)}
						</span>
					) : null}
					<Button
						variant="ghost"
						size="icon-sm"
						aria-label="Проверить сейчас"
						disabled={isFetching}
						onClick={refetch}
					>
						<RefreshCw
							className={cn(
								isFetching && "animate-spin motion-reduce:animate-none",
							)}
							aria-hidden
						/>
					</Button>
				</div>
			</div>

			<div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
				<Card>
					<CardHeader>
						<CardTitle className="flex items-center gap-2 text-lg">
							<OverallIcon className={cn("size-5", overallTone)} aria-hidden />
							{overall.title}
						</CardTitle>
						<CardDescription>{overall.hint}</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-col gap-5">
						{kind === "checking" ? (
							<Skeleton className="h-20 w-full rounded-xl" />
						) : (
							<ChartContainer config={chartConfig} className="h-20 w-full">
								<LineChart
									data={chartData}
									margin={{ top: 6, right: 4, bottom: 6, left: 4 }}
								>
									<XAxis dataKey="at" hide />
									<YAxis hide domain={[0, "dataMax + 20"]} />
									<ChartTooltip
										cursor={false}
										content={
											<ChartTooltipContent
												hideLabel
												labelFormatter={(_, payload) => {
													const at = payload?.[0]?.payload?.at;
													return at ? formatClock(at) : "";
												}}
											/>
										}
									/>
									<Line
										dataKey="latencyMs"
										type="monotone"
										stroke="var(--color-latencyMs)"
										strokeWidth={1.5}
										dot={false}
										connectNulls={false}
										isAnimationActive={false}
									/>
								</LineChart>
							</ChartContainer>
						)}
						<dl className="grid grid-cols-3 gap-4">
							<Metric
								label="Отклик сейчас"
								value={latencyMs === null ? "нет" : String(latencyMs)}
								unit={latencyMs === null ? undefined : "мс"}
							/>
							<Metric
								label="Медиана"
								value={
									median(latencies) === null ? "нет" : String(median(latencies))
								}
								unit={median(latencies) === null ? undefined : "мс"}
							/>
							<Metric
								label="Доступность"
								value={availability === null ? "нет" : String(availability)}
								unit={availability === null ? undefined : "%"}
							/>
						</dl>
					</CardContent>
				</Card>

				<Card>
					<CardHeader>
						<CardTitle className="text-base">Сервисы</CardTitle>
						<CardDescription>Проверка каждые 10 секунд.</CardDescription>
						{DEV_TOOLS && IS_MOCK ? (
							<CardAction>
								<Badge variant="secondary">mock</Badge>
							</CardAction>
						) : null}
					</CardHeader>
					<CardContent className="flex flex-col gap-4">
						<ServiceRow
							name="Бэкенд"
							service={health?.services.backend ?? null}
							samples={samples}
							pick={(sample) =>
								sample.reachable ? sample.backend : "unreachable"
							}
						/>
						<Separator />
						<ServiceRow
							name="GPU-сервер"
							service={health?.services.gpu_server ?? null}
							samples={samples}
							pick={(sample) => (sample.reachable ? sample.gpu : "unreachable")}
						/>
					</CardContent>
				</Card>
			</div>

			{DEV_TOOLS && health ? (
				<details className="rounded-2xl border bg-secondary/40 px-4 py-3 text-xs">
					<summary className="cursor-pointer font-medium">
						Ответ /health (debug)
					</summary>
					<pre className="mt-2 overflow-x-auto font-mono leading-relaxed">
						{JSON.stringify(health, null, 2)}
					</pre>
				</details>
			) : null}
		</section>
	);
}
