export function getClusters(listings, zoom, bounds) {
  if (zoom >= 13) {
    return listings.map(l => ({
      type: "marker",
      listing: l,
      lat: l.lat,
      lng: l.lng
    }));
  }

  // Basic grid-based clustering
  const clusters = {};
  const gridSize = 0.5; // Degree grid size, adjust based on clustering needs. Larger = fewer clusters

  listings.forEach(l => {
    if (l.lat === undefined || l.lng === undefined) return;

    // Only process listings within bounds if provided
    if (bounds) {
      if (l.lat < bounds.south || l.lat > bounds.north || l.lng < bounds.west || l.lng > bounds.east) {
        return;
      }
    }

    const gridX = Math.floor(l.lng / gridSize);
    const gridY = Math.floor(l.lat / gridSize);
    const key = `${gridX}_${gridY}`;

    if (!clusters[key]) {
      clusters[key] = {
        type: "cluster",
        count: 0,
        latSum: 0,
        lngSum: 0,
        bounds: {
          north: -90,
          south: 90,
          east: -180,
          west: 180
        }
      };
    }

    clusters[key].count++;
    clusters[key].latSum += l.lat;
    clusters[key].lngSum += l.lng;

    // Update cluster bounds
    if (l.lat > clusters[key].bounds.north) clusters[key].bounds.north = l.lat;
    if (l.lat < clusters[key].bounds.south) clusters[key].bounds.south = l.lat;
    if (l.lng > clusters[key].bounds.east) clusters[key].bounds.east = l.lng;
    if (l.lng < clusters[key].bounds.west) clusters[key].bounds.west = l.lng;
  });

  const result = [];
  for (const key in clusters) {
    const c = clusters[key];
    if (c.count === 1) {
      // Find the original listing
      const gridX = parseInt(key.split('_')[0], 10);
      const gridY = parseInt(key.split('_')[1], 10);
      const l = listings.find(l =>
        Math.floor(l.lng / gridSize) === gridX &&
        Math.floor(l.lat / gridSize) === gridY
      );
      if (l) {
        result.push({
          type: "marker",
          listing: l,
          lat: l.lat,
          lng: l.lng
        });
      }
    } else {
      result.push({
        type: "cluster",
        count: c.count,
        lat: c.latSum / c.count,
        lng: c.lngSum / c.count,
        bounds: c.bounds
      });
    }
  }

  return result;
}

export function applyMapClustering(map, listings, onSelectListing) {
  // Clear previous markers
  map.eachLayer((layer) => {
    if (layer instanceof window.L.Marker) {
      map.removeLayer(layer);
    }
  });

  const zoom = map.getZoom();

  // Calculate bounds if map is initialized
  let boundsObj = null;
  if (map.getBounds) {
    const bounds = map.getBounds();
    boundsObj = {
      north: bounds.getNorth(),
      south: bounds.getSouth(),
      east: bounds.getEast(),
      west: bounds.getWest()
    };
  }

  const items = getClusters(listings, zoom, boundsObj);

  items.forEach((item) => {
    if (item.type === "marker") {
      const l = item.listing;
      const customIcon = window.L.divIcon({
        className: "custom-price-marker-wrapper",
        html: `<div class="custom-price-marker">₺${l.pricePerNight.toLocaleString("tr-TR")}</div>`,
        iconSize: [80, 30],
        iconAnchor: [40, 15]
      });

      const marker = window.L.marker([item.lat, item.lng], { icon: customIcon }).addTo(map);

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
    } else {
      const clusterIcon = window.L.divIcon({
        className: "custom-cluster-marker-wrapper",
        html: `<div class="custom-cluster-marker bg-charcoal text-white rounded-full flex items-center justify-center font-bold text-sm shadow-md" style="width: 40px; height: 40px;">${item.count}</div>`,
        iconSize: [40, 40],
        iconAnchor: [20, 20]
      });

      const marker = window.L.marker([item.lat, item.lng], { icon: clusterIcon }).addTo(map);
      marker.on('click', () => {
        map.setView([item.lat, item.lng], zoom + 2);
      });
    }
  });

  // Re-cluster on zoom or pan
  const updateClusters = () => {
    map.off('moveend', updateClusters); // prevent infinite loops if we reset map here
    applyMapClustering(map, listings, onSelectListing);
    map.on('moveend', updateClusters);
  };

  // Attach event listener only once
  if (!map.hasLayerEvent) {
    map.on('moveend', updateClusters);
    map.hasLayerEvent = true;
  }
}
