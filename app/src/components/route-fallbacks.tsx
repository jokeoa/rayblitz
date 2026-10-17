import { Link, useRouter } from "@tanstack/react-router";
import { SearchX, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "@/components/ui/empty";

export function NotFound() {
	return (
		<main className="grid min-h-dvh place-items-center px-4">
			<Empty className="max-w-md border">
				<EmptyHeader>
					<EmptyMedia variant="icon">
						<SearchX aria-hidden />
					</EmptyMedia>
					<EmptyTitle>Страница не найдена</EmptyTitle>
					<EmptyDescription>
						Такого адреса нет. Вернитесь на дашборд.
					</EmptyDescription>
				</EmptyHeader>
				<EmptyContent>
					<Button render={<Link to="/" />}>На дашборд</Button>
				</EmptyContent>
			</Empty>
		</main>
	);
}

export function RouteError() {
	const router = useRouter();
	return (
		<main className="grid min-h-dvh place-items-center px-4">
			<Empty className="max-w-md border">
				<EmptyHeader>
					<EmptyMedia variant="icon">
						<TriangleAlert aria-hidden />
					</EmptyMedia>
					<EmptyTitle>Что-то пошло не так</EmptyTitle>
					<EmptyDescription>
						Страница не загрузилась. Повторите попытку.
					</EmptyDescription>
				</EmptyHeader>
				<EmptyContent>
					<Button onClick={() => void router.invalidate()}>Повторить</Button>
				</EmptyContent>
			</Empty>
		</main>
	);
}
