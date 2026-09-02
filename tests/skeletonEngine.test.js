import { describe, it, expect } from "vitest";
import React from "react";
import { 
  ListingCardSkeleton, 
  ListingGridSkeleton, 
  ListingDetailSkeleton 
} from "../src/components/ListingSkeleton.jsx";

describe("Skeleton Loading Engine (Boneyard Architecture)", () => {
  it("creates ListingCardSkeleton element correctly", () => {
    const element = ListingCardSkeleton();
    expect(element).toBeDefined();
    expect(element.props.className).toContain("animate-pulse");
  });

  it("creates ListingGridSkeleton with requested card count", () => {
    const grid = ListingGridSkeleton({ count: 6 });
    expect(grid).toBeDefined();
    expect(grid.props.className).toContain("grid");
    expect(grid.props.children.length).toBe(6);
  });

  it("creates ListingDetailSkeleton with gallery and widget placeholders", () => {
    const detail = ListingDetailSkeleton();
    expect(detail).toBeDefined();
    expect(detail.props.className).toContain("animate-pulse");
    expect(detail.props.children.length).toBeGreaterThan(0);
  });
});
