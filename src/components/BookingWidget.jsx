import React, { useState, useMemo } from "react";
import { 
  Star, 
  Zap, 
  AlertCircle, 
  Calendar, 
  CheckCircle2, 
  Tag, 
  X, 
  Loader2, 
  CreditCard, 
  ShieldCheck, 
  Sparkles,
  Waves,
  Lock
} from "lucide-react";
import { calculateBookingPrice, validateBookingConflict } from "../lib/bookingEngine.js";
import { validateAndCalculateDiscount } from "../lib/couponEngine.js";
import { formatCurrency } from "../lib/currencyEngine.js";
import { PaymentModal } from "./PaymentModal.jsx";

// Yerel saat dilimiyle "YYYY-MM-DD" anahtarı üretir (takvim karşılaştırmaları için)
function toDateKey(dt) {
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function BookingWidget({ listing, bookings = [], availability = [], onBook, currentUser, currency = "TRY" }) {
  const tomorrow = new Date(Date.now() + 86400000).toISOString().split("T")[0];
  const nextWeek = new Date(Date.now() + 6 * 86400000).toISOString().split("T")[0];

  // Son dakika fırsatı: indirimli efektif gecelik fiyat
  const effectivePrice = listing.lastMinuteDiscount > 0
    ? (listing.lastMinuteOriginalPrice
        ? Math.round(listing.lastMinuteOriginalPrice * (1 - listing.lastMinuteDiscount / 100))
        : listing.pricePerNight)
    : listing.pricePerNight;
  const isLastMinuteDeal = listing.lastMinuteDiscount > 0 && listing.lastMinuteOriginalPrice > 0;
  const savingsPerNight = isLastMinuteDeal
    ? Math.max(0, listing.lastMinuteOriginalPrice - effectivePrice)
    : 0;

  // Rezervasyonlu tarih aralıklarını tek tek tarihlere çevir
  const bookedDates = useMemo(() => {
    const set = new Set();
    (bookings || []).forEach((b) => {
      const start = new Date(b.checkIn);
      const end = new Date(b.checkOut);
      if (isNaN(start.getTime()) || isNaN(end.getTime())) return;
      for (let d = new Date(start); d < end; d.setDate(d.getDate() + 1)) {
        set.add(toDateKey(d));
      }
    });
    return set;
  }, [bookings]);

  // Önümüzdeki 31 günü tek satırlık takvim hücreleri olarak hazırla
  const calendarDays = useMemo(() => {
    const days = [];
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    for (let i = 0; i < 31; i++) {
      const d = new Date(today);
      d.setDate(today.getDate() + i);
      days.push({
        key: toDateKey(d),
        day: d.getDate(),
        weekday: d.toLocaleDateString("tr-TR", { weekday: "short" }).slice(0, 2),
        isBooked: bookedDates.has(toDateKey(d))
      });
    }
    return days;
  }, [bookedDates]);

  const [checkIn, setCheckIn] = useState(tomorrow);
  const [checkOut, setCheckOut] = useState(nextWeek);
  const [guests, setGuests] = useState(2);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [bookingSuccessData, setBookingSuccessData] = useState(null);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);

  // Coupon state
  const [couponCodeInput, setCouponCodeInput] = useState("");
  const [appliedCoupon, setAppliedCoupon] = useState(null);
  const [couponError, setCouponError] = useState("");
  const [isValidatingCoupon, setIsValidatingCoupon] = useState(false);

  // Validate date conflict
  const conflictCheck = useMemo(() => {
    try {
      return validateBookingConflict(listing.id, checkIn, checkOut, bookings, availability);
    } catch {
      return { hasConflict: true, reason: "Geçersiz tarih aralığı." };
    }
  }, [listing.id, checkIn, checkOut, bookings, availability]);

  // Calculate base pricing breakdown
  const priceMath = useMemo(() => {
    try {
      return calculateBookingPrice(checkIn, checkOut, effectivePrice, listing.cleaningFee, listing.serviceFee);
    } catch {
      return null;
    }
  }, [checkIn, checkOut, effectivePrice, listing.cleaningFee, listing.serviceFee]);

  // Dynamically update or validate discount if dates/base price change
  const currentDiscountAmount = useMemo(() => {
    if (!appliedCoupon || !priceMath) return 0;
    try {
      const res = validateAndCalculateDiscount(appliedCoupon, priceMath.basePrice, checkIn);
      return res.discountAmount;
    } catch {
      return 0;
    }
  }, [appliedCoupon, priceMath, checkIn]);

  // Total price after discount in base TRY
  const finalTotalPrice = useMemo(() => {
    if (!priceMath) return 0;
    const discountedBase = Math.max(0, priceMath.basePrice - currentDiscountAmount);
    return Math.max(0, discountedBase + (listing.cleaningFee || 0) + (listing.serviceFee || 0));
  }, [priceMath, currentDiscountAmount, listing]);

  const handleApplyCoupon = async (e) => {
    e?.preventDefault();
    const cleanCode = couponCodeInput.trim().toUpperCase();
    if (!cleanCode) {
      setCouponError("Lütfen bir kupon kodu giriniz.");
      return;
    }
    if (!priceMath || priceMath.basePrice <= 0) {
      setCouponError("Lütfen önce geçerli konaklama tarihleri seçiniz.");
      return;
    }

    setCouponError("");
    setIsValidatingCoupon(true);

    try {
      const response = await fetch("/api/coupons/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: cleanCode,
          basePrice: priceMath.basePrice,
          checkIn
        })
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Geçersiz veya süresi dolmuş kupon kodu.");
      }

      setAppliedCoupon({
        code: data.code,
        discountType: data.discountType,
        discountValue: data.discountValue,
        discountAmount: data.discountAmount
      });
      setCouponError("");
      setCouponCodeInput("");
    } catch (err) {
      setCouponError(err.message);
      setAppliedCoupon(null);
    } finally {
      setIsValidatingCoupon(false);
    }
  };

  const handleRemoveCoupon = () => {
    setAppliedCoupon(null);
    setCouponError("");
    setCouponCodeInput("");
  };

  const handleOpenPayment = () => {
    if (conflictCheck.hasConflict || !priceMath) return;
    if (currentUser?.id === listing.hostId) {
      alert("Kendi ilanınıza rezervasyon ve ödeme yapamazsınız!");
      return;
    }
    setIsPaymentModalOpen(true);
  };

  const handlePaymentSuccess = (result) => {
    setIsPaymentModalOpen(false);
    setBookingSuccessData(result);
    if (onBook) {
      onBook(result.booking);
    }
  };

  if (bookingSuccessData) {
    const { booking, payment } = bookingSuccessData;
    return (
      <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xl text-center flex flex-col items-center gap-4 animate-in fade-in zoom-in duration-300">
        <div className="w-16 h-16 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center shadow-inner">
          <CheckCircle2 className="w-10 h-10" />
        </div>
        <div>
          <div className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-xs font-bold border border-emerald-200 mb-1">
            <Sparkles className="w-3 h-3 text-emerald-600" />
            iyzico Ödemesi Onaylandı
          </div>
          <h3 className="text-xl font-extrabold text-charcoal">Rezervasyon Başarılı!</h3>
          <p className="text-xs text-charcoal-light mt-1">
            Ödemeniz alındı ve rezervasyonunuz anında onaylandı. İyi tatiller dileriz!
          </p>
        </div>

        {/* Receipt Details Box */}
        <div className="bg-charcoal-bg rounded-2xl p-4 w-full text-left text-xs space-y-2 border border-charcoal-border">
          <div className="flex justify-between font-medium">
            <span className="text-charcoal-light">Rezervasyon Kodu:</span>
            <span className="font-mono font-bold text-charcoal">{booking?.id}</span>
          </div>
          <div className="flex justify-between font-medium">
            <span className="text-charcoal-light">iyzico Ödeme No:</span>
            <span className="font-mono font-bold text-blue-600">#{payment?.paymentId || booking?.paymentId}</span>
          </div>
          <div className="flex justify-between font-medium">
            <span className="text-charcoal-light">Ödeme Yöntemi:</span>
            <span className="font-semibold text-charcoal">
              {payment?.cardAssociation || "Kart"} (•••• {payment?.lastFourDigits || "0016"})
            </span>
          </div>
          <div className="flex justify-between font-medium">
            <span className="text-charcoal-light">Giriş / Çıkış:</span>
            <span className="font-bold text-charcoal">{checkIn} → {checkOut}</span>
          </div>
          {booking?.couponCode && (
            <div className="flex justify-between font-medium text-emerald-600">
              <span>Kupon İndirimi:</span>
              <span className="font-bold">{booking.couponCode} (-{formatCurrency(booking.discountAmount, currency)})</span>
            </div>
          )}
          <div className="flex justify-between font-medium pt-2 border-t border-charcoal-border/70 text-sm">
            <span className="text-charcoal font-bold">Ödenen Tutar:</span>
            <span className="font-extrabold text-airbnb font-mono">{formatCurrency(booking?.totalPrice, currency)}</span>
          </div>
        </div>

        <button
          onClick={() => {
            setBookingSuccessData(null);
            setAppliedCoupon(null);
          }}
          className="w-full py-3 bg-charcoal text-white rounded-xl font-bold text-xs hover:bg-black transition-colors"
        >
          Yeni Rezervasyon Yap
        </button>
      </div>
    );
  }

  return (
    <div className="sticky top-28 bg-white border border-charcoal-border rounded-3xl p-6 shadow-xl flex flex-col gap-5">
      {/* Price Header */}
      <div className="flex flex-col gap-2">
        {isLastMinuteDeal && (
          <div className="flex items-center justify-between gap-2">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-100 text-amber-800 text-[11px] font-extrabold border border-amber-300">
              <Zap className="w-3.5 h-3.5 text-amber-600" />
              Son Dakika Fırsatı -%{listing.lastMinuteDiscount}
            </span>
            <span className="text-[11px] font-bold text-emerald-600 flex items-center gap-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
              ₺{savingsPerNight.toLocaleString("tr-TR")} tasarruf edin
            </span>
          </div>
        )}
        <div className="flex items-baseline justify-between">
          <div className="flex items-baseline gap-1.5 font-mono">
            {isLastMinuteDeal ? (
              <>
                <span className="text-sm font-bold text-charcoal-light line-through">
                  {formatCurrency(listing.lastMinuteOriginalPrice, currency)}
                </span>
                <span className="text-2xl font-black text-airbnb">
                  {formatCurrency(effectivePrice, currency)}
                </span>
              </>
            ) : (
              <span className="text-2xl font-black text-charcoal">
                {formatCurrency(listing.pricePerNight, currency)}
              </span>
            )}
            <span className="text-charcoal-light text-xs font-normal">/gece</span>
          </div>
          <div className="flex items-center gap-1 text-xs font-bold bg-charcoal-bg px-2.5 py-1 rounded-xl border border-charcoal-border/60">
            <Star className="w-3.5 h-3.5 fill-charcoal text-charcoal" />
            <span>{listing.avgRating > 0 ? listing.avgRating.toFixed(2) : "Yeni"}</span>
            <span className="text-charcoal-light font-normal">({listing.reviewCount} yorum)</span>
          </div>
        </div>
      </div>

      {/* Date & Guest Picker Box */}
      <div className="border border-charcoal-border rounded-2xl overflow-hidden divide-y divide-charcoal-border">
        <div className="grid grid-cols-2 divide-x divide-charcoal-border">
          <div className="p-3 bg-white hover:bg-charcoal-bg/40 transition-colors">
            <label className="block text-[10px] font-extrabold text-charcoal uppercase tracking-wider">GİRİŞ</label>
            <input 
              type="date"
              value={checkIn}
              onChange={(e) => setCheckIn(e.target.value)}
              className="w-full text-xs font-semibold text-charcoal bg-transparent outline-none cursor-pointer mt-0.5"
            />
          </div>
          <div className="p-3 bg-white hover:bg-charcoal-bg/40 transition-colors">
            <label className="block text-[10px] font-extrabold text-charcoal uppercase tracking-wider">ÇIKIŞ</label>
            <input 
              type="date"
              value={checkOut}
              onChange={(e) => setCheckOut(e.target.value)}
              className="w-full text-xs font-semibold text-charcoal bg-transparent outline-none cursor-pointer mt-0.5"
            />
          </div>
        </div>
        <div className="p-3 bg-white flex items-center justify-between">
          <div>
            <label className="block text-[10px] font-extrabold text-charcoal uppercase tracking-wider">MİSAFİRLER</label>
            <span className="text-xs font-semibold text-charcoal">{guests} misafir</span>
          </div>
          <select 
            value={guests}
            onChange={(e) => setGuests(Number(e.target.value))}
            className="text-xs font-bold text-charcoal border border-charcoal-border rounded-lg px-2 py-1 bg-white outline-none cursor-pointer"
          >
            {Array.from({ length: listing.maxGuests || 6 }, (_, i) => i + 1).map((num) => (
              <option key={num} value={num}>{num} Misafir</option>
            ))}
          </select>
        </div>
      </div>

      {/* Availability Calendar */}
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <label className="text-[10px] font-extrabold text-charcoal uppercase tracking-wider flex items-center gap-1">
            <Calendar className="w-3 h-3 text-airbnb" />
            MÜSAİTLİK TAKVİMİ
          </label>
          <span className="text-[10px] text-charcoal-light">Önümüzdeki 31 gün</span>
        </div>
        <div className="flex gap-1 overflow-x-auto pb-1">
          {calendarDays.map((d) => (
            <div
              key={d.key}
              className={`shrink-0 w-9 min-h-[44px] flex flex-col items-center justify-center rounded-xl border transition-colors ${
                d.isBooked
                  ? "bg-charcoal-bg text-charcoal-light border-charcoal-border line-through"
                  : "bg-white text-charcoal border-charcoal-border/60"
              }`}
            >
              <span className="font-bold uppercase opacity-70 text-[9px]">{d.weekday}</span>
              <span className="font-mono font-black text-xs">{d.day}</span>
              {d.isBooked && <span className="w-1 h-1 rounded-full bg-airbnb mt-0.5" />}
            </div>
          ))}
        </div>
      </div>

      {/* Coupon Code Section */}
      <div className="bg-charcoal-bg/60 border border-charcoal-border/70 rounded-2xl p-3.5 flex flex-col gap-2">
        <div className="flex items-center gap-1.5 text-xs font-bold text-charcoal">
          <Tag className="w-3.5 h-3.5 text-airbnb" />
          <span>İndirim Kuponu</span>
        </div>

        {!appliedCoupon ? (
          <form onSubmit={handleApplyCoupon} className="flex flex-col gap-1.5">
            <div className="flex gap-2">
              <input 
                type="text"
                placeholder="Örn: FATSA2026, HOSGELDIN"
                value={couponCodeInput}
                onChange={(e) => {
                  setCouponCodeInput(e.target.value.toUpperCase());
                  if (couponError) setCouponError("");
                }}
                className="flex-1 px-3 py-2 text-xs font-semibold text-charcoal uppercase bg-white border border-charcoal-border rounded-xl outline-none focus:border-airbnb transition-colors"
              />
              <button
                type="submit"
                disabled={isValidatingCoupon || !couponCodeInput.trim()}
                className="px-3.5 py-2 bg-charcoal text-white text-xs font-bold rounded-xl hover:bg-black disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center gap-1 active:scale-95 cursor-pointer"
              >
                {isValidatingCoupon ? <Loader2 className="w-3 h-3 animate-spin" /> : "Uygula"}
              </button>
            </div>
            {couponError && (
              <p className="text-[11px] font-semibold text-rose-600 pl-1">{couponError}</p>
            )}
          </form>
        ) : (
          <div className="flex items-center justify-between bg-emerald-50 border border-emerald-200 rounded-xl p-2.5">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <div>
                <div className="text-xs font-extrabold text-emerald-800">
                  {appliedCoupon.code}
                </div>
                <div className="text-[10px] text-emerald-600 font-medium">
                  {appliedCoupon.discountType === "percentage" 
                    ? `%${appliedCoupon.discountValue} indirim uygulandı` 
                    : `${formatCurrency(appliedCoupon.discountValue, currency)} indirim uygulandı`}
                </div>
              </div>
            </div>
            <button aria-label="X"
              onClick={handleRemoveCoupon}
              className="p-1 text-emerald-700 hover:text-rose-600 hover:bg-emerald-100 rounded-lg transition-colors cursor-pointer"
              title="Kuponu Kaldır"
            > <X /> </button>
          </div>
        )}
      </div>

      {/* Conflict Warning */}
      {conflictCheck.hasConflict && (
        <div className="flex items-start gap-2.5 p-3 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 text-xs font-medium">
          <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <span>{conflictCheck.reason}</span>
        </div>
      )}

      {/* Primary Action Button */}
      <button
        disabled={conflictCheck.hasConflict || isSubmitting || !priceMath}
        onClick={handleOpenPayment}
        className={`w-full py-3.5 rounded-xl font-extrabold text-sm text-white shadow-md transition-all flex items-center justify-center gap-2 ${
          conflictCheck.hasConflict || !priceMath
            ? "bg-charcoal-muted cursor-not-allowed"
            : "bg-gradient-to-r from-airbnb to-amber-600 hover:from-airbnb-dark hover:to-amber-700 active:scale-[0.98] shadow-lg cursor-pointer"
        }`}
      >
        <CreditCard className="w-4 h-4" />
        <span>Rezervasyon ve Ödemeye Geç</span>
      </button>

      <div className="flex items-center justify-center gap-1.5 text-[11px] text-charcoal-light font-medium">
        <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
        <span>iyzico Sandbox ile 256-Bit SSL 3D Ödeme</span>
      </div>

      {/* Dynamic Price Breakdown */}
      {priceMath && (
        <div className="flex flex-col gap-2.5 pt-4 border-t border-charcoal-border/60 text-xs">
          <div className="flex justify-between text-charcoal-light">
            <span className="underline cursor-help">
              {isLastMinuteDeal ? (
                <>
                  <span className="line-through mr-1">
                    {formatCurrency(listing.lastMinuteOriginalPrice, currency)}
                  </span>
                  <span className="text-airbnb font-black">
                    {formatCurrency(effectivePrice, currency)}
                  </span>
                </>
              ) : (
                formatCurrency(listing.pricePerNight, currency)
              )}
              {' '}x {priceMath.nights} gece
            </span>
            <span className="text-charcoal font-bold font-mono">
              {formatCurrency(priceMath.basePrice, currency)}
            </span>
          </div>

          {/* Green Discount Line */}
          {appliedCoupon && currentDiscountAmount > 0 && (
            <div className="flex justify-between text-emerald-600 font-semibold bg-emerald-50/70 px-2.5 py-1.5 rounded-xl border border-emerald-100">
              <span className="flex items-center gap-1">
                <Tag className="w-3.5 h-3.5" />
                İndirim ({appliedCoupon.code})
              </span>
              <span className="font-mono font-bold">-{formatCurrency(currentDiscountAmount, currency)}</span>
            </div>
          )}

          {listing.cleaningFee > 0 && (
            <div className="flex justify-between text-charcoal-light">
              <span className="underline cursor-help">Temizlik ücreti</span>
              <span className="text-charcoal font-bold font-mono">
                {formatCurrency(listing.cleaningFee, currency)}
              </span>
            </div>
          )}
          {listing.serviceFee > 0 && (
            <div className="flex justify-between text-charcoal-light">
              <span className="underline cursor-help">Airbnb hizmet bedeli</span>
              <span className="text-charcoal font-bold font-mono">
                {formatCurrency(listing.serviceFee, currency)}
              </span>
            </div>
          )}

          <div className="flex justify-between text-sm font-black text-charcoal pt-3 border-t border-charcoal-border">
            <span>Toplam Tutar</span>
            <span className="text-airbnb font-extrabold font-mono text-base">
              {formatCurrency(finalTotalPrice, currency)}
            </span>
          </div>
        </div>
      )}

      {/* Payment Modal */}
      <PaymentModal
        isOpen={isPaymentModalOpen}
        onClose={() => setIsPaymentModalOpen(false)}
        listing={listing}
        checkIn={checkIn}
        checkOut={checkOut}
        guests={guests}
        priceMath={priceMath}
        appliedCoupon={appliedCoupon}
        currentDiscountAmount={currentDiscountAmount}
        finalTotalPrice={finalTotalPrice}
        currentUser={currentUser}
        onPaymentSuccess={handlePaymentSuccess}
      />
    </div>
  );
}
