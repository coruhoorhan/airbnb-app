import React, { useState, useEffect } from "react";
import { Star, Heart, Bell, BellOff, ChevronLeft, ChevronRight, Zap, MapPin, Compass, Clock } from "lucide-react";
import { formatCurrency } from "../lib/currencyEngine.js";

export function ListingCard({ listing, onSelect, isFavorite, onToggleFavorite, currency = "TRY", featured = false, currentUserId = "usr_guest_01" }) {
  const [currentImgIndex, setCurrentImgIndex] = useState(0);
  const [watchedIds, setWatchedIds] = useState(new Set());

  // Derive watching state from watchedIds set
  const isWatched = watchedIds.has(listing.id);

  useEffect(() => {
    fetch(`/api/price-watches?userId=${currentUserId}`)
      .then(r => r.json())
      .then(d => {
        if (d.success && d.data) {
          setWatchedIds(new Set(d.data.map(w => w.listingId)));
        }
      })
      .catch(() => {});
  }, [currentUserId]);

  const images = listing.images && listing.images.length > 0
    ? listing.images
    : ["https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=800&q=80"];

  const handleNextImage = (e) => {
    e.stopPropagation();
    setCurrentImgIndex((prev) => (prev + 1) % images.length);
  };

  const handlePrevImage = (e) => {
    e.stopPropagation();
    setCurrentImgIndex((prev) => (prev - 1 + images.length) % images.length);
  };

  const handleFavoriteClick = (e) => {
    e.stopPropagation();
    onToggleFavorite(listing.id);
  };

  const handlePriceWatch = async (e) => {
    e.stopPropagation();
    if (isWatched) {
      try {
        await fetch(`/api/price-watches/${listing.id}?userId=${currentUserId}`, { method: "DELETE" });
      } catch {/* ignore */}
      setWatchedIds(prev => { const s = new Set(prev); s.delete(listing.id); return s; });
    } else {
      try {
        await fetch("/api/price-watches", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userId: currentUserId, listingId: listing.id })
        });
      } catch {/* ignore */}
      setWatchedIds(prev => { const s = new Set(prev); s.add(listing.id); return s; });
    }
  };

  const effectivePrice = listing.lastMinuteDiscount > 0 && listing.lastMinuteOriginalPrice
    ? Math.round(listing.lastMinuteOriginalPrice * (1 - listing.lastMinuteDiscount / 100))
    : listing.pricePerNight;

  return (
    <div
      onClick={() => onSelect(listing)}
      className={`flex flex-col gap-3 group cursor-pointer select-none animate-in fade-in duration-300 ${
        featured ? "sm:col-span-2 lg:col-span-2 lg:row-span-2" : ""
      }`}
    >
      {/* Cinematic Image Container with 3D Hover Depth */}
      <div className={`relative w-full overflow-hidden rounded-3xl bg-charcoal-bg shadow-border group-hover:shadow-xl transition-shadow duration-500 ${
        featured ? "aspect-[16/10] lg:aspect-[16/9]" : "aspect-[4/3] sm:aspect-square"
      }`}>
        <img
          src={images[currentImgIndex]}
          alt={listing.title}
          className="h-full w-full object-cover transition-transform duration-700 group-hover:scale-108"
          loading="lazy"
        />

        {/* Coastal Badges Overlay */}
        <div className="absolute top-3.5 left-3.5 flex flex-col gap-1.5 items-start">
          {listing.instantBook && (
            <div className="bg-charcoal/90 text-white backdrop-blur-md px-2.5 py-1 rounded-xl text-[10px] font-mono font-bold flex items-center gap-1 shadow-sm border border-white/10">
              <Zap className="w-3 h-3 text-amber-400 fill-amber-400" />
              <span>ANINDA ONAY</span>
            </div>
          )}
          {listing.lastMinuteDiscount > 0 && (
            <div className="bg-amber-500 text-white backdrop-blur-md px-2.5 py-1 rounded-xl text-[10px] font-mono font-bold flex items-center gap-1 shadow-sm border border-white/20">
              <Clock className="w-3 h-3" />
              <span>SON DAKİKA -%{listing.lastMinuteDiscount}</span>
            </div>
          )}
          <div className="bg-white/90 text-charcoal backdrop-blur-md px-2 py-0.5 rounded-lg text-[9px] font-mono font-bold tracking-wider uppercase border border-charcoal-border/60">
            {listing.category}
          </div>
        </div>

        {/* Favorite Heart Button */}
        <button
          onClick={handleFavoriteClick}
          className="absolute top-3.5 right-3.5 p-2.5 rounded-full bg-black/20 hover:bg-black/40 backdrop-blur-md active:scale-90 transition-[background-color,transform] focus:outline-none"
          title={isFavorite ? "Favorilerden Çıkar" : "Favorilere Ekle"}
        >
          <Heart
            className={`w-5 h-5 transition-colors drop-shadow-md ${
              isFavorite
                ? "fill-airbnb text-airbnb"
                : "fill-white/20 text-white stroke-[2]"
            }`}
          />
        </button>
        {/* Price Watch Button */}
        <button
          onClick={handlePriceWatch}
          className="absolute top-[68px] right-3.5 p-2.5 rounded-full bg-black/20 hover:bg-black/40 backdrop-blur-md active:scale-90 transition-[background-color,transform] focus:outline-none"
          title={isWatched ? "Fiyat Takibini Bırak" : "Fiyat Takibine Ekle"}
        >
          {isWatched ? (
            <BellOff className="w-5 h-5 text-amber-300 drop-shadow-md" />
          ) : (
            <Bell className="w-5 h-5 text-white fill-white/20 drop-shadow-md" />
          )}
        </button>

        {/* Carousel Arrows */}
        {images.length > 1 && (
          <>
            <button
              onClick={handlePrevImage}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/90 shadow-md flex items-center justify-center text-charcoal opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white hover:scale-105 active:scale-95"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={handleNextImage}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-white/90 shadow-md flex items-center justify-center text-charcoal opacity-0 group-hover:opacity-100 transition-opacity hover:bg-white hover:scale-105 active:scale-95"
            >
              <ChevronRight className="w-4 h-4" />
            </button>

            {/* Pagination Indicators */}
            <div className="absolute bottom-3 left-1/2 -translate-x-1/2 flex items-center gap-1.5 bg-black/30 backdrop-blur-xs px-2 py-1 rounded-full">
              {images.map((_, idx) => (
                <div
                  key={idx}
                  className={`rounded-full transition-[width,height,background-color] ${
                    idx === currentImgIndex
                      ? "w-2.5 h-1.5 bg-white"
                      : "w-1.5 h-1.5 bg-white/50"
                  }`}
                />
              ))}
            </div>
          </>
        )}
      </div>

      {/* Modernist Editorial Information */}
      <div className="flex items-center justify-between text-charcoal dark:text-white">
        <span className={`truncate tracking-tight flex items-center gap-1 ${featured ? "text-base lg:text-lg font-extrabold" : "text-sm font-extrabold"}`}>
          <MapPin className="w-3.5 h-3.5 text-airbnb shrink-0" />
          {listing.city}, {listing.country}
        </span>
        <div className="flex items-center gap-1 shrink-0 text-xs font-bold bg-charcoal-bg dark:bg-white/10 px-2 py-0.5 rounded-lg border border-charcoal-border/50 dark:border-white/10">
          <Star className="w-3 h-3 fill-charcoal text-charcoal" />
          <span>{listing.avgRating > 0 ? listing.avgRating.toFixed(2) : "5.0"}</span>
        </div>
      </div>
      <p className={`text-charcoal-light dark:text-gray-400 font-medium line-clamp-1 ${featured ? "text-sm lg:text-base" : "text-xs"}`}>
        {listing.title}
      </p>
      <div className="flex items-baseline justify-between pt-1 border-t border-charcoal-border/40 mt-1">
        <span className="text-[11px] font-mono text-charcoal-light dark:text-gray-400">
          Gecelik Fiyat:
        </span>
        <div className="flex items-baseline gap-1.5 font-mono">
          {listing.lastMinuteDiscount > 0 && (
            <>
              <span className="text-[11px] text-charcoal-light/70 dark:text-gray-500 line-through">
                {formatCurrency(listing.lastMinuteOriginalPrice || listing.pricePerNight, currency)}
              </span>
              <span className={`font-black text-amber-500 ${featured ? "text-xl lg:text-2xl" : "text-base"}`}>
                {formatCurrency(effectivePrice, currency)}
              </span>
            </>
          )}
          {!(listing.lastMinuteDiscount > 0) && (
            <span className={`font-black text-airbnb ${featured ? "text-xl lg:text-2xl" : "text-base"}`}>
              {formatCurrency(effectivePrice, currency)}
            </span>
          )}
          <span className="text-charcoal-light dark:text-gray-400 text-[11px] font-normal">/gece</span>
        </div>
      </div>
    </div>
  );
}