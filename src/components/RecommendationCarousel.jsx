import React, { useState, useEffect } from "react";
import { Sparkles, ChevronLeft, ChevronRight } from "lucide-react";
import { ListingCard } from "./ListingCard.jsx";

export function RecommendationCarousel({ userId, currency, onSelectListing }) {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scrollIndex, setScrollIndex] = useState(0);

  useEffect(() => {
    const url = userId ? `/api/recommendations?userId=${userId}&limit=10` : "/api/recommendations?limit=10";
    fetch(url)
      .then(res => res.json())
      .then(data => {
        if (data.success && data.data) {
          setRecommendations(data.data);
        }
      })
      .finally(() => setLoading(false));
  }, [userId]);

  if (loading || recommendations.length === 0) return null;

  const itemsVisible = window.innerWidth >= 1024 ? 4 : window.innerWidth >= 768 ? 3 : 1;
  const maxScroll = Math.max(0, recommendations.length - itemsVisible);

  const scrollLeft = () => setScrollIndex(i => Math.max(0, i - 1));
  const scrollRight = () => setScrollIndex(i => Math.min(maxScroll, i + 1));

  return (
    <div className="mb-10 w-full animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-purple-500" />
          <h2 className="text-xl font-black text-charcoal dark:text-white tracking-tight">Size Özel Öneriler</h2>
        </div>
        <div className="flex gap-2">
          <button
            onClick={scrollLeft}
            disabled={scrollIndex === 0}
            className="p-2 rounded-full border border-charcoal-border dark:border-white/10 hover:bg-charcoal-bg dark:hover:bg-white/5 disabled:opacity-30 transition-colors"
          >
            <ChevronLeft className="w-4 h-4 text-charcoal dark:text-white" />
          </button>
          <button
            onClick={scrollRight}
            disabled={scrollIndex >= maxScroll}
            className="p-2 rounded-full border border-charcoal-border dark:border-white/10 hover:bg-charcoal-bg dark:hover:bg-white/5 disabled:opacity-30 transition-colors"
          >
            <ChevronRight className="w-4 h-4 text-charcoal dark:text-white" />
          </button>
        </div>
      </div>

      <div className="overflow-hidden relative -mx-4 px-4 sm:mx-0 sm:px-0">
        <div
          className="flex gap-5 transition-transform duration-500 ease-out"
          style={{ transform: `translateX(-${scrollIndex * (100 / itemsVisible)}%)` }}
        >
          {recommendations.map(listing => (
            <div key={listing.id} className="min-w-[85vw] sm:min-w-[calc(50%-10px)] md:min-w-[calc(33.333%-14px)] lg:min-w-[calc(25%-15px)] shrink-0">
              <ListingCard
                listing={listing}
                onSelect={onSelectListing}
                currency={currency}
                currentUserId={userId}
                isFavorite={false}
                onToggleFavorite={() => {}}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
