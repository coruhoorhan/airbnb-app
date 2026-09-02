import React, { useState, useEffect } from "react";
import { 
  CreditCard, 
  ShieldCheck, 
  Lock, 
  X, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Sparkles, 
  Calendar, 
  Tag, 
  Building2 
} from "lucide-react";

export function PaymentModal({
  isOpen,
  onClose,
  listing,
  checkIn,
  checkOut,
  guests,
  priceMath,
  appliedCoupon,
  currentDiscountAmount,
  finalTotalPrice,
  currentUser,
  onPaymentSuccess
}) {
  const [cardHolderName, setCardHolderName] = useState(currentUser?.name || "Ahmet Yılmaz");
  const [cardNumber, setCardNumber] = useState("");
  const [expireMonth, setExpireMonth] = useState("12");
  const [expireYear, setExpireYear] = useState("2028");
  const [cvc, setCvc] = useState("123");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  // Taksit seçimi: varsayılan tek çekim
  const [installmentMonths, setInstallmentMonths] = useState(1);
  const [installmentPlans, setInstallmentPlans] = useState([]);

  // Toplam tutar değişince taksit planlarını getir (300ms debounce + AbortController)
  useEffect(() => {
    const total = Number(finalTotalPrice) || 0;
    if (total <= 0) return;

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const response = await fetch("/api/payments/installments", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ totalPrice: total }),
          signal: controller.signal
        });
        const data = await response.json();
        if (data.success) {
          setInstallmentPlans(data.data || []);
        }
      } catch (err) {
        if (err.name !== "AbortError") {
          setInstallmentPlans([]);
        }
      }
    }, 300);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [finalTotalPrice]);

  if (!isOpen) return null;

  // Quick sandbox test cards
  const sandboxTestCards = [
    {
      name: "Mastercard Test",
      number: "5890040000000016",
      month: "12",
      year: "2028",
      cvc: "123",
      brand: "MasterCard"
    },
    {
      name: "Visa Test",
      number: "4543600000000009",
      month: "12",
      year: "2028",
      cvc: "123",
      brand: "Visa"
    },
    {
      name: "Troy Test",
      number: "9792000000000001",
      month: "12",
      year: "2028",
      cvc: "123",
      brand: "Troy"
    }
  ];

  const handleFillTestCard = (card) => {
    setCardNumber(card.number.replace(/(\d{4})(?=\d)/g, "$1 "));
    setExpireMonth(card.month);
    setExpireYear(card.year);
    setCvc(card.cvc);
    setError("");
  };

  const handleCardNumberChange = (e) => {
    const raw = e.target.value.replace(/\D/g, "").slice(0, 16);
    const formatted = raw.replace(/(\d{4})(?=\d)/g, "$1 ");
    setCardNumber(formatted);
    if (error) setError("");
  };

  const handleSubmitPayment = async (e) => {
    e.preventDefault();
    const cleanNumber = cardNumber.replace(/\s+/g, "");

    if (!cardHolderName.trim()) {
      setError("Lütfen kart üzerindeki adı ve soyadı giriniz.");
      return;
    }
    if (cleanNumber.length < 15) {
      setError("Lütfen geçerli bir kart numarası giriniz.");
      return;
    }
    if (!cvc || cvc.length < 3) {
      setError("Lütfen 3 haneli güvenlik kodunu (CVC) giriniz.");
      return;
    }

    setIsLoading(true);
    setError("");

    try {
      const response = await fetch("/api/payments/iyzico/direct-pay", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          listingId: listing.id,
          guestId: currentUser?.id || "usr_guest_01",
          checkIn,
          checkOut,
          numGuests: guests,
          couponCode: appliedCoupon?.code || null,
          installmentMonths,
          card: {
            cardHolderName: cardHolderName.trim(),
            cardNumber: cleanNumber,
            expireMonth,
            expireYear,
            cvc
          },
          buyer: {
            id: currentUser?.id || "usr_guest_01",
            name: cardHolderName.trim(),
            email: currentUser?.email || "guest@fatsa.bel.tr",
            phone: "+905350000000"
          }
        })
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        throw new Error(data.error || "Ödeme iyzico tarafından reddedildi.");
      }

      onPaymentSuccess({
        booking: data.booking,
        payment: data.payment
      });
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-200">
      <div className="bg-white border border-charcoal-border rounded-3xl max-w-lg w-full shadow-2xl overflow-hidden my-8 flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 bg-gradient-to-r from-charcoal-bg via-white to-charcoal-bg border-b border-charcoal-border flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-blue-600/10 text-blue-600 flex items-center justify-center font-black text-sm tracking-tight border border-blue-200">
              iyzi
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h3 className="font-extrabold text-charcoal text-base">Güvenli Ödeme</h3>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
                  Sandbox Aktif
                </span>
              </div>
              <p className="text-[11px] text-charcoal-light font-medium flex items-center gap-1">
                <ShieldCheck className="w-3 h-3 text-emerald-600" />
                256-Bit SSL Şifreli iyzico Gateway
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-1.5 text-charcoal-light hover:text-charcoal hover:bg-charcoal-bg rounded-full transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 flex flex-col gap-5 overflow-y-auto max-h-[80vh]">
          {/* Reservation Summary Box */}
          <div className="bg-charcoal-bg/70 border border-charcoal-border rounded-2xl p-4 flex flex-col gap-2.5">
            <div className="flex items-start justify-between">
              <div>
                <h4 className="font-bold text-sm text-charcoal">{listing.title}</h4>
                <p className="text-xs text-charcoal-light flex items-center gap-1 mt-0.5">
                  <Calendar className="w-3 h-3 text-airbnb" />
                  {checkIn} → {checkOut} ({priceMath?.nights} gece, {guests} misafir)
                </p>
              </div>
              <div className="text-right">
                <span className="text-xs text-charcoal-light">Ödenecek</span>
                <div className="font-extrabold text-lg text-airbnb">
                  ₺{finalTotalPrice.toLocaleString("tr-TR")}
                </div>
              </div>
            </div>

            {appliedCoupon && (
              <div className="flex items-center justify-between text-xs font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2.5 py-1.5 rounded-xl">
                <span className="flex items-center gap-1">
                  <Tag className="w-3.5 h-3.5" />
                  Kupon İndirimi ({appliedCoupon.code})
                </span>
                <span>-₺{currentDiscountAmount.toLocaleString("tr-TR")}</span>
              </div>
            )}
          </div>

          {/* Installment Plan Selector */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-charcoal flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-airbnb" />
                Taksit Seçeneği
              </label>
              <span className="text-[10px] text-charcoal-light">Taksitli ödeme</span>
            </div>
            {installmentPlans.some((p) => p.feeRate > 0) ? (
              <div className="flex gap-2 overflow-x-auto pb-1">
                {installmentPlans.map((plan) => (
                  <button
                    key={plan.months}
                    type="button"
                    onClick={() => setInstallmentMonths(plan.months)}
                    className={`shrink-0 min-h-[44px] px-3.5 py-2 rounded-xl border transition-all text-left flex flex-col justify-center gap-0.5 ${
                      installmentMonths === plan.months
                        ? "bg-airbnb text-white border-airbnb shadow-md"
                        : "bg-white border-charcoal-border hover:border-airbnb hover:shadow-sm"
                    }`}
                  >
                    <span className="flex items-center gap-1.5 text-[11px] font-extrabold">
                      {plan.label}
                      {plan.badge && (
                        <span className={`text-[8px] font-bold px-1.5 py-0.5 rounded-full ${
                          installmentMonths === plan.months
                            ? "bg-white/20 text-white"
                            : "bg-amber-100 text-amber-700"
                        }`}>
                          {plan.badge}
                        </span>
                      )}
                    </span>
                    <span className={`font-mono tabular-nums text-[11px] ${
                      installmentMonths === plan.months ? "text-white/90" : "text-charcoal-light"
                    }`}>
                      ₺{plan.monthlyPayment.toLocaleString("tr-TR")}/ay
                    </span>
                  </button>
                ))}
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setInstallmentMonths(1)}
                className={`min-h-[44px] px-4 py-2 rounded-xl border transition-all text-left ${
                  installmentMonths === 1
                    ? "bg-airbnb text-white border-airbnb shadow-md"
                    : "bg-white border-charcoal-border hover:border-airbnb"
                }`}
              >
                <span className="flex items-center gap-1.5 text-xs font-extrabold">
                  <CreditCard className="w-3.5 h-3.5" />
                  Tek Çekim
                </span>
              </button>
            )}
          </div>

          {/* Sandbox Test Cards Preset Selector */}
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <label className="text-xs font-bold text-charcoal flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                Hızlı Test Kartı Seç (Sandbox)
              </label>
              <span className="text-[10px] text-charcoal-light">1 Tıkla Doldur</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {sandboxTestCards.map((card) => (
                <button
                  key={card.name}
                  type="button"
                  onClick={() => handleFillTestCard(card)}
                  className="px-2.5 py-2 rounded-xl border border-charcoal-border hover:border-airbnb hover:bg-rose-50/40 transition-all text-left flex flex-col gap-0.5 group"
                >
                  <span className="text-[11px] font-bold text-charcoal group-hover:text-airbnb">
                    {card.brand}
                  </span>
                  <span className="text-[10px] text-charcoal-light font-mono">
                    •••• {card.number.slice(-4)}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Payment Form */}
          <form onSubmit={handleSubmitPayment} className="flex flex-col gap-4">
            {/* Card Holder Name */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-extrabold text-charcoal uppercase tracking-wider">
                KART ÜZERİNDEKİ İSİM
              </label>
              <input 
                type="text"
                value={cardHolderName}
                onChange={(e) => setCardHolderName(e.target.value)}
                placeholder="Örn: Ahmet Yılmaz"
                className="w-full px-3.5 py-2.5 text-xs font-semibold text-charcoal bg-white border border-charcoal-border rounded-xl outline-none focus:border-airbnb transition-colors"
                required
              />
            </div>

            {/* Card Number */}
            <div className="flex flex-col gap-1">
              <label className="text-[11px] font-extrabold text-charcoal uppercase tracking-wider">
                KART NUMARASI
              </label>
              <div className="relative">
                <input 
                  type="text"
                  value={cardNumber}
                  onChange={handleCardNumberChange}
                  placeholder="5890 0400 0000 0016"
                  maxLength={19}
                  className="w-full pl-3.5 pr-10 py-2.5 text-xs font-mono font-semibold text-charcoal bg-white border border-charcoal-border rounded-xl outline-none focus:border-airbnb transition-colors"
                  required
                />
                <CreditCard className="w-4 h-4 text-charcoal-light absolute right-3.5 top-3" />
              </div>
            </div>

            {/* Expiry & CVC Grid */}
            <div className="grid grid-cols-2 gap-3">
              <div className="flex flex-col gap-1">
                <label className="text-[11px] font-extrabold text-charcoal uppercase tracking-wider">
                  SON KULLANMA
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <select 
                    value={expireMonth}
                    onChange={(e) => setExpireMonth(e.target.value)}
                    className="px-2 py-2.5 text-xs font-bold text-charcoal bg-white border border-charcoal-border rounded-xl outline-none focus:border-airbnb cursor-pointer"
                  >
                    {Array.from({ length: 12 }, (_, i) => {
                      const m = (i + 1).toString().padStart(2, "0");
                      return <option key={m} value={m}>{m}</option>;
                    })}
                  </select>
                  <select 
                    value={expireYear}
                    onChange={(e) => setExpireYear(e.target.value)}
                    className="px-2 py-2.5 text-xs font-bold text-charcoal bg-white border border-charcoal-border rounded-xl outline-none focus:border-airbnb cursor-pointer"
                  >
                    {[2026, 2027, 2028, 2029, 2030, 2031].map((y) => (
                      <option key={y} value={String(y)}>{y}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex flex-col gap-1">
                <label className="text-[11px] font-extrabold text-charcoal uppercase tracking-wider">
                  CVC / GÜVENLİK
                </label>
                <div className="relative">
                  <input 
                    type="password"
                    maxLength={4}
                    value={cvc}
                    onChange={(e) => setCvc(e.target.value.replace(/\D/g, ""))}
                    placeholder="123"
                    className="w-full px-3.5 py-2.5 text-xs font-mono font-bold text-charcoal bg-white border border-charcoal-border rounded-xl outline-none focus:border-airbnb transition-colors"
                    required
                  />
                  <Lock className="w-3.5 h-3.5 text-charcoal-light absolute right-3 top-3.5" />
                </div>
              </div>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs font-medium rounded-xl flex items-start gap-2 animate-in fade-in">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Security Notice */}
            <div className="flex items-center justify-center gap-1.5 text-[11px] text-charcoal-light pt-1">
              <Lock className="w-3.5 h-3.5 text-emerald-600" />
              <span>Ödemeniz iyzico altyapısıyla 3D Secure güvencesinde işlenir.</span>
            </div>

            {/* Action Buttons */}
            <div className="flex items-center gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={isLoading}
                className="flex-1 py-3 text-xs font-bold text-charcoal hover:bg-charcoal-bg rounded-xl border border-charcoal-border transition-colors"
              >
                Vazgeç
              </button>
              <button
                type="submit"
                disabled={isLoading || !cardNumber}
                className="flex-2 py-3 px-6 bg-airbnb hover:bg-airbnb-dark text-white text-sm font-extrabold rounded-xl shadow-lg hover:shadow-xl active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>iyzico İşleniyor...</span>
                  </>
                ) : (
                  <>
                    <ShieldCheck className="w-4 h-4" />
                    <span>₺{finalTotalPrice.toLocaleString("tr-TR")} Güvenli Öde</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
