import { type HTMLMotionProps, motion, useReducedMotion } from "motion/react";
import {
	type CSSProperties,
	forwardRef,
	type KeyboardEvent,
	type ReactNode,
	useEffect,
	useLayoutEffect,
	useRef,
	useState,
} from "react";

import {
	createJellyValues,
	destroyJellyValues,
	type JellyTuning,
	type JellyValues,
	jellyTo,
	useJellyTransform,
} from "@/lib/jelly";

import "./jelly-radio.css";

/** React Bits `JellyRadio`, ported to TypeScript. */

export type JellyRadioItem =
	| string
	| { value: string; label: ReactNode; icon?: ReactNode; disabled?: boolean };

export type JellyRadioProps = {
	items?: JellyRadioItem[];
	/** Controlled value. Outside changes jump. */
	value?: string;
	/** Initial value when uncontrolled. Falls back to the first item. */
	defaultValue?: string;
	/** Called on the commit, before the motion ends. */
	onChange?: (value: string, index: number) => void;
	chipColor?: string;
	activeColor?: string;
	textColor?: string;
	activeTextColor?: string;
	/** Chip height 28, 36 or 44 pixels. Large is the touch-first size. */
	size?: "sm" | "md" | "lg";
	gap?: number;
	radius?: number;
	/** How much the chosen chip grows. It also sets the room the neighbours make. */
	swell?: number;
	/** Extra pixels every neighbour is shoved beyond that room. */
	barge?: number;
	/** How much every unchosen chip gives up. */
	shrink?: number;
	/** The wide-before-tall split. 0 swells uniformly, 1.5 exaggerates it. */
	jelly?: number;
	/** One minus the damping ratio. 0 arrives and stops, 0.4 rings. */
	bounce?: number;
	/** Milliseconds per row step before a neighbour moves. */
	stagger?: number;
	/** Spring stiffness of the chosen chip. Neighbours soften from it with distance. */
	stiffness?: number;
	disabled?: boolean;
	ariaLabel?: string;
	className?: string;
};

type Tuning = JellyTuning & {
	swell: number;
	barge: number;
	shrink: number;
	count: number;
};

const DEFAULT_ITEMS = ["Off", "Low", "Medium", "High", "Max"];
/** Chip height, font size and horizontal padding per size. */
const SIZES = { sm: [28, 12, 12], md: [36, 13, 16], lg: [44, 14, 20] } as const;

const Chip = forwardRef<
	HTMLButtonElement,
	{ mv: JellyValues } & Omit<HTMLMotionProps<"button">, "style" | "ref">
>(function Chip({ mv, children, ...rest }, ref) {
	const transform = useJellyTransform(mv);
	return (
		<motion.button ref={ref} style={{ transform }} {...rest}>
			{children}
		</motion.button>
	);
});

export function JellyRadio({
	items = DEFAULT_ITEMS,
	value,
	defaultValue,
	onChange,
	chipColor = "#27272a",
	activeColor = "#f5f5f5",
	textColor = "#f5f5f5",
	activeTextColor = "#18181b",
	size = "md",
	gap = 8,
	radius = 18,
	swell = 0.2,
	barge = 6,
	shrink = 0.05,
	jelly = 1,
	bounce = 0.25,
	stagger = 22,
	stiffness = 580,
	disabled = false,
	ariaLabel = "Options",
	className = "",
}: JellyRadioProps) {
	const list = items.map((item) =>
		typeof item === "string" ? { value: item, label: item as ReactNode } : item,
	);
	const [inner, setInner] = useState(() => defaultValue ?? list[0]?.value);
	const current = value ?? inner;
	const at = Math.max(
		0,
		list.findIndex((item) => item.value === current),
	);
	const reduce = useReducedMotion();
	const groupRef = useRef<HTMLDivElement>(null);
	const chipRefs = useRef<(HTMLButtonElement | null)[]>([]);
	const widths = useRef<number[]>([]);
	const mvs = useRef<JellyValues[]>([]);
	const applied = useRef(at);
	const cfg = useRef<Tuning>({} as Tuning);
	cfg.current = {
		swell,
		barge,
		shrink,
		jelly,
		bounce,
		stagger,
		stiffness,
		reduce,
		count: list.length,
	};
	const [h, font, px] = SIZES[size] ?? SIZES.md;
	const itemsKey = list.map((item) => item.value).join("|");

	const mvFor = (i: number) => {
		let mv = mvs.current[i];
		if (!mv) {
			mv = createJellyValues();
			mvs.current[i] = mv;
		}
		return mv;
	};

	const apply = (sel: number, instant: boolean) => {
		const C = cfg.current;
		const group = groupRef.current;
		const rtl = group ? getComputedStyle(group).direction === "rtl" : false;
		const push = ((widths.current[sel] ?? 0) * C.swell) / 2 + C.barge;
		for (let i = 0; i < C.count; i++) {
			const on = i === sel;
			const dir = Math.sign(i - sel) * (rtl ? -1 : 1);
			jellyTo(
				mvFor(i),
				dir * push,
				on ? 1 + C.swell : 1 - C.shrink,
				Math.abs(i - sel),
				C,
				instant,
			);
		}
	};

	const measure = () => {
		const group = groupRef.current;
		if (!group) return;
		widths.current = chipRefs.current.map((el) => el?.offsetWidth ?? 0);
		const chipH = chipRefs.current[0]?.offsetHeight ?? 0;
		const maxW = Math.max(0, ...widths.current);
		group.style.setProperty(
			"--jr-pad-x",
			`${Math.ceil((maxW * swell * 1.3) / 2 + barge) + 2}px`,
		);
		group.style.setProperty(
			"--jr-pad-y",
			`${Math.ceil((chipH * swell) / 2) + 2}px`,
		);
	};
	// measure and apply read the latest props through refs; only layout-affecting props re-run this.
	useLayoutEffect(() => {
		const settle = () => {
			measure();
			apply(applied.current, true);
		};
		settle();
		const observer = new ResizeObserver(settle);
		if (groupRef.current) observer.observe(groupRef.current);
		void document.fonts?.ready.then(settle);
		return () => observer.disconnect();
	}, [itemsKey, size, gap, swell, barge, shrink]);
	useEffect(() => {
		if (applied.current === at) return;
		applied.current = at;
		apply(at, true);
	}, [at]);
	useEffect(
		() => () => {
			for (const mv of mvs.current) destroyJellyValues(mv);
		},
		[],
	);

	const commit = (i: number, instant: boolean) => {
		if (disabled || i === at || !list[i] || list[i].disabled) return;
		applied.current = i;
		apply(i, instant);
		if (value === undefined) setInner(list[i].value);
		onChange?.(list[i].value, i);
	};
	const stepFrom = (i: number, dir: 1 | -1) => {
		const n = list.length;
		let j = i;
		for (let tries = 0; tries < n; tries++) {
			j = (j + dir + n) % n;
			if (!list[j].disabled) return j;
		}
		return i;
	};
	const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, i: number) => {
		let next: number | null = null;
		if (e.key === "ArrowRight" || e.key === "ArrowDown") next = stepFrom(i, 1);
		else if (e.key === "ArrowLeft" || e.key === "ArrowUp")
			next = stepFrom(i, -1);
		else if (e.key === "Home") next = stepFrom(-1, 1);
		else if (e.key === "End") next = stepFrom(list.length, -1);
		else if (e.key === " " || e.key === "Enter") next = i;
		if (next === null) return;
		e.preventDefault();
		commit(next, true);
		chipRefs.current[next]?.focus();
	};

	return (
		<div
			ref={groupRef}
			role="radiogroup"
			aria-label={ariaLabel}
			data-disabled={disabled ? "" : undefined}
			className={`jelly-radio${className ? ` ${className}` : ""}`}
			style={
				{
					"--jr-chip": chipColor,
					"--jr-active": activeColor,
					"--jr-text": textColor,
					"--jr-active-text": activeTextColor,
					"--jr-gap": `${gap}px`,
					"--jr-radius": `${radius}px`,
					"--jr-h": `${h}px`,
					"--jr-font": `${font}px`,
					"--jr-px": `${px}px`,
				} as CSSProperties
			}
		>
			{list.map((item, i) => (
				<Chip
					key={item.value}
					mv={mvFor(i)}
					ref={(el) => {
						chipRefs.current[i] = el;
					}}
					type="button"
					role="radio"
					aria-checked={i === at}
					tabIndex={i === at ? 0 : -1}
					disabled={disabled || !!item.disabled}
					className="jelly-radio__chip"
					data-on={i === at ? "true" : "false"}
					onClick={(e) => commit(i, e.detail === 0)}
					onKeyDown={(e) => onKeyDown(e, i)}
				>
					<span className="jelly-radio__skin">
						{item.icon ? (
							<span className="jelly-radio__icon">{item.icon}</span>
						) : null}
						<span className="jelly-radio__label">{item.label}</span>
					</span>
				</Chip>
			))}
		</div>
	);
}
