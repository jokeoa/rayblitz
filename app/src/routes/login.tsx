import { useMutation } from "@tanstack/react-query";
import { createFileRoute, redirect, useNavigate } from "@tanstack/react-router";
import { CircleAlert, ClipboardPaste, Eye, EyeOff } from "lucide-react";
import { useId, useRef, useState } from "react";
import { toast } from "sonner";
import { z } from "zod";
import { LaserFlow, type LaserFlowProps } from "@/components/laser-flow";
import { Logo } from "@/components/logo";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
	Field,
	FieldError,
	FieldGroup,
	FieldLabel,
} from "@/components/ui/field";
import {
	InputGroup,
	InputGroupAddon,
	InputGroupButton,
	InputGroupInput,
} from "@/components/ui/input-group";
import { Spinner } from "@/components/ui/spinner";
import { isApiError } from "@/lib/api/client";
import { login } from "@/lib/api/review";
import { getSessionState } from "@/server/auth.functions";
import { useAuthStore } from "@/stores/auth-store";

export const Route = createFileRoute("/login")({
	validateSearch: z.object({
		reason: z.enum(["expired", "signed-out"]).optional(),
	}),
	beforeLoad: async () => {
		const state = await getSessionState();
		if (state.authenticated) throw redirect({ to: "/" });
	},
	component: LoginPage,
});

function loginErrorMessage(error: unknown): string {
	if (isApiError(error)) {
		if (error.code === "UNAUTHORIZED") {
			return "Ключ не принят. Проверьте, что он вставлен полностью.";
		}
		if (error.code === "NETWORK")
			return "Нет связи с сервером. Проверьте подключение.";
		return error.message;
	}
	return "Не удалось войти. Повторите попытку.";
}

// Two mirrored scanner beams, one from each side, sweeping top to bottom.
const SCANNER = {
	sweepMode: "scan",
	sweepPeriod: 4.5,
	sweepRest: 1,
	sweepFade: 0.3,
	intro: false,
	baseGlow: 0,
	wrap: "contour",
	wrapIntensity: 0.9,
	wrapReach: 80,
	wrapBloom: 1.4,
	color: "#ff9433",
	intensity: 1.6,
	fog: 0.25,
	dust: 1.4,
	className: "absolute inset-0 -z-10",
} satisfies Partial<LaserFlowProps>;

function LoginPage() {
	const { reason } = Route.useSearch();
	const navigate = useNavigate();
	const setProfile = useAuthStore((state) => state.setProfile);
	const keyId = useId();
	const errorId = useId();
	const [apiKey, setApiKey] = useState("");
	const [visible, setVisible] = useState(false);
	const cardRef = useRef<HTMLDivElement>(null);

	const mutation = useMutation({
		mutationFn: login,
		onSuccess: ({ profile, verified }) => {
			setProfile(profile);
			if (!verified) {
				toast.warning("Сервис анализа недоступен, ключ не проверен.", {
					description: "Он будет проверен при первом обращении к анализатору.",
				});
			}
			void navigate({ to: "/" });
		},
	});

	const paste = async () => {
		try {
			const text = await navigator.clipboard.readText();
			if (text.trim()) setApiKey(text.trim());
		} catch {
			toast.error("Нет доступа к буферу обмена. Вставьте ключ вручную.");
		}
	};

	const invalid = mutation.isError;

	return (
		<main className="relative isolate grid min-h-dvh place-items-center bg-black px-4 py-12 text-white">
			<LaserFlow {...SCANNER} surfaceRef={cardRef} direction="right" />
			<LaserFlow {...SCANNER} surfaceRef={cardRef} direction="left" />
			<div className="flex w-full max-w-sm flex-col items-center gap-10">
				<Logo />
				<Card ref={cardRef} className="w-full shadow-overlay">
					<CardHeader>
						<CardTitle className="text-xl font-semibold tracking-tight">
							Вход по API-ключу
						</CardTitle>
					</CardHeader>
					<CardContent>
						<form
							noValidate
							onSubmit={(event) => {
								event.preventDefault();
								if (apiKey.trim()) mutation.mutate(apiKey.trim());
							}}
						>
							<FieldGroup>
								{reason ? (
									<Alert>
										<CircleAlert aria-hidden />
										<AlertDescription>
											{reason === "expired"
												? "Сеанс завершён. Вставьте ключ ещё раз."
												: "Вы вышли. История на этом устройстве очищена."}
										</AlertDescription>
									</Alert>
								) : null}

								<Field data-invalid={invalid || undefined}>
									<FieldLabel htmlFor={keyId}>API-ключ</FieldLabel>
									<InputGroup>
										<InputGroupInput
											id={keyId}
											name="api_key"
											type={visible ? "text" : "password"}
											autoComplete="off"
											autoCapitalize="off"
											spellCheck={false}
											autoFocus
											required
											value={apiKey}
											onChange={(event) => setApiKey(event.target.value)}
											aria-invalid={invalid}
											aria-describedby={invalid ? errorId : undefined}
											placeholder="Вставьте ключ"
											className="font-mono"
										/>
										<InputGroupAddon align="inline-end">
											<InputGroupButton
												size="icon-xs"
												aria-label="Вставить из буфера обмена"
												onClick={paste}
											>
												<ClipboardPaste aria-hidden />
											</InputGroupButton>
											<InputGroupButton
												size="icon-xs"
												aria-label={visible ? "Скрыть ключ" : "Показать ключ"}
												aria-pressed={visible}
												onClick={() => setVisible((value) => !value)}
											>
												{visible ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
											</InputGroupButton>
										</InputGroupAddon>
									</InputGroup>
									{invalid ? (
										<FieldError id={errorId}>
											{loginErrorMessage(mutation.error)}
										</FieldError>
									) : null}
								</Field>

								<Button
									type="submit"
									size="lg"
									className="w-full"
									disabled={!apiKey.trim() || mutation.isPending}
								>
									{mutation.isPending ? (
										<Spinner data-icon="inline-start" />
									) : null}
									{mutation.isPending ? "Проверяем ключ" : "Войти"}
								</Button>
							</FieldGroup>
						</form>
					</CardContent>
				</Card>
			</div>
		</main>
	);
}
