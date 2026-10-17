import { useEffect, useState } from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { avatarPng, avatarSvg } from "@/lib/avatar";
import { cn } from "@/lib/utils";

/**
 * Lorelei avatar from @dicebear/core. The SVG renders immediately; the
 * @dicebear/converter PNG replaces it once the canvas rasterisation finishes.
 */
export function UserAvatar({
	seed,
	name,
	className,
}: {
	seed: string;
	name: string;
	className?: string;
}) {
	const [src, setSrc] = useState(() => avatarSvg(seed));

	useEffect(() => {
		let active = true;
		setSrc(avatarSvg(seed));
		avatarPng(seed)
			.then((png) => {
				if (active) setSrc(png);
			})
			.catch(() => {
				// The SVG already on screen is a fine fallback.
			});
		return () => {
			active = false;
		};
	}, [seed]);

	return (
		<Avatar className={cn("size-8 bg-secondary", className)}>
			<AvatarImage src={src} alt="" />
			<AvatarFallback>{name.slice(0, 2).toUpperCase()}</AvatarFallback>
		</Avatar>
	);
}
