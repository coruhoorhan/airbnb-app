import React, { useEffect, useRef } from "react";
import L from "leaflet";
import { applyMapClustering } from "../lib/mapClusterEngine.js";

export function MapView({ listings = [], onSelectListing }) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);

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

    // Apply clustering and get custom markers
    applyMapClustering(map, listings, onSelectListing);

  }, [listings, onSelectListing]);

  return (
    <div className="w-full h-[600px] rounded-3xl overflow-hidden shadow-md border border-charcoal-border relative z-10 animate-in fade-in">
      <div ref={mapContainerRef} className="w-full h-full" />
    </div>
  );
}
