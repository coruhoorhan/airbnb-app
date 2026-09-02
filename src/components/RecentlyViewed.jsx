import React from "react";
import { History } from "lucide-react";
import { ListingCard } from "./ListingCard.jsx";

export function RecentlyViewed({ listings = [], onSelect, favorites = [], onToggleFavorite, currency = "TRY", currentUserId = "usr_guest_01" }) {
  if (listings.length < 2) return null;

  return (
    <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 w-full">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-black text-charcoal dark:text-white tracking-tight flex items-center gap-2">
          <History className="w-5 h-5 text-emerald-600" />
          <span>Son Bakılanlar</span>
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 border border-emerald-200">
            {listings.length} ilan
          </span>
        </h2>
      </div>
      <div className="flex gap-4 overflow-x-auto pb-2 -mx-4 px-4 snap-x">
        {listings.map((l) => (
          <div key={l.id} className="min-w-[270px] max-w-[270px] snap-start">
            <ListingCard
              listing={l}
              onSelect={onSelect}
              isFavorite={favorites.includes(l.id)}
              onToggleFavorite={onToggleFavorite}
              currency={currency}
              currentUserId={currentUserId}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
