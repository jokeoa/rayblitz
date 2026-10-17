import { cn } from "@/lib/utils";

/*
 * RayBlitz brand mark, exported from the Figma frame (node 1-716).
 * Coordinates are in the 214x214 artboard of the mark.
 */

// White swoosh ("R" bowl and tail); path is local to its own 88.87x141.55 box.
// Rainbow stripes: rows run top to bottom (Tailwind shades 50 -> 500),
// columns run left to right (red -> rose).



/*
 * RayBlitz wordmark, exported from the Figma frame (node 1-713): Geist, "Ray"
 * SemiBold + "Blitz" Thin at 115.2px. Sized by the inherited font-size and
 * coloured by the inherited text colour; set `text-*` classes to scale or
 * recolour it.
 */
function Wordmark({ className, ...props }: React.ComponentProps<"span">) {
	return (
		<span
			role="img"
			aria-label="RayBlitz"
			className={cn("inline-block whitespace-nowrap leading-none", className)}
			{...props}
		>
			<span aria-hidden className="font-semibold">
				Ray
			</span>
			<span aria-hidden className="font-thin">
				Blitz
			</span>
		</span>
	);
}

/*
 * Sized by font-size, like the Figma lockup: mark is 214/115.2 em, the gap is
 * 64/115.2 em. Override with a `text-*` class on the wrapper to scale it.
 */
function Logo({
	className
}: {
	className?: string;
	markClassName?: string;
}) {
	return (
		<span
			className={cn(
				"inline-flex items-center gap-[0.556em] text-[1.625rem]",
				className,
			)}
		>

			<Wordmark aria-hidden />
		</span>
	);
}

export { Logo, Wordmark };
