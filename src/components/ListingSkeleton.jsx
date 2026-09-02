import React from "react";

/**
 * Pixel-Perfect Skeleton Card for Listing Grid
 * Matches exact aspect-ratio, typography dimensions, and layout of ListingCard
 */
export function ListingCardSkeleton() {
  return (
    <div className="flex flex-col gap-2.5 animate-pulse select-none">
      {/* Image Skeleton Box */}
      <div className="relative aspect-square w-full rounded-2xl bg-gradient-to-r from-charcoal-bg via-gray-200/80 to-charcoal-bg bg-[length:200%_100%] overflow-hidden">
        {/* Heart Placeholder */}
        <div className="absolute top-3 right-3 w-8 h-8 rounded-full bg-white/60" />
      </div>

      {/* Info Lines Skeleton */}
      <div className="flex flex-col gap-2 pt-1">
        <div className="flex items-center justify-between">
          <div className="h-4 w-3/5 rounded-md bg-charcoal-bg" />
          <div className="h-4 w-10 rounded-md bg-charcoal-bg" />
        </div>

        <div className="h-3.5 w-4/5 rounded-md bg-charcoal-bg/70" />

        <div className="flex items-center gap-2 mt-1">
          <div className="h-4 w-20 rounded-md bg-charcoal-bg" />
          <div className="h-3 w-8 rounded-md bg-charcoal-bg/60" />
        </div>
      </div>
    </div>
  );
}

/**
 * Full 8-Card Responsive Skeleton Grid
 */
export function ListingGridSkeleton({ count = 8 }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-10">
      {Array.from({ length: count }, (_, i) => (
        <ListingCardSkeleton key={i} />
      ))}
    </div>
  );
}

/**
 * Pixel-Perfect Listing Detail Page Skeleton
 */
export function ListingDetailSkeleton() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6 animate-pulse select-none">
      {/* Title & Header */}
      <div className="flex flex-col gap-2">
        <div className="h-7 w-2/5 rounded-xl bg-charcoal-bg" />
        <div className="flex items-center gap-3">
          <div className="h-4 w-24 rounded-md bg-charcoal-bg" />
          <div className="h-4 w-32 rounded-md bg-charcoal-bg" />
        </div>
      </div>

      {/* 5-Photo Gallery Grid Skeleton */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-2 rounded-3xl overflow-hidden h-[380px] sm:h-[440px]">
        <div className="md:col-span-2 md:row-span-2 bg-gradient-to-r from-charcoal-bg via-gray-200/80 to-charcoal-bg" />
        <div className="hidden md:block bg-charcoal-bg" />
        <div className="hidden md:block bg-charcoal-bg" />
        <div className="hidden md:block bg-charcoal-bg" />
        <div className="hidden md:block bg-charcoal-bg" />
      </div>

      {/* Content & Booking Widget Split */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 mt-4">
        {/* Left Column */}
        <div className="lg:col-span-2 flex flex-col gap-8">
          <div className="flex items-center justify-between pb-6 border-b border-charcoal-border/50">
            <div className="flex flex-col gap-2">
              <div className="h-5 w-48 rounded-lg bg-charcoal-bg" />
              <div className="h-4 w-64 rounded-md bg-charcoal-bg/70" />
            </div>
            <div className="w-14 h-14 rounded-full bg-charcoal-bg" />
          </div>

          <div className="flex flex-col gap-3">
            <div className="h-4 w-full rounded-md bg-charcoal-bg/80" />
            <div className="h-4 w-5/6 rounded-md bg-charcoal-bg/80" />
            <div className="h-4 w-3/4 rounded-md bg-charcoal-bg/80" />
          </div>
        </div>

        {/* Right Sticky Widget */}
        <div className="lg:col-span-1">
          <div className="border border-charcoal-border rounded-3xl p-6 shadow-sm flex flex-col gap-5 bg-white">
            <div className="flex justify-between items-center">
              <div className="h-6 w-28 rounded-lg bg-charcoal-bg" />
              <div className="h-4 w-16 rounded-md bg-charcoal-bg" />
            </div>
            <div className="h-28 rounded-2xl bg-charcoal-bg/60 border border-charcoal-border/40" />
            <div className="h-12 rounded-xl bg-charcoal-bg" />
          </div>
        </div>
      </div>
    </div>
  );
}
