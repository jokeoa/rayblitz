import { OverlaySwitch } from "./overlay-switch";
import { Film, VideoOff, Maximize } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Spinner } from "@/components/ui/spinner";
import type { VideoSource } from "@/hooks/use-video-source";
import type { ReactNode } from "react";
import {
	type PlayerController,
	playheadTime,
	usePlayerStore,
} from "@/stores/player-store";

const clamp = (value: number, min: number, max: number) =>
	Math.min(Math.max(value, min), max);

/**
 * A `<video>` with no native UI. It publishes a controller to the player
 * store; every control on the page drives playback through that controller.
 * Without a playable file it still registers one, so events can move the
 * playhead even when the preview is unavailable.
 */
export function VideoPlayer({
	source,
	fallbackDuration,
	children,
}: {
	source: VideoSource;
	fallbackDuration: number;
	children?: ReactNode;
}) {
	const videoRef = useRef<HTMLVideoElement>(null);
	const containerRef = useRef<HTMLDivElement>(null);
	const [fullscreen, setFullscreen] = useState(false);
	useEffect(() => {
		const changed = () =>
			setFullscreen(document.fullscreenElement === containerRef.current);
		document.addEventListener("fullscreenchange", changed);
		return () => document.removeEventListener("fullscreenchange", changed);
	}, []);
	const status = usePlayerStore((state) => state.status);
	const playbackFailed = status === "unavailable";

	// Keep the timeline usable when the browser cannot play the file.
	useEffect(() => {
		if (source.state === "missing" || playbackFailed) {
			const store = usePlayerStore.getState();
			store.setStatus("unavailable");
			store.setDuration(fallbackDuration);
		}
	}, [source.state, playbackFailed, fallbackDuration]);

	useEffect(() => {
		const store = usePlayerStore.getState();
		// The <video> element exists only while there is a source, so re-run when it changes.
		const video = source.url === null ? null : videoRef.current;
		let frame = 0;

		const loop = () => {
			if (video) playheadTime.set(video.currentTime);
			frame = requestAnimationFrame(loop);
		};
		const stopLoop = () => {
			cancelAnimationFrame(frame);
			frame = 0;
		};

		const limit = () => {
			const total = video?.duration;
			return Number.isFinite(total) && total
				? total
				: usePlayerStore.getState().duration;
		};
		const controller: PlayerController = {
			toggle: () => {
				if (!video) return;
				if (video.paused) void video.play().catch(() => {});
				else video.pause();
			},
			play: () => void video?.play().catch(() => {}),
			pause: () => video?.pause(),
			seek: (seconds) => {
				const next = clamp(seconds, 0, limit() || seconds);
				if (video) video.currentTime = next;
				playheadTime.set(next);
				usePlayerStore.getState().setCurrentTime(next);
			},
			skip: (delta) =>
				controller.seek(
					(video ? video.currentTime : playheadTime.get()) + delta,
				),
			setRate: (rate) => {
				if (video) video.playbackRate = rate;
				usePlayerStore.getState().setRate(rate);
			},
		};
		store.register(controller);

		if (!video) return () => store.register(null);

		const onMetadata = () => {
			usePlayerStore.getState().setDuration(video.duration);
			usePlayerStore.getState().setStatus("ready");
		};
		const onPlay = () => {
			usePlayerStore.getState().setPlaying(true);
			if (!frame) frame = requestAnimationFrame(loop);
		};
		const onPause = () => {
			usePlayerStore.getState().setPlaying(false);
			stopLoop();
			playheadTime.set(video.currentTime);
			usePlayerStore.getState().setCurrentTime(video.currentTime);
		};
		const onTime = () =>
			usePlayerStore.getState().setCurrentTime(video.currentTime);
		const onSeek = () => playheadTime.set(video.currentTime);
		const onError = () => usePlayerStore.getState().setStatus("unavailable");

		video.addEventListener("loadedmetadata", onMetadata);
		video.addEventListener("play", onPlay);
		video.addEventListener("pause", onPause);
		video.addEventListener("ended", onPause);
		video.addEventListener("timeupdate", onTime);
		video.addEventListener("seeking", onSeek);
		video.addEventListener("seeked", onSeek);
		video.addEventListener("error", onError);
		if (video.readyState >= 1) onMetadata();

		return () => {
			stopLoop();
			video.removeEventListener("loadedmetadata", onMetadata);
			video.removeEventListener("play", onPlay);
			video.removeEventListener("pause", onPause);
			video.removeEventListener("ended", onPause);
			video.removeEventListener("timeupdate", onTime);
			video.removeEventListener("seeking", onSeek);
			video.removeEventListener("seeked", onSeek);
			video.removeEventListener("error", onError);
			store.register(null);
		};
	}, [source.url]);

	return (
		<div
			ref={containerRef}
			className="relative aspect-video w-full shrink-0 overflow-hidden rounded-2xl bg-neutral-950 shadow-card"
		>
			{source.url && !playbackFailed ? (
				// biome-ignore lint/a11y/useMediaCaption: analysis footage has no captions track.
				<video
					ref={videoRef}
					src={source.url}
					playsInline
					controls={fullscreen}
					preload="metadata"
					className="size-full object-contain"
					onClick={() => usePlayerStore.getState().controller?.toggle()}
				/>
			) : null}
			{children}
			{fullscreen && <OverlaySwitch className="absolute left-3 top-3 z-10" />}
			{source.url && !playbackFailed && (
				<button
					type="button"
					aria-label={
						fullscreen ? "Выйти из полноэкранного режима" : "На весь экран"
					}
					title="На весь экран"
					className="absolute right-3 top-3 rounded-lg bg-black/60 p-2 text-white hover:bg-black/80"
					onClick={() => {
						const action = fullscreen
							? document.exitFullscreen()
							: containerRef.current?.requestFullscreen();
						void action?.catch(() => {});
					}}
				>
					<Maximize className="size-4" aria-hidden />
				</button>
			)}

			{source.state === "loading" ||
			(source.url && status === "loading" && !playbackFailed) ? (
				<div className="absolute inset-0 grid place-items-center text-neutral-400">
					<Spinner className="size-5" />
				</div>
			) : null}

			{source.state === "missing" || playbackFailed ? (
				<div className="absolute inset-0 grid place-items-center p-6 text-center">
					<div className="flex max-w-sm flex-col items-center gap-2 text-neutral-300">
						{source.state === "missing" ? (
							<Film className="size-6" aria-hidden />
						) : (
							<VideoOff className="size-6" aria-hidden />
						)}
						<p className="text-sm font-medium text-white">
							{source.state === "missing"
								? "Видео ещё подготавливается"
								: "Предпросмотр недоступен"}
						</p>
						<p className="text-xs text-neutral-400">
							{source.state === "missing"
								? "Сервер готовит видео для воспроизведения."
								: "Не удалось загрузить видео с сервера. Обновите страницу после завершения обработки."}
						</p>
					</div>
				</div>
			) : null}
		</div>
	);
}
