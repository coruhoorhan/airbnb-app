import React, { useEffect, useState, useRef } from "react";
import { ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
import { ListingCard } from "./ListingCard.jsx";

export function RecommendationCarousel({ currentUser, onSelectListing, currency, isFavorite, onToggleFavorite }) {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);
  const scrollContainerRef = useRef(null);

  useEffect(() => {
    let url = "/api/recommendations?limit=6";
    if (currentUser?.id) {
      url += `&userId=${currentUser.id}`;
    }
    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setRecommendations(data.recommendations);
        }
      })
      .catch((err) => console.error("Error fetching recommendations:", err))
      .finally(() => setLoading(false));
  }, [currentUser]);

  const scrollLeft = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollBy({ left: -320, behavior: "smooth" });
    }
  };

  const scrollRight = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollBy({ left: 320, behavior: "smooth" });
    }
  };

  if (loading || recommendations.length === 0) return null;

  return (
    <div className="mb-12 relative animate-in fade-in">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl sm:text-2xl font-display font-extrabold text-charcoal dark:text-white tracking-tight flex items-center gap-2">
          <Sparkles className="w-6 h-6 text-amber-400" />
          Sizin İçin Önerilenler
        </h2>
        <div className="flex items-center gap-2">
          <button onClick={scrollLeft} className="p-2 rounded-full border border-charcoal-border dark:border-white/10 hover:bg-charcoal-bg dark:hover:bg-white/10 text-charcoal dark:text-white transition-colors cursor-pointer">
            <ChevronLeft className="w-4 h-4" />
          </button>
          <button onClick={scrollRight} className="p-2 rounded-full border border-charcoal-border dark:border-white/10 hover:bg-charcoal-bg dark:hover:bg-white/10 text-charcoal dark:text-white transition-colors cursor-pointer">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
      <div className="relative">
        <div ref={scrollContainerRef} className="flex gap-6 overflow-x-auto snap-x snap-mandatory no-scrollbar pb-4 scroll-smooth">
          {recommendations.map((listing) => (
            <div key={listing.id} className="min-w-[280px] sm:min-w-[320px] snap-start shrink-0">
              <ListingCard
                listing={listing}
                onSelect={(l) => onSelectListing(l)}
                isFavorite={isFavorite(listing.id)}
                onToggleFavorite={onToggleFavorite}
                currency={currency}
                currentUserId={currentUser?.id}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
