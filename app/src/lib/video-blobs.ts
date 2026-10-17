/**
 * The API never serves the source video back, so the preview comes from the
 * file the user uploaded. It is kept in IndexedDB so a reload or a trip via
 * the history list can still play it. Every call degrades to "not available".
 */
const DB_NAME = "review-videos";
const STORE = "videos";
const memory = new Map<string, Blob>();

function open(): Promise<IDBDatabase> {
	return new Promise((resolve, reject) => {
		const request = indexedDB.open(DB_NAME, 1);
		request.onupgradeneeded = () => request.result.createObjectStore(STORE);
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => reject(request.error);
	});
}

async function withStore<T>(
	mode: IDBTransactionMode,
	run: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
	const db = await open();
	try {
		return await new Promise<T>((resolve, reject) => {
			const request = run(db.transaction(STORE, mode).objectStore(STORE));
			request.onsuccess = () => resolve(request.result);
			request.onerror = () => reject(request.error);
		});
	} finally {
		db.close();
	}
}

export async function saveVideo(jobId: string, blob: Blob): Promise<void> {
	memory.set(jobId, blob);
	try {
		await withStore("readwrite", (store) => store.put(blob, jobId));
	} catch {
		// Private mode or quota: the in-memory copy still serves this session.
	}
}

export async function loadVideo(jobId: string): Promise<Blob | null> {
	const cached = memory.get(jobId);
	if (cached) return cached;
	try {
		const blob = await withStore<Blob | undefined>("readonly", (store) =>
			store.get(jobId),
		);
		if (blob) memory.set(jobId, blob);
		return blob ?? null;
	} catch {
		return null;
	}
}

export async function deleteVideo(jobId: string): Promise<void> {
	memory.delete(jobId);
	try {
		await withStore("readwrite", (store) => store.delete(jobId));
	} catch {
		// nothing to clean up
	}
}

export async function clearVideos(): Promise<void> {
	memory.clear();
	try {
		await withStore("readwrite", (store) => store.clear());
	} catch {
		// nothing to clean up
	}
}
