import { useEffect, useState } from "react";
import { loadVideo } from "@/lib/video-blobs";

export type VideoSource =
	| { state: "loading"; url: null }
	| { state: "ready"; url: string }
	| { state: "missing"; url: null };

/**
 * The API does not serve the source video, so playback uses the local copy
 * saved at upload time. `missing` means this browser no longer has it.
 */
export function useVideoSource(jobId: string): VideoSource {
	const [source, setSource] = useState<VideoSource>({
		state: "loading",
		url: null,
	});

	useEffect(() => {
		let active = true;
		let objectUrl: string | null = null;
		setSource({ state: "loading", url: null });
		loadVideo(jobId).then((blob) => {
			if (!active) return;
			if (!blob) {
				setSource({ state: "missing", url: null });
				return;
			}
			objectUrl = URL.createObjectURL(blob);
			setSource({ state: "ready", url: objectUrl });
		});
		return () => {
			active = false;
			if (objectUrl) URL.revokeObjectURL(objectUrl);
		};
	}, [jobId]);

	return source;
}
