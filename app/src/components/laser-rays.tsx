import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

/*
 * Printer-style laser scan as a fullscreen fragment shader, in a single warm
 * amber. Every PERIOD seconds a laser bar sweeps top to bottom over DURATION
 * seconds (accelerating, cruising, braking), then the screen rests black.
 *
 * The bar also lights a horizontal sheet of laser rays in real perspective:
 * the sheet lies in the plane of the bar and runs away from the viewer along
 * the z axis, so its rays point straight into the screen and converge on the
 * vanishing point at the screen centre. The sheet is widest at the bar,
 * collapses to a line as the bar crosses the centre, and opens again on the
 * other side. Light packets stream along the rays toward the viewer.
 *
 * It is meant to sit under opaque content: the card covers the vanishing
 * point, so the rays appear to run in from beneath it.
 */
const PERIOD = 5;
const DURATION = 2.5;

const VERTEX_SOURCE = `
attribute vec2 aPosition;

void main() {
	gl_Position = vec4(aPosition, 0.0, 1.0);
}
`;

const FRAGMENT_SOURCE = `
precision highp float;

uniform vec2 uResolution;
uniform float uDpr;
uniform float uTime;

const float PERIOD = ${PERIOD.toFixed(1)};
const float DURATION = ${DURATION.toFixed(1)};
// Distance in px the bar travels past each edge; the bar fades in and out over
// it, so the visible sweep takes nearly the whole DURATION.
const float REACH = 48.0;
// Width in px of one ray cell, measured in the plane of the bar.
const float CELL = 26.0;

// The one color of the effect; the lamp core is the same amber pushed to white.
const vec3 WARM = vec3(1.0, 0.58, 0.2);
const vec3 HOT = vec3(1.0, 0.87, 0.7);

float hash(vec2 p) {
	return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float noise1(float x) {
	float i = floor(x);
	float f = fract(x);
	f = f * f * (3.0 - 2.0 * f);
	return mix(hash(vec2(i, 0.0)), hash(vec2(i + 1.0, 0.0)), f);
}

// Trapezoidal velocity profile: ramp up, cruise, brake. Maps 0..1 to 0..1.
float carriage(float p) {
	const float a = 0.15;
	const float k = 1.0 / (2.0 * a * (1.0 - a));
	if (p < a) return p * p * k;
	if (p > 1.0 - a) {
		float q = 1.0 - p;
		return 1.0 - q * q * k;
	}
	return (p - 0.5 * a) / (1.0 - a);
}

void main() {
	vec2 size = uResolution / uDpr;
	vec2 px = vec2(gl_FragCoord.x, uResolution.y - gl_FragCoord.y) / uDpr;
	vec2 center = 0.5 * size;

	float phase = mod(uTime, PERIOD);
	float live = step(phase, DURATION);
	float time = clamp(phase / DURATION, 0.0, 1.0);
	float barY = mix(-REACH, size.y + REACH, carriage(time));
	float envelope = live
		* smoothstep(-REACH, 0.0, barY)
		* (1.0 - smoothstep(size.y, size.y + REACH, barY));
	// The lamp warms up over the first 28% of the pass and dims over the last
	// 28%, so the bar fades in and out instead of switching on and off.
	float ignite = smoothstep(0.0, 0.28, time) * (1.0 - smoothstep(0.72, 1.0, time));
	// The ray sheet fades more slowly still: an S-curve squared, which starts
	// and ends very gently, over the first 40% and the last 50% of the pass.
	float easeIn = smoothstep(0.0, 0.4, time);
	float easeOut = 1.0 - smoothstep(0.5, 1.0, time);
	float sheetEnvelope = live * easeIn * easeIn * easeOut * easeOut;

	// --- The bar ---------------------------------------------------------

	// Signed distance in px from the bar; negative means already scanned.
	float d = px.y - barY;
	float core = exp(-d * d / (2.0 * 1.1 * 1.1));
	float inner = exp(-d * d / (2.0 * 7.0 * 7.0));
	float outer = exp(-d * d / (2.0 * 42.0 * 42.0));
	// Bloom: wide, soft halos around the bar.
	float bloom = exp(-d * d / (2.0 * 110.0 * 110.0));
	float haze = exp(-d * d / (2.0 * 260.0 * 260.0));

	// Faint reflections of the lamp in the scanner glass, ahead of the bar.
	float g1 = d - 24.0;
	float g2 = d - 52.0;
	float ghosts = 0.14 * exp(-g1 * g1 / (2.0 * 1.6 * 1.6))
		+ 0.06 * exp(-g2 * g2 / (2.0 * 2.4 * 2.4));

	// The lamp is a row of LED cells whose output drifts and flickers.
	float cells = 0.9 + 0.1 * sin(px.x * 1.0472);
	float drift = 0.88 + 0.12 * noise1(px.x / 80.0 + uTime * 0.9);
	float flicker = 0.95 + 0.05 * hash(vec2(floor(uTime * 30.0), 3.0));
	float lamp = cells * drift * flicker * ignite;

	// Raster afterglow: a bright trace right behind the bar, then a long, cooler
	// tail made of scanlines that each decay a little differently.
	float scanned = min(d, 0.0);
	float behind = step(d, 0.0) * (0.6 * exp(scanned / 16.0) + 0.4 * exp(scanned / 140.0));
	behind *= 1.0 - smoothstep(size.y * 0.7, size.y + REACH, barY);
	float band = floor(px.y / 2.0);
	float raster = (0.35 + 0.65 * mod(band, 2.0)) * (0.55 + 0.45 * hash(vec2(band, 7.0)));
	float grain = 0.8 + 0.2 * hash(floor(px / 2.0) + floor(uTime * 24.0));

	vec3 color = HOT * core * lamp
		+ WARM * inner * 0.75 * lamp
		+ WARM * outer * 0.4 * flicker * ignite
		+ WARM * bloom * 0.3 * flicker * ignite
		+ WARM * haze * 0.14 * flicker * ignite
		+ HOT * ghosts * lamp
		+ WARM * behind * raster * grain * 0.1;
	color *= envelope;

	// --- The ray sheet ---------------------------------------------------

	// The sheet is the plane of the bar. Put the camera at the screen centre,
	// looking along +z, with the bar at depth 1. A point of the plane at depth
	// z and sideways offset X lands at (X, bar) / z from the centre, so a pixel
	// at offset (qx, qy) is at depth z = bar / qy with X = qx * z. The plane
	// only fills the strip between the bar and the horizon (the centre line).
	float bar = barY - center.y;
	float qy = px.y - center.y;
	float inSheet = step(0.0, bar * qy) * step(abs(qy), abs(bar));
	float z = min(abs(bar) / max(abs(qy), 0.5), 60.0);
	float sideways = (px.x - center.x) * z;

	float u = sideways / CELL;
	float cell = floor(u);
	float rays = 0.0;
	float rayGlow = 0.0;
	for (int k = -1; k <= 1; k++) {
		float id = cell + float(k);
		float h = hash(vec2(id, 31.0));
		float pos = id + 0.2 + 0.6 * hash(vec2(id, 47.0));
		float strength = smoothstep(0.3, 1.0, h);
		// Constant width in the plane, so a ray narrows toward the vanishing
		// point; never thinner than a pixel on screen.
		float sigma = max(0.1 + 0.08 * hash(vec2(id, 59.0)), 0.8 * z / CELL);
		float du = u - pos;
		// Packets of light streaming along the ray toward the viewer.
		float packet = 0.35 + 0.65 * pow(fract(z * 0.7 + 3.0 * h + uTime * 1.2), 3.0);
		float lit = strength * packet;
		rays += lit * exp(-du * du / (2.0 * sigma * sigma));
		// Bloom of the ray: the same shaft, 3.5x wider and softer.
		rayGlow += lit * exp(-du * du / (2.0 * 12.25 * sigma * sigma));
	}

	// Rays fade with depth, and the sheet fades out toward both screen sides.
	float depthFade = exp(-(z - 1.0) * 0.8);
	float across = px.x / size.x;
	float edge = smoothstep(0.0, 0.12, across) * (1.0 - smoothstep(0.88, 1.0, across));
	float sheet = inSheet * depthFade * edge * (0.12 + 1.0 * rays + 0.5 * rayGlow);
	color += WARM * sheet * sheetEnvelope * flicker * 0.6;

	// Soft highlight roll-off, so overlapping glows bloom into white-hot
	// instead of clipping flat.
	color = 1.0 - exp(-1.35 * color);

	// Dither the lit area so the glow does not band on 8-bit displays.
	float visible = clamp(max(color.r, max(color.g, color.b)) * 40.0, 0.0, 1.0);
	color += (hash(gl_FragCoord.xy + fract(uTime)) - 0.5) / 255.0 * visible;

	gl_FragColor = vec4(clamp(color, 0.0, 1.0), 1.0);
}
`;

function compile(gl: WebGLRenderingContext, type: number, source: string) {
	const shader = gl.createShader(type);
	if (!shader) return null;
	gl.shaderSource(shader, source);
	gl.compileShader(shader);
	if (gl.getShaderParameter(shader, gl.COMPILE_STATUS)) return shader;
	gl.deleteShader(shader);
	return null;
}

function LaserRays({ className }: { className?: string }) {
	const canvasRef = useRef<HTMLCanvasElement>(null);

	useEffect(() => {
		const canvas = canvasRef.current;
		if (!canvas) return;
		if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

		const gl = canvas.getContext("webgl", {
			alpha: false,
			antialias: false,
			powerPreference: "low-power",
		});
		if (!gl) return;

		const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX_SOURCE);
		const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SOURCE);
		const program = gl.createProgram();
		if (!vertex || !fragment || !program) return;

		gl.attachShader(program, vertex);
		gl.attachShader(program, fragment);
		gl.linkProgram(program);
		if (!gl.getProgramParameter(program, gl.LINK_STATUS)) return;
		// biome-ignore lint/correctness/useHookAtTopLevel: WebGL call, not a React hook
		gl.useProgram(program);

		// One oversized triangle covers the whole viewport.
		const buffer = gl.createBuffer();
		gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
		gl.bufferData(
			gl.ARRAY_BUFFER,
			new Float32Array([-1, -1, 3, -1, -1, 3]),
			gl.STATIC_DRAW,
		);
		const position = gl.getAttribLocation(program, "aPosition");
		gl.enableVertexAttribArray(position);
		gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0);

		const resolution = gl.getUniformLocation(program, "uResolution");
		const dprUniform = gl.getUniformLocation(program, "uDpr");
		const time = gl.getUniformLocation(program, "uTime");

		let dpr = 1;
		const resize = () => {
			dpr = Math.min(window.devicePixelRatio || 1, 1.5);
			canvas.width = Math.max(1, Math.round(canvas.clientWidth * dpr));
			canvas.height = Math.max(1, Math.round(canvas.clientHeight * dpr));
			gl.viewport(0, 0, canvas.width, canvas.height);
		};
		resize();
		const observer = new ResizeObserver(resize);
		observer.observe(canvas);

		const start = performance.now();
		let frame = 0;
		const render = (now: number) => {
			gl.uniform2f(resolution, canvas.width, canvas.height);
			gl.uniform1f(dprUniform, dpr);
			gl.uniform1f(time, (now - start) / 1000);
			gl.drawArrays(gl.TRIANGLES, 0, 3);
			frame = requestAnimationFrame(render);
		};
		frame = requestAnimationFrame(render);

		return () => {
			cancelAnimationFrame(frame);
			observer.disconnect();
			gl.deleteBuffer(buffer);
			gl.deleteProgram(program);
			gl.deleteShader(vertex);
			gl.deleteShader(fragment);
		};
	}, []);

	return (
		<canvas
			ref={canvasRef}
			aria-hidden
			className={cn("pointer-events-none block size-full", className)}
		/>
	);
}

export { LaserRays };
