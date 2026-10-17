import { Avatar, Style } from "@dicebear/core";
import lorelei from "@dicebear/styles/lorelei.json";

const style = new Style(lorelei as ConstructorParameters<typeof Style>[0]);
const cache = new Map<string, Promise<string>>();

/** Deterministic lorelei avatar as an SVG data URI. */
export function avatarSvg(seed: string): string {
	return new Avatar(style, { seed, size: 96 }).toDataUri();
}

/**
 * Rasterised variant through @dicebear/converter, which uses a canvas in the
 * browser. Loaded lazily so server rendering never pulls in its Node build.
 */
export function avatarPng(seed: string): Promise<string> {
	let pending = cache.get(seed);
	if (!pending) {
		pending = import("@dicebear/converter").then(({ toPng }) =>
			toPng(new Avatar(style, { seed }), { size: 96 }).toDataUri(),
		);
		cache.set(seed, pending);
	}
	return pending;
}
