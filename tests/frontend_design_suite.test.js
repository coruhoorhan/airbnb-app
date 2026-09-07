/**
 * @vitest-environment jsdom
 */
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MapView } from "../src/components/MapView.jsx";
import { ListingDetail } from "../src/components/ListingDetail.jsx";
import { Navbar } from "../src/components/Navbar.jsx";
import { RecommendationCarousel } from "../src/components/RecommendationCarousel.jsx";
import { getClusters } from "../src/lib/mapClusterEngine.js";

vi.mock("leaflet", () => {
  const mapMock = {
    setView: vi.fn().mockReturnThis(),
    eachLayer: vi.fn(),
    removeLayer: vi.fn(),
    getZoom: vi.fn().mockReturnValue(10),
    getBounds: vi.fn().mockReturnValue({
      getNorth: () => 40,
      getSouth: () => 35,
      getEast: () => 35,
      getWest: () => 30,
    }),
    on: vi.fn(),
    off: vi.fn(),
    fitBounds: vi.fn(),
  };
  return {
    default: {
      map: vi.fn(() => mapMock),
      tileLayer: vi.fn(() => ({ addTo: vi.fn() })),
      marker: vi.fn(() => ({ addTo: vi.fn().mockReturnThis(), bindPopup: vi.fn(), on: vi.fn() })),
      divIcon: vi.fn(),
    }
  };
});

describe("Frontend Design Suite", () => {
  it("Map Clustering logic works correctly", () => {
    const listings = [
      { id: "1", lat: 37.1, lng: 30.1 },
      { id: "2", lat: 37.12, lng: 30.12 }, // Close to 1, should cluster depending on grid
      { id: "3", lat: 39.1, lng: 32.1 }  // Far
    ];

    // Zoom out (e.g. zoom 10)
    const bounds = { north: 40, south: 35, east: 35, west: 30 };
    const clusters = getClusters(listings, 10, bounds);

    // With grid size 0.5, 37.1 and 37.12 might be in the same cell.
    // 37.1 / 0.5 = 74.2 => 74
    // 37.12 / 0.5 = 74.24 => 74
    // They are in the same cell, so count should be 2 for that cluster.
    expect(clusters.length).toBe(2);
    expect(clusters.some(c => c.type === "cluster" && c.count === 2)).toBe(true);

    // Zoom in (e.g. zoom 14)
    const markers = getClusters(listings, 14, bounds);
    expect(markers.length).toBe(3);
    expect(markers.every(m => m.type === "marker")).toBe(true);
  });

  it("ListingDetail renders 5-photo grid for 5+ images", () => {
    const listingWith5Images = {
      id: "1",
      title: "Test",
      images: ["img1", "img2", "img3", "img4", "img5"],
      amenities: [],
    };

    render(<ListingDetail listing={listingWith5Images} currentUser={{}} onBack={() => {}} onBook={() => {}} onOpenChat={() => {}} bookings={[]} reviews={[]} isFavorite={false} onToggleFavorite={() => {}} />);

    // Should have 1 main image and 4 sub images in the grid
    const mainImages = screen.getAllByAltText("Ana Görsel");
    expect(mainImages.length).toBeGreaterThan(0);
    expect(screen.getByAltText("Detay 1")).toBeTruthy();
    expect(screen.getByAltText("Detay 4")).toBeTruthy();
  });

  it("Navbar toggles dark mode", () => {
    const onToggle = vi.fn();
    render(<Navbar currentUser={{}} onToggleDarkMode={onToggle} isDarkMode={false} onViewChange={() => {}} notifications={[]} />);

    const toggleBtn = screen.getByTitle("Karanlık Moda Geç");
    fireEvent.click(toggleBtn);
    expect(onToggle).toHaveBeenCalled();
  });

  it("RecommendationCarousel fetches and renders", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      json: vi.fn().mockResolvedValue({
        data: {
          recommendedListings: [
            { id: "1", title: "Rec 1", pricePerNight: 100 },
            { id: "2", title: "Rec 2", pricePerNight: 200 }
          ]
        }
      })
    });

    render(<RecommendationCarousel userId="user1" />);

    await waitFor(() => {
      expect(screen.getByText("Sizin İçin Önerilenler")).toBeTruthy();
      // Since ListingCard handles its own rendering and we didn't mock it, we can just check if titles appear
      expect(screen.getByText("Rec 1")).toBeTruthy();
      expect(screen.getByText("Rec 2")).toBeTruthy();
    });
  });
});
