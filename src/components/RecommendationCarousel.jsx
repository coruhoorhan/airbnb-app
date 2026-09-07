import React, { useEffect, useState } from "react";
import { ListingCard } from "./ListingCard.jsx";

export function RecommendationCarousel({ currentUserId, onSelectListing, onViewChange }) {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let url = "/api/recommendations?limit=6";
    if (currentUserId) {
      url += `&userId=${currentUserId}`;
    }

    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        if (data.success) {
          setRecommendations(data.data);
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching recommendations:", err);
        setLoading(false);
      });
  }, [currentUserId]);

  if (loading) {
    return (
      <div className="py-8">
        <h2 className="text-2xl font-bold mb-6">Sizin İçin Önerilenler</h2>
        <div className="flex gap-4 overflow-x-auto pb-4 snap-x">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="min-w-[300px] w-[300px] h-[400px] bg-charcoal-border/20 dark:bg-white/5 rounded-3xl animate-pulse snap-start" />
          ))}
        </div>
      </div>
    );
  }

  if (recommendations.length === 0) {
    return null;
  }

  return (
    <div className="py-8">
      <h2 className="text-2xl font-bold mb-6 text-charcoal dark:text-white">Sizin İçin Önerilenler</h2>
      <div className="flex gap-4 overflow-x-auto pb-4 snap-x no-scrollbar">
        {recommendations.map((listing) => (
          <div key={listing.id} className="min-w-[300px] w-[300px] snap-start">
            <ListingCard
              listing={listing}
              onClick={() => onSelectListing(listing)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
