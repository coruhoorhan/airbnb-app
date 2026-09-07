import React, { useState, useEffect } from "react";
import { ListingCard } from "./ListingCard.jsx";
import { Sparkles, ChevronLeft, ChevronRight } from "lucide-react";

export function RecommendationCarousel({ userId, onSelectListing, currency = "TRY" }) {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRecommendations() {
      try {
        const res = await fetch("/graphql", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: `
          query GetRecommendations($userId: ID) {
            recommendedListings(userId: $userId, limit: 6) {
              id
              title
              description
              category
              propertyType
              pricePerNight
              maxGuests
              bedrooms
              beds
              baths
              city
              country
              lat
              lng
              amenities
              images
              hostId
              avgRating
              reviewCount
              lastMinuteDiscount
              lastMinuteOriginalPrice
              instantBook
            }
          }
        `,
            variables: { userId: userId || null }
          })
        });
        const result = await res.json();
        if (result.data?.recommendedListings) {
          setRecommendations(result.data.recommendedListings);
        }
      } catch (err) {
        console.error("Error fetching recommendations:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchRecommendations();
  }, [userId]);

  if (loading) return null;
  if (recommendations.length === 0) return null;

  const scrollContainer = (direction) => {
    const container = document.getElementById("recommendation-scroll-container");
    if (container) {
      const scrollAmount = 400;
      container.scrollBy({ left: direction === 'left' ? -scrollAmount : scrollAmount, behavior: "smooth" });
    }
  };

  return (
    <div className="w-full py-8 mt-4 border-t border-charcoal-border/50 dark:border-white/10 relative">
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-gradient-to-br from-amber-400 to-amber-600 rounded-2xl shadow-lg">
            <Sparkles className="w-6 h-6 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-extrabold text-charcoal dark:text-white flex items-center gap-2">
              Sizin İçin Önerilenler
              <span className="bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 text-[10px] font-black px-2 py-0.5 rounded-full uppercase tracking-widest">
                Yapay Zeka
              </span>
            </h2>
            <p className="text-sm font-medium text-charcoal-light dark:text-gray-400 mt-1">Geçmiş tercihlerinize ve trendlere göre eşleşmeler</p>
          </div>
        </div>

        <div className="hidden sm:flex gap-2">
          <button
            onClick={() => scrollContainer('left')}
            className="p-2 rounded-full border border-charcoal-border dark:border-white/10 hover:bg-charcoal-bg dark:hover:bg-white/5 transition-colors cursor-pointer"
          >
            <ChevronLeft className="w-5 h-5 text-charcoal dark:text-white" />
          </button>
          <button
            onClick={() => scrollContainer('right')}
            className="p-2 rounded-full border border-charcoal-border dark:border-white/10 hover:bg-charcoal-bg dark:hover:bg-white/5 transition-colors cursor-pointer"
          >
            <ChevronRight className="w-5 h-5 text-charcoal dark:text-white" />
          </button>
        </div>
      </div>

      <div
        id="recommendation-scroll-container"
        className="flex gap-6 overflow-x-auto pb-6 pt-2 snap-x snap-mandatory hide-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0"
        style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
      >
        {recommendations.map((listing) => (
          <div key={listing.id} className="min-w-[280px] sm:min-w-[320px] max-w-[320px] shrink-0 snap-start">
            <ListingCard
              listing={listing}
              onSelect={onSelectListing}
              isFavorite={false} // Would need favorite context here to fully implement
              onToggleFavorite={() => {}}
              currency={currency}
              currentUserId={userId}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
