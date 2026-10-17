import { Film, VideoOff } from "lucide-react";
import { useEffect, useRef } from "react";
import { Spinner } from "@/components/ui/spinner";
import type { VideoSource } from "@/hooks/use-video-source";
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
}: {
	source: VideoSource;
	fallbackDuration: number;
}) {
	const videoRef = useRef<HTMLVideoElement>(null);
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
		<div className="relative aspect-video w-full overflow-hidden rounded-2xl bg-neutral-950 shadow-card">
			{source.url && !playbackFailed ? (
				// biome-ignore lint/a11y/useMediaCaption: analysis footage has no captions track.
				<video
					ref={videoRef}
					src={source.url}
					playsInline
					preload="metadata"
					className="size-full object-contain"
					onClick={() => usePlayerStore.getState().controller?.toggle()}
				/>
			) : null}

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
								? "Видео нет на этом устройстве"
								: "Предпросмотр недоступен"}
						</p>
						<p className="text-xs text-neutral-400">
							{source.state === "missing"
								? "Исходный файл хранится только в браузере, где его загрузили. События и таймкоды при этом доступны."
								: "Браузер не воспроизводит этот MOV. Анализ и события при этом доступны."}
						</p>
					</div>
				</div>
			) : null}
		</div>
	);
}
