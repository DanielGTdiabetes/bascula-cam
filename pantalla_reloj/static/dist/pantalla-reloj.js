(function (global) {
  "use strict";

  function isObject(value) {
    return typeof value === "object" && value !== null;
  }

  function toNumber(value, fallback) {
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string") {
      var parsed = Number.parseFloat(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
    return fallback;
  }

  function toString(value) {
    if (typeof value === "string") {
      var trimmed = value.trim();
      return trimmed.length > 0 ? trimmed : null;
    }
    return value == null ? null : String(value);
  }

  function buildRuntimeMapOptions(configPayload) {
    var mappingConfig = isObject(configPayload) && isObject(configPayload.ui_map)
      ? configPayload.ui_map
      : {};
    var maptilerConfig = isObject(mappingConfig.maptiler) ? mappingConfig.maptiler : {};
    var satelliteConfig = isObject(mappingConfig.satellite) ? mappingConfig.satellite : {};
    var labelsOverlayConfig = isObject(satelliteConfig.labels_overlay)
      ? satelliteConfig.labels_overlay
      : {};

    var baseStyleUrl = toString(maptilerConfig.styleUrl) || toString(maptilerConfig.style_url);
    var satelliteStyleUrl = toString(satelliteConfig.style_url);
    var labelsOverlayStyleUrl = toString(labelsOverlayConfig.style_url);
    var labelsOverlayFilter = labelsOverlayConfig.layer_filter != null
      ? labelsOverlayConfig.layer_filter
      : null;
    var maptilerKey = maptilerConfig.api_key != null
      ? toString(maptilerConfig.api_key)
      : null;
    var maptilerKeyPresent = maptilerKey != null && String(maptilerKey).trim().length > 0;

    var runtimeOptions = {
      base_style_url: baseStyleUrl || null,
      satellite_enabled: Boolean(satelliteConfig.enabled),
      satellite_style_url: satelliteStyleUrl || null,
      satellite_opacity: toNumber(satelliteConfig.opacity, 1.0),
      labels_overlay_enabled: Boolean(labelsOverlayConfig.enabled),
      labels_overlay_style_url: labelsOverlayStyleUrl || null,
      labels_overlay_filter: labelsOverlayFilter,
      maptiler_key_present: Boolean(maptilerKeyPresent),
      maptiler_api_key: maptilerKey,
    };

    runtimeOptions.hybrid_enabled = runtimeOptions.satellite_enabled && runtimeOptions.maptiler_key_present;

    console.info("[HybridFix] Mapping config received", mappingConfig);
    console.info("[HybridFix] Runtime map options", runtimeOptions);
    return runtimeOptions;
  }

  function buildMapInitPayload(runtimeOptions, containerId) {
    var payload = {
      container: containerId || "map",
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

  function resolveContainer(containerRef) {
    if (!containerRef) {
      return null;
    }
    if (typeof containerRef === "string") {
      if (!global.document) {
        return null;
      }
      return global.document.getElementById(containerRef);
    }
    return containerRef;
  }

  function initialiseHybridMap(configPayload, maplibreInstance) {
    var runtimeOptions = buildRuntimeMapOptions(configPayload);
    var payload = buildMapInitPayload(runtimeOptions);
    var maplibre = maplibreInstance || global.maplibregl;
    if (!maplibre || typeof maplibre.Map !== "function") {
      console.warn("[HybridFix] maplibregl.Map is not available; skipping init");
      return null;
    }
    if (!payload.style) {
      console.warn("[HybridFix] base_style_url missing; map cannot be initialised");
      return null;
    }
    var container = resolveContainer(payload.container);
    if (!container) {
      console.warn("[HybridFix] Map container not found", payload.container);
      return null;
    }
    console.info("[HybridFix] Map init", {
      base_style_url: payload.base_style_url,
      satellite_enabled: payload.satellite_enabled,
      satellite_style_url: payload.satellite_style_url,
      satellite_opacity: payload.satellite_opacity,
      labels_overlay_enabled: payload.labels_overlay_enabled,
      labels_overlay_style_url: payload.labels_overlay_style_url,
      labels_overlay_filter: payload.labels_overlay_filter,
      maptiler_key_present: payload.maptiler_key_present,
      hybrid_enabled: payload.hybrid_enabled,
    });
    var map = new maplibre.Map({
      container: container,
      style: payload.style,
      attributionControl: true,
    });
    return map;
  }

  function bootstrapHybridMap(fetchImpl, maplibreInstance) {
    var fetchFn = fetchImpl || global.fetch;
    if (typeof fetchFn !== "function") {
      console.warn("[HybridFix] fetch implementation missing; cannot bootstrap map");
      return Promise.resolve(null);
    }
    return fetchFn("/api/config").then(function (response) {
      if (!response || typeof response.json !== "function") {
        throw new Error("Invalid response from /api/config");
      }
      if (!response.ok) {
        throw new Error("Failed to load /api/config: " + response.status);
      }
      return response.json();
    }).then(function (configPayload) {
      return initialiseHybridMap(configPayload, maplibreInstance);
    }).catch(function (error) {
      console.error("[HybridFix] Failed to initialise hybrid map", error);
      return null;
    });
  }

  global.HybridFix = global.HybridFix || {};
  global.HybridFix.buildRuntimeMapOptions = buildRuntimeMapOptions;
  global.HybridFix.buildMapInitPayload = buildMapInitPayload;
  global.HybridFix.initialiseHybridMap = initialiseHybridMap;
  global.HybridFix.bootstrapHybridMap = bootstrapHybridMap;

  if (global.document && typeof global.document.addEventListener === "function") {
    global.document.addEventListener("DOMContentLoaded", function () {
      var container = global.document.getElementById("map");
      if (!container) {
        return;
      }
      bootstrapHybridMap();
    });
  }
})(typeof window !== "undefined" ? window : globalThis);
