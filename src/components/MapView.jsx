import React, { useEffect, useRef } from "react";
import L from "leaflet";
import { createMarkerClusterGroup } from "../lib/mapClusterEngine.js";
import "leaflet.markercluster/dist/MarkerCluster.css";
import "leaflet.markercluster/dist/MarkerCluster.Default.css";

export function MapView({ listings = [], onSelectListing }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const clusterGroupRef = useRef(null);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (!mapInstanceRef.current) {
      // Initialize Leaflet Map centered on Turkey (Muğla / Ege center)
      const map = L.map(mapContainerRef.current).setView([37.5, 30.5], 7);

      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        maxZoom: 18
      }).addTo(map);

      mapInstanceRef.current = map;
    }

    const map = mapInstanceRef.current;

    if (!clusterGroupRef.current) {
      clusterGroupRef.current = createMarkerClusterGroup();
      map.addLayer(clusterGroupRef.current);

      map.on('zoomend', () => {
        const currentZoom = map.getZoom();
        if (currentZoom < 13) {
          if (!map.hasLayer(clusterGroupRef.current)) {
            map.addLayer(clusterGroupRef.current);
          }
        } else {
          // You could conditionally disable clustering if needed
        }
      });
    }

    const clusterGroup = clusterGroupRef.current;
    clusterGroup.clearLayers();

    // Add custom HTML price pill markers (Taste Skill Pill Markers)
    listings.forEach((l) => {
      if (!l.lat || !l.lng) return;

      const customIcon = L.divIcon({
        className: "custom-price-marker-wrapper",
        html: `<div class="custom-price-marker">₺${l.pricePerNight.toLocaleString("tr-TR")}</div>`,
        iconSize: [80, 30],
        iconAnchor: [40, 15]
      });

      const marker = L.marker([l.lat, l.lng], { icon: customIcon });

      // Popup card content
      const popupContent = document.createElement("div");
      popupContent.className = "p-1 cursor-pointer max-w-[200px]";
      popupContent.innerHTML = `
        <img src="${l.images?.[0] || ""}" class="w-full h-24 object-cover rounded-xl mb-2" />
        <p class="font-bold text-xs text-[#222222] truncate">${l.title}</p>
        <p class="text-[11px] text-[#717171]">${l.city}</p>
        <p class="font-extrabold text-xs text-[#222222] mt-1">₺${l.pricePerNight.toLocaleString("tr-TR")} <span class="font-normal text-[10px]">gece</span></p>
      `;
      popupContent.onclick = () => onSelectListing(l);

      marker.bindPopup(popupContent);
      clusterGroup.addLayer(marker);
    });

  }, [listings, onSelectListing]);

  return (
    <div className="w-full h-[600px] rounded-3xl overflow-hidden shadow-md border border-charcoal-border relative z-10 animate-in fade-in">
      <div ref={mapContainerRef} className="w-full h-full" />
    </div>
  );
}
