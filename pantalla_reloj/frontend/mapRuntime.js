/**
 * Hybrid map runtime adapter for Pantalla Reloj.
 *
 * The legacy build ignored `ui_map.maptiler` and `ui_map.satellite` entirely.
 * This adapter strictly maps the `/api/config` payload to the runtime
 * structure consumed by the MapLibre initialisation code.
 */

function isObject(value) {
  return typeof value === "object" && value !== null;
}

function toNumber(value, fallback) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string") {
    const parsed = Number.parseFloat(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function toString(value) {
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed.length > 0 ? trimmed : null;
  }
  return null;
}

export function buildRuntimeMapOptions(configPayload) {
  const mappingConfig = isObject(configPayload) && isObject(configPayload.ui_map)
    ? configPayload.ui_map
    : {};
  const maptilerConfig = isObject(mappingConfig.maptiler) ? mappingConfig.maptiler : {};
  const satelliteConfig = isObject(mappingConfig.satellite) ? mappingConfig.satellite : {};
  const labelsOverlayConfig = isObject(satelliteConfig.labels_overlay)
    ? satelliteConfig.labels_overlay
    : {};

  const baseStyleUrl = toString(maptilerConfig.styleUrl) || toString(maptilerConfig.style_url);
  const satelliteStyleUrl = toString(satelliteConfig.style_url);
  const labelsOverlayStyleUrl = toString(labelsOverlayConfig.style_url);
  const labelsOverlayFilter = labelsOverlayConfig.layer_filter ?? null;
  const maptilerKeyPresent = maptilerConfig.api_key != null
    && (typeof maptilerConfig.api_key !== "string" || maptilerConfig.api_key.trim().length > 0);

  const runtimeOptions = {
    base_style_url: baseStyleUrl || null,
    satellite_enabled: Boolean(satelliteConfig.enabled),
    satellite_style_url: satelliteStyleUrl || null,
    satellite_opacity: toNumber(satelliteConfig.opacity, 1.0),
    labels_overlay_enabled: Boolean(labelsOverlayConfig.enabled),
    labels_overlay_style_url: labelsOverlayStyleUrl || null,
    labels_overlay_filter: labelsOverlayFilter,
    maptiler_key_present: Boolean(maptilerKeyPresent),
  };

  runtimeOptions.hybrid_enabled = runtimeOptions.satellite_enabled && runtimeOptions.maptiler_key_present;
  runtimeOptions.maptiler_api_key = toString(maptilerConfig.api_key);

  console.info("[HybridFix] Mapping config received", mappingConfig);
  console.info("[HybridFix] Runtime map options", runtimeOptions);

  return runtimeOptions;
}

export function buildMapInitPayload(runtimeOptions, containerId = "map") {
  const payload = {
    container: containerId,
    style: runtimeOptions.base_style_url,
    base_style_url: runtimeOptions.base_style_url,
    satellite_enabled: runtimeOptions.satellite_enabled,
    satellite_style_url: runtimeOptions.satellite_style_url,
    satellite_opacity: runtimeOptions.satellite_opacity,
    labels_overlay_enabled: runtimeOptions.labels_overlay_enabled,
    labels_overlay_style_url: runtimeOptions.labels_overlay_style_url,
    labels_overlay_filter: runtimeOptions.labels_overlay_filter,
    maptiler_key_present: runtimeOptions.maptiler_key_present,
    hybrid_enabled: runtimeOptions.hybrid_enabled,
  };
  console.info("[HybridFix] Map init payload", payload);
  return payload;
}

export function initialiseHybridMap(configPayload, maplibre = globalThis.maplibregl) {
  const runtimeOptions = buildRuntimeMapOptions(configPayload);
  const payload = buildMapInitPayload(runtimeOptions);
  if (!maplibre || typeof maplibre.Map !== "function") {
    console.warn("[HybridFix] maplibregl.Map is not available; skipping init");
    return null;
  }
  if (!payload.style) {
    console.warn("[HybridFix] base_style_url missing; map cannot be initialised");
    return null;
  }
  const container = typeof payload.container === "string"
    ? globalThis.document?.getElementById(payload.container)
    : payload.container;
  if (!container) {
    console.warn("[HybridFix] Map container not found", payload.container);
    return null;
  }
  const map = new maplibre.Map({
    container,
    style: payload.style,
    attributionControl: true,
  });
  return map;
}

if (typeof window !== "undefined") {
  window.HybridFix = window.HybridFix || {};
  window.HybridFix.buildRuntimeMapOptions = buildRuntimeMapOptions;
  window.HybridFix.initialiseHybridMap = initialiseHybridMap;
}
