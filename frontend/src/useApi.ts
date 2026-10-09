// File: useApi.ts
// Description: Reuses cancellable loading and error handling for read-only requests.
// Author: Michael Burns <mdburnsjr@gmail.com>
// Created: 2026-10-08
// Last Modified: 2026-10-08 by Michael Burns
// Dependencies: react, api.ts

import { useEffect, useState } from "react";
import { api, errorMessage } from "./api";

export function useApi<T>(path: string, userId?: number, revision = 0) {
  const [retry, setRetry] = useState(0);
  const requestKey = JSON.stringify([path, userId, revision, retry]);
  const [result, setResult] = useState<{
    key: string;
    data?: T;
    error?: string;
  }>({ key: "" });

  useEffect(() => {
    const controller = new AbortController();
    api<T>(path, userId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResult({ key: requestKey, data });
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted)
          setResult({ key: requestKey, error: errorMessage(error) });
      });
    return () => controller.abort();
  }, [path, userId, requestKey]);

  // Never display data from a previous filter or identity while the new effect
  // starts. A request is loading until we have a result with its exact key.
  const loading = result.key !== requestKey;
  return {
    data: loading ? undefined : result.data,
    error: loading ? undefined : result.error,
    loading,
    reload: () => setRetry((value) => value + 1),
  };
}
