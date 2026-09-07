import React, { useState, useEffect } from "react";
import { Sparkles, Star, MapPin, Loader2 } from "lucide-react";

export function RecommendedListings({ userId, onSelectListing, currency = "TRY" }) {
  const [recommendations, setRecommendations] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchRecommendations() {
      try {
        setLoading(true);
        const query = `
          query GetRecommendations($userId: ID) {
            recommendedListings(userId: $userId, limit: 4) {
              id
              title
              category
              city
              pricePerNight
              avgRating
              reviewCount
              images
            }
          }
        `;
        const res = await fetch("/graphql", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, variables: { userId: userId || null } })
        });
        const result = await res.json();
        if (result.data?.recommendedListings) {
          setRecommendations(result.data.recommendedListings);
        }
      } catch (err) {
        console.error("Öneri motoru hatası:", err);
      } finally {
        setLoading(false);
      }
    }
    fetchRecommendations();
  }, [userId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8 text-charcoal-light">
        <Loader2 className="w-5 h-5 animate-spin text-coral mr-2" />
        <span className="text-xs font-medium">Size özel ilanlar hazırlanıyor...</span>
      </div>
    );
  }

  if (recommendations.length === 0) return null;

  return (
    <section className="my-8">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-black text-charcoal flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-coral fill-coral/20" /> Size Özel Önerilen İlanlar
          </h3>
          <p className="text-xs text-charcoal-light">
            {userId ? "Geçmiş rezervasyonlarınız ve ilgi alanlarınıza göre yapay zeka ile seçildi." : "Fatsa'nın en çok beğenilen ve puanlanan popüler konaklamaları."}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {recommendations.map((item) => (
          <div
            key={item.id}
            onClick={() => onSelectListing && onSelectListing(item)}
            className="group cursor-pointer bg-white border border-charcoal-border rounded-2xl overflow-hidden hover:shadow-md transition-all flex flex-col"
          >
            <div className="relative aspect-4/3 bg-gray-100 overflow-hidden">
              {item.images && item.images[0] ? (
                <img
                  src={item.images[0]}
                  alt={item.title}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-gray-400">Görsel Yok</div>
              )}
              <div className="absolute top-2 right-2 px-2 py-1 bg-white/90 backdrop-blur-xs rounded-lg text-[10px] font-bold text-charcoal flex items-center gap-1 shadow-xs">
                <Star className="w-3 h-3 text-amber-500 fill-amber-500" />
                <span>{item.avgRating?.toFixed(1) || "5.0"}</span>
              </div>
            </div>
            <div className="p-3.5 flex flex-col justify-between flex-1">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-coral block mb-1">
                  {item.category}
                </span>
                <h4 className="text-xs font-bold text-charcoal line-clamp-1 group-hover:text-coral transition-colors">
                  {item.title}
                </h4>
                <div className="flex items-center gap-1 text-[11px] text-charcoal-light mt-1">
                  <MapPin className="w-3 h-3 text-charcoal-light" />
                  <span>{item.city}</span>
                </div>
              </div>
              <div className="mt-3 pt-2 border-t border-gray-100 flex items-baseline justify-between">
                <span className="text-xs font-black text-charcoal">
                  ₺{item.pricePerNight?.toLocaleString("tr-TR")} <span className="text-[10px] font-normal text-charcoal-light">/ gece</span>
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
export default RecommendedListings;
