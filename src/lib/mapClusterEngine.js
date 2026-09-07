import L from "leaflet";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

export function createClusterGroup() {
  return L.markerClusterGroup({
    maxClusterRadius: 50,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true,
    spiderfyOnMaxZoom: true,
    iconCreateFunction: function (cluster) {
      const count = cluster.getChildCount();
      let sizeClass = "w-8 h-8 text-sm";
      if (count > 10) sizeClass = "w-10 h-10 text-base";
      if (count > 50) sizeClass = "w-12 h-12 text-lg";

      const html = `<div class="flex items-center justify-center bg-charcoal text-white font-bold rounded-full shadow-md border-2 border-white ${sizeClass}">${count}</div>`;

      return L.divIcon({
        html: html,
        className: "custom-cluster-icon",
        iconSize: L.point(40, 40)
      });
    }
  });
}
