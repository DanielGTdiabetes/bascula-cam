import { buildRuntimeMapOptions, buildMapInitPayload, initialiseHybridMap } from "./mapRuntime.js";

async function loadConfig(fetchImpl = fetch) {
  const response = await fetchImpl("/api/config");
  if (!response.ok) {
    throw new Error(`Failed to load config: ${response.status}`);
  }
  return response.json();
}

export async function bootstrapHybridMap(fetchImpl = fetch, maplibre = globalThis.maplibregl) {
  const configPayload = await loadConfig(fetchImpl);
  const runtimeOptions = buildRuntimeMapOptions(configPayload);
  const payload = buildMapInitPayload(runtimeOptions);
  if (!maplibre || typeof maplibre.Map !== "function") {
    console.warn("[HybridFix] maplibregl not available; skipping bootstrap");
    return null;
  }
  return initialiseHybridMap(configPayload, maplibre);
}

if (typeof window !== "undefined") {
  window.addEventListener("DOMContentLoaded", () => {
    const container = document.getElementById("map");
    if (!container) {
      return;
    }
    bootstrapHybridMap().catch((error) => {
      console.error("[HybridFix] Failed to bootstrap map", error);
    });
  });
}
