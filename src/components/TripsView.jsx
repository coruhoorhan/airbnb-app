import React, { useState } from "react";
import { Briefcase, Calendar, MapPin, AlertTriangle, ArrowRight } from "lucide-react";
import { formatCurrency } from "../lib/currencyEngine.js";
import { CancelBookingModal } from "./CancelBookingModal.jsx";

export function TripsView({ bookings = [], listings = [], onCancelBooking, onExplore, currency = "TRY" }) {
  const [cancelTarget, setCancelTarget] = useState(null);
  const handleCancelConfirmed = (bookingId) => {
    onCancelBooking(bookingId);
    setCancelTarget(null);
  };

  if (bookings.length === 0) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-16 text-center flex flex-col items-center gap-4 animate-in fade-in">
        <div className="w-16 h-16 bg-charcoal-bg rounded-full flex items-center justify-center text-charcoal-light">
          <Briefcase className="w-8 h-8" />
        </div>
        <h2 className="text-2xl font-bold text-charcoal">Henüz rezerve edilmiş bir seyahatiniz yok</h2>
        <p className="text-sm text-charcoal-light max-w-md font-medium">Bavullarınızı hazırlama zamanı! Bir sonraki tatiliniz için harika yerler keşfedin.</p>
        <button
          onClick={onExplore}
          className="mt-2 px-6 py-3 bg-charcoal text-white rounded-xl font-bold text-xs hover:bg-black transition-colors"
        >
          Aramaya Başlayın
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col gap-6 animate-in fade-in duration-300">
      <div>
        <h1 className="text-3xl font-extrabold text-charcoal tracking-tight">Seyahatlerim</h1>
        <p className="text-sm text-charcoal-light font-medium mt-1">Yaklaşan ve geçmiş tüm tatil rezervasyonlarınız.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {bookings.map((booking) => {
          const listing = listings.find((l) => l.id === booking.listingId);
          const isCancelled = booking.status === "cancelled";
          const isConfirmed = booking.status === "confirmed";

          return (
            <div 
              key={booking.id}
              className={`bg-white border rounded-3xl p-5 shadow-xs flex flex-col justify-between gap-4 transition-all ${
                isCancelled ? "border-charcoal-border/40 opacity-70 bg-charcoal-bg/30" : "border-charcoal-border hover:shadow-md"
              }`}
            >
              <div className="flex gap-4">
                <img 
                  src={listing?.images?.[0] || "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=300&q=80"}
                  alt={listing?.title}
                  className="w-24 h-24 rounded-2xl object-cover shrink-0"
                />
                <div className="flex flex-col justify-between">
                  <div>
                    <span className={`text-[10px] font-extrabold px-2.5 py-0.5 rounded-full inline-block mb-1 ${
                      isConfirmed ? "bg-emerald-50 text-emerald-700 border border-emerald-200" :
                      isCancelled ? "bg-rose-50 text-rose-700 border border-rose-200" :
                      "bg-amber-50 text-amber-700 border border-amber-200"
                    }`}>
                      {isConfirmed ? "✓ Onaylandı" : isCancelled ? "✕ İptal Edildi" : "… Onay Bekliyor"}
                    </span>
                    <h3 className="font-bold text-sm text-charcoal leading-tight line-clamp-2">{listing?.title}</h3>
                    <p className="text-xs text-charcoal-light font-medium mt-1 flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5 text-airbnb" />
                      <span>{listing?.city}, {listing?.country}</span>
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-charcoal-bg/80 rounded-2xl p-3.5 text-xs flex items-center justify-between border border-charcoal-border/50">
                <div className="flex items-center gap-2 font-semibold text-charcoal">
                  <Calendar className="w-4 h-4 text-charcoal-light" />
                  <span>{booking.checkIn} → {booking.checkOut}</span>
                </div>
                <span className="font-black text-sm text-airbnb">
                  {formatCurrency(booking.totalPrice, currency)}
                </span>
              </div>

              {!isCancelled && (
                <div className="flex items-center justify-between pt-2 border-t border-charcoal-border/40">
                  <span className="text-xs text-charcoal-light">İptal Politikası: {listing?.cancellationPolicy || "Esnek"}</span>
                  <button
                    onClick={() => setCancelTarget(booking)}
                    className="text-xs font-bold text-rose-600 hover:text-rose-800 underline cursor-pointer"
                  >
                    Rezervasyonu İptal Et
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {cancelTarget && (
        <CancelBookingModal
          isOpen={!!cancelTarget}
          booking={cancelTarget}
          listing={listings.find((l) => l.id === cancelTarget.listingId)}
          onClose={() => setCancelTarget(null)}
          onCancelConfirmed={handleCancelConfirmed}
          currency={currency}
        />
      )}
      </div>
  );
}
