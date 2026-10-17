import { Slider as SliderPrimitive } from "@base-ui/react/slider";
import { cn } from "cn";

type SliderProps = SliderPrimitive.Root.Props & {
	/** Extra classes for the interactive control that hosts the track and thumb. */
	controlClassName?: string;
	trackClassName?: string;
	indicatorClassName?: string;
	thumbClassName?: string;
};

function Slider({
	className,
	controlClassName,
	trackClassName,
	indicatorClassName,
	thumbClassName,
	defaultValue,
	value,
	min = 0,
	max = 100,
	...props
}: SliderProps) {
	const _values = Array.isArray(value)
		? value
		: Array.isArray(defaultValue)
			? defaultValue
			: [min, max];

	return (
		<SliderPrimitive.Root
			className={cn("data-horizontal:w-full data-vertical:h-full", className)}
			data-slot="slider"
			defaultValue={defaultValue}
			value={value}
			min={min}
			max={max}
			thumbAlignment="edge"
			{...props}
		>
			<SliderPrimitive.Control
				className={cn(
					"relative flex w-full touch-none items-center select-none data-disabled:opacity-50 data-vertical:h-full data-vertical:min-h-40 data-vertical:w-auto data-vertical:flex-col",
					controlClassName,
				)}
			>
				<SliderPrimitive.Track
					data-slot="slider-track"
					className={cn(
						"relative grow overflow-hidden rounded-full bg-input/90 select-none data-horizontal:h-2 data-horizontal:w-full data-vertical:h-full data-vertical:w-2",
						trackClassName,
					)}
				>
					<SliderPrimitive.Indicator
						data-slot="slider-range"
						className={cn(
							"bg-primary select-none data-horizontal:h-full data-vertical:w-full",
							indicatorClassName,
						)}
					/>
				</SliderPrimitive.Track>
				{Array.from({ length: _values.length }, (_, index) => (
					<SliderPrimitive.Thumb
						data-slot="slider-thumb"
						key={index}
						className={cn(
							"block h-4 w-6 shrink-0 rounded-full bg-white shadow-md ring-1 ring-black/10 transition-[color,box-shadow,background-color] select-none not-dark:bg-clip-padding hover:ring-4 hover:ring-ring/30 focus-visible:ring-4 focus-visible:ring-ring/30 focus-visible:outline-hidden disabled:pointer-events-none disabled:opacity-50 data-vertical:h-6 data-vertical:w-4",
							thumbClassName,
						)}
					/>
				))}
			</SliderPrimitive.Control>
		</SliderPrimitive.Root>
	);
}

export { Slider };
