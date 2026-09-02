import React from "react";
import { Heart, ArrowLeft } from "lucide-react";
import { ListingCard } from "./ListingCard.jsx";

export function WishlistView({ favorites = [], listings = [], onSelectListing, onToggleFavorite, onExplore, currency = "TRY" }) {
  const favoriteListings = listings.filter((l) => favorites.includes(l.id));

  if (favoriteListings.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center flex flex-col items-center gap-4 animate-in fade-in">
        <div className="w-16 h-16 bg-airbnb/10 text-airbnb rounded-full flex items-center justify-center">
          <Heart className="w-8 h-8 fill-airbnb" />
        </div>
        <h2 className="text-2xl font-bold text-charcoal">Favoriler listeniz henüz boş</h2>
        <p className="text-sm text-charcoal-light max-w-md font-medium">Beğendiğiniz tatil evlerini kalp ikonuna tıklayarak buraya kaydedin.</p>
        <button
          onClick={onExplore}
          className="mt-2 px-6 py-3 bg-charcoal text-white rounded-xl font-bold text-sm hover:bg-black transition-colors"
        >
          İlanları Keşfet
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col gap-6 animate-in fade-in duration-300">
      <div>
        <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">Favorilerim ({favoriteListings.length})</h1>
        <p className="text-sm text-charcoal-light font-medium mt-1">Kaydettiğiniz ve daha sonra incelemek istediğiniz yerler.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {favoriteListings.map((listing) => (
          <ListingCard
            key={listing.id}
            listing={listing}
            onSelect={onSelectListing}
            isFavorite={true}
            onToggleFavorite={onToggleFavorite}
            currency={currency}
          />
        ))}
      </div>
    </div>
  );
}
