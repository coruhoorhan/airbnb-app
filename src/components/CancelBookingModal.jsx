import React, { useState, useEffect } from "react";
import { X, AlertTriangle, CheckCircle, Loader2, Calendar } from "lucide-react";
import { formatCurrency } from "../lib/currencyEngine.js";
import { calculateCancellationRefund } from "../lib/bookingEngine.js";

export function CancelBookingModal({ isOpen, onClose, booking, listing, onCancelConfirmed, currency = "TRY" }) {
  const [refund, setRefund] = useState(null);
  const [cancelling, setCancelling] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!isOpen || !booking || !listing) return;
    setCancelling(false);
    setDone(false);
    setError(null);
    const policy = listing.cancellationPolicy || "flexible";
    const result = calculateCancellationRefund(booking.checkIn, booking.totalPrice, booking.nightlyPrice, policy, false, Date.now());
    setRefund(result);
  }, [isOpen, booking, listing]);

  const handleConfirm = async () => {
    setCancelling(true);
    setError(null);
    try {
      const res = await fetch(`/api/bookings/${booking.id}/cancel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cancelReason: "Kullanıcı iptali" })
      });
      const data = await res.json();
      if (!data.success) {
        setError(data.error || "İptal işlemi başarısız oldu.");
        setCancelling(false);
        return;
      }
      setDone(true);
      onCancelConfirmed(booking.id);
    } catch (err) {
      setError("Sunucu hatası: " + err.message);
      setCancelling(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white w-full max-w-md rounded-3xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-charcoal-border/50 shrink-0">
          <h2 className="text-lg font-bold text-charcoal flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-rose-500" />
            Rezervasyonu İptal Et
          </h2>
          <button aria-label="X"
            onClick={onClose}
            className="p-2 rounded-full hover:bg-charcoal-bg transition-colors cursor-pointer"
          > <X /> </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {done ? (
            <div className="rounded-2xl bg-emerald-50 border border-emerald-200 p-6 text-center space-y-3">
              <CheckCircle className="w-12 h-12 text-emerald-500 mx-auto" />
              <h3 className="text-lg font-bold text-emerald-700">Rezervasyon İptal Edildi</h3>
              <p className="text-sm text-emerald-600 font-medium">{refund?.description}</p>
              {refund?.refundAmount > 0 && (
                <p className="text-2xl font-black text-emerald-600 font-mono">
                  İade: ₺{refund.refundAmount.toLocaleString("tr-TR")}
                </p>
              )}
              <button
                onClick={onClose}
                className="mt-2 px-6 py-2.5 bg-emerald-600 text-white rounded-2xl font-bold text-sm hover:bg-emerald-700 transition-colors cursor-pointer"
              >
                Kapat
              </button>
            </div>
          ) : (
            <>
              {/* Booking Summary */}
              <div className="rounded-2xl bg-charcoal-bg/80 border border-charcoal-border/50 p-4 space-y-2">
                <h3 className="font-bold text-sm text-charcoal">{listing?.title}</h3>
                <div className="flex items-center gap-2 text-xs text-charcoal-light font-medium">
                  <Calendar className="w-3.5 h-3.5" />
                  <span>{booking?.checkIn} → {booking?.checkOut}</span>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-charcoal-border/30">
                  <span className="text-xs font-bold text-charcoal-light">Toplam Tutar</span>
                  <span className="text-lg font-black text-airbnb font-mono">
                    {formatCurrency(booking?.totalPrice || 0, currency)}
                  </span>
                </div>
              </div>

              {/* Cancellation Policy */}
              <div className="rounded-2xl border border-charcoal-border p-4 space-y-2">
                <h4 className="font-bold text-xs text-charcoal uppercase tracking-wider">İptal Politikası</h4>
                <span className="inline-block text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 capitalize">
                  {listing?.cancellationPolicy || "Esnek"}
                </span>
              </div>

              {/* Refund Summary */}
              {refund && (
                <div className="rounded-2xl bg-gradient-to-br from-sky-50 to-blue-50/60 border border-sky-200/60 p-4 space-y-2">
                  <h4 className="font-bold text-xs text-sky-700 uppercase tracking-wider">İade Özeti</h4>
                  <p className="text-sm text-charcoal font-medium">{refund.description}</p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-charcoal-light">İade Tutarı</span>
                    <span className="text-2xl font-black font-mono text-emerald-600">
                      ₺{refund.refundAmount.toLocaleString("tr-TR")}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-charcoal-light">İade Oranı</span>
                    <span className="text-lg font-black font-mono text-charcoal">
                      %{refund.refundPercentage}
                    </span>
                  </div>
                </div>
              )}

              {error && (
                <p className="text-sm text-red-500 font-medium bg-red-50 border border-red-200 rounded-2xl p-3">{error}</p>
              )}

              {/* Action Buttons */}
              <div className="flex gap-3 pt-2">
                <button
                  onClick={onClose}
                  disabled={cancelling}
                  className="flex-1 h-11 rounded-2xl border border-charcoal-border text-charcoal font-bold text-sm hover:bg-charcoal-bg transition-colors cursor-pointer disabled:opacity-40"
                >
                  Vazgeç
                </button>
                <button
                  onClick={handleConfirm}
                  disabled={cancelling}
                  className="flex-1 h-11 bg-rose-600 text-white rounded-2xl font-bold text-sm hover:bg-rose-700 transition-colors flex items-center justify-center gap-2 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {cancelling ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <AlertTriangle className="w-4 h-4" />
                  )}
                  {cancelling ? "İptal Ediliyor..." : "İptal Et"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}