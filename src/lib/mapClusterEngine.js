import L from "leaflet";
import "leaflet.markercluster";

export function createMarkerClusterGroup() {
  return L.markerClusterGroup({
    iconCreateFunction: function(cluster) {
      const count = cluster.getChildCount();
      return L.divIcon({
        html: `<div class="bg-charcoal text-white font-bold text-sm w-10 h-10 rounded-full flex items-center justify-center border-2 border-white shadow-lg">${count}</div>`,
        className: 'custom-cluster-icon',
        iconSize: L.point(40, 40)
      });
    },
    maxClusterRadius: 50,
    spiderfyOnMaxZoom: true,
    showCoverageOnHover: false,
    zoomToBoundsOnClick: true
  });
}
