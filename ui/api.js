const requestTimeoutMs = 35_000;
const readAttempts = 3;
const retryableStatuses = new Set([502, 503, 504]);

async function api(base, path, { onRetry, ...options } = {}) {
  const isRead = (options.method || "GET").toUpperCase() === "GET";
  const attempts = isRead ? readAttempts : 1;

  for (let attempt = 1; attempt <= attempts; attempt++) {
    let response;
    try {
      response = await fetch(base + path, {
        ...options,
        signal: AbortSignal.timeout(requestTimeoutMs),
      });
    } catch (error) {
      if (error.name !== "TimeoutError" && !(error instanceof TypeError)) throw error;
      if (!isRead) {
        throw new Error("Could not confirm the save. Reload and check before submitting again.");
      }
    }

    if (response && (!isRead || !retryableStatuses.has(response.status))) {
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body?.error || (isRead
          ? "Service unavailable. Try again shortly."
          : "Could not confirm the save. Reload and check before submitting again."));
      }
      if (response.status === 204) return null;
      try {
        return await response.json();
      } catch (error) {
        if (!isRead || (error.name !== "TimeoutError" && !(error instanceof TypeError))) throw error;
      }
    }

    if (attempt < attempts) {
      if (response?.body && !response.bodyUsed) response.body.cancel().catch(() => {});
      onRetry?.();
      await new Promise((resolve) => setTimeout(resolve, 1000 * attempt));
    }
  }

  throw new Error("The service is still starting or unavailable. Try again shortly.");
}
