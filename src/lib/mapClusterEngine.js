import * as db from "./db.js";

// Dummy engine as the frontend will handle Leaflet map clustering
export function getMapClusters(bbox, zoom) {
  return [];
}
