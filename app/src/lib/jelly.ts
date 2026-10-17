import {
	animate,
	type MotionValue,
	motionValue,
	useTransform,
} from "motion/react";

/**
 * The jelly spring shared by `JellyRadio` and the timeline markers: the chosen
 * element swells, the rest give up a little, and the wide axis rings before the
 * tall one.
 */
export type JellyValues = {
	x: MotionValue<number>;
	sx: MotionValue<number>;
	sy: MotionValue<number>;
};

export type JellyTuning = {
	jelly: number;
	bounce: number;
	/** Milliseconds per step of distance before a neighbour moves. */
	stagger: number;
	stiffness: number;
	reduce: boolean | null;
};

export const createJellyValues = (): JellyValues => ({
	x: motionValue(0),
	sx: motionValue(1),
	sy: motionValue(1),
});

export const destroyJellyValues = (mv: JellyValues) => {
	mv.x.destroy();
	mv.sx.destroy();
	mv.sy.destroy();
};

const spring = (stiffness: number, mass: number, bounce: number) => ({
	type: "spring" as const,
	stiffness,
	damping: 2 * Math.sqrt(stiffness * mass) * (1 - bounce),
	mass,
});

/** Move one element to `x` px and uniform scale `s`; `far` is its distance from the chosen one. */
export function jellyTo(
	mv: JellyValues,
	x: number,
	s: number,
	far: number,
	tuning: JellyTuning,
	instant = false,
) {
	if (instant || tuning.reduce) {
		mv.x.jump(x);
		mv.sx.jump(s);
		mv.sy.jump(s);
		return;
	}
	const k = tuning.stiffness * (1 - 0.12 * Math.min(far, 3));
	const inFlight =
		mv.x.isAnimating() || mv.sx.isAnimating() || mv.sy.isAnimating();
	const delay = inFlight ? 0 : (far * tuning.stagger) / 1000;
	const j = tuning.jelly;
	animate(mv.x, x, { ...spring(k, 0.9, tuning.bounce), delay });
	animate(mv.sx, s, {
		...spring(
			k * (1 + 0.24 * j),
			0.9 - 0.1 * j,
			Math.min(0.85, tuning.bounce + 0.3 * j),
		),
		delay,
	});
	animate(mv.sy, s, {
		...spring(k * (1 - 0.14 * j), 0.9 + 0.05 * j, tuning.bounce),
		delay: delay + 0.05 * j,
	});
}

/** CSS transform driven by the jelly values, so springs never re-render React. */
export function useJellyTransform(mv: JellyValues) {
	return useTransform(
		() => `translateX(${mv.x.get()}px) scale(${mv.sx.get()}, ${mv.sy.get()})`,
	);
}
