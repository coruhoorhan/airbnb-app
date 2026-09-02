import React, { useState } from "react";
import { Clock, Users, MapPin, Star, X, Check, CalendarDays, ChevronRight } from "lucide-react";
import { formatCurrency } from "../lib/currencyEngine.js";

const DATE_OPTIONS = [
  { label: "Bu Hafta Sonu", offset: 2 },
  { label: "Önümüzdeki Cumartesi", offset: 7 },
  { label: "2 Hafta Sonra", offset: 14 },
  { label: "1 Ay Sonra", offset: 30 }
];

function nextDate(offsetDays) {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toISOString().slice(0, 10);
}

export function ExperienceDetailModal({ experience, currency = "TRY", currentUser, onClose, onReserve }) {
  const [participants, setParticipants] = useState(2);
  const [dateOffset, setDateOffset] = useState(2);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  if (!experience) return null;

  const totalPrice = experience.pricePerPerson * participants;
  const durationLabel = experience.duration >= 60
    ? `${Math.round(experience.duration / 60 * 10) / 10} saat`
    : `${experience.duration} dk`;

  const handleReserve = async () => {
    if (!currentUser) return;
    setIsSubmitting(true);
    setError("");
    try {
      const res = await fetch("/api/experiences/reserve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          experienceId: experience.id,
          userId: currentUser.id,
          participants,
          reservationDate: nextDate(dateOffset)
        })
      });
      const data = await res.json();
      if (!data.success) {
        setError(data.error || "Rezervasyon oluşturulamadı.");
        return;
      }
      setResult(data.data);
      onReserve?.(data.data);
    } catch (e) {
      setError("Bir hata oluştu. Lütfen tekrar deneyin.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-white dark:bg-[#16191E] rounded-3xl shadow-2xl w-full max-w-3xl max-h-[90dvh] overflow-y-auto animate-in fade-in zoom-in-95 duration-200">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-10 w-9 h-9 rounded-full bg-white/90 backdrop-blur-md border border-charcoal-border/50 flex items-center justify-center shadow-md hover:scale-105 transition-transform cursor-pointer"
        >
          <X className="w-4 h-4 text-charcoal" />
        </button>

        {result ? (
          <div className="p-8 sm:p-12 text-center flex flex-col items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center">
              <Check className="w-8 h-8 text-emerald-600" />
            </div>
            <h2 className="text-2xl font-black font-display text-charcoal dark:text-white">Rezervasyonunuz Alındı!</h2>
            <p className="text-sm text-charcoal-light dark:text-gray-400 max-w-sm font-medium">
              <span className="font-bold text-charcoal dark:text-white">{experience.title}</span> deneyimi için
              {participants} kişilik rezervasyonunuz oluşturuldu.
            </p>
            <div className="flex items-center gap-2 text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-xl px-4 py-2.5">
              <CalendarDays className="w-4 h-4" />
              <span>{nextDate(dateOffset)}</span>
              <ChevronRight className="w-3.5 h-3.5" />
              <span className="font-mono">{formatCurrency(totalPrice, currency)}</span>
            </div>
            <p className="text-[11px] text-charcoal-light font-mono">Rezervasyon No: <span className="font-bold">{result.id}</span></p>
            <button
              onClick={onClose}
              className="mt-2 px-6 py-3 bg-airbnb hover:bg-airbnb-dark text-white rounded-2xl font-bold text-xs transition-colors cursor-pointer"
            >
              Kapat
            </button>
          </div>
        ) : (
          <>
            {/* Hero Image */}
            <div className="relative h-56 sm:h-72 overflow-hidden">
              <img src={experience.images?.[0]} alt={experience.title} className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-gradient-to-t from-black/70 via-black/10 to-transparent" />
              <div className="absolute bottom-4 left-5 right-5 flex items-end justify-between gap-4">
                <div>
                  <span className="inline-block bg-white/95 backdrop-blur-md text-charcoal px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold shadow-xs mb-2">
                    {experience.category}
                  </span>
                  <h2 className="text-xl sm:text-2xl font-black font-display text-white tracking-tight">{experience.title}</h2>
                </div>
                {experience.avgRating > 0 && (
                  <span className="flex items-center gap-1 bg-black/50 backdrop-blur-md text-white px-2.5 py-1 rounded-lg text-xs font-bold shrink-0">
                    <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" />
                    {experience.avgRating.toFixed(1)}
                    <span className="text-white/50 font-medium">({experience.reviewCount})</span>
                  </span>
                )}
              </div>
            </div>

            <div className="p-5 sm:p-7 flex flex-col gap-5">
              {/* Meta Row */}
              <div className="flex flex-wrap items-center gap-2.5 text-[11px] font-semibold text-charcoal-light dark:text-gray-400">
                <span className="flex items-center gap-1.5 bg-charcoal-bg dark:bg-white/5 rounded-full px-3 py-1.5">
                  <Clock className="w-3.5 h-3.5" /> {durationLabel}
                </span>
                <span className="flex items-center gap-1.5 bg-charcoal-bg dark:bg-white/5 rounded-full px-3 py-1.5">
                  <Users className="w-3.5 h-3.5" /> {experience.maxParticipants} kişilik
                </span>
                <span className="flex items-center gap-1.5 bg-charcoal-bg dark:bg-white/5 rounded-full px-3 py-1.5">
                  <MapPin className="w-3.5 h-3.5" /> {experience.location}
                </span>
              </div>

              {/* Description */}
              <p className="text-sm text-charcoal dark:text-gray-300 leading-relaxed font-medium">{experience.description}</p>

              {/* Included */}
              <div>
                <h4 className="text-xs font-black uppercase tracking-wider text-charcoal dark:text-white mb-2.5">Neler Dahil?</h4>
                <div className="flex flex-wrap gap-2">
                  {(experience.includes || []).map((item) => (
                    <span key={item} className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 border border-emerald-100 dark:border-emerald-500/20 rounded-full px-3 py-1.5">
                      <Check className="w-3 h-3" /> {item}
                    </span>
                  ))}
                </div>
              </div>

              {/* Gallery */}
              {experience.images?.length > 1 && (
                <div className="flex gap-2.5 overflow-x-auto pb-1 -mx-1 px-1">
                  {experience.images.slice(1).map((img, i) => (
                    <img key={i} src={img} alt="" className="w-28 h-20 object-cover rounded-xl shrink-0 border border-charcoal-border/50" />
                  ))}
                </div>
              )}

              {/* Reservation Panel */}
              <div className="border-t border-charcoal-border/60 dark:border-white/10 pt-5">
                <h4 className="text-xs font-black uppercase tracking-wider text-charcoal dark:text-white mb-3">Rezervasyon Yap</h4>
                {error && (
                  <p className="text-[11px] font-bold text-red-600 bg-red-50 dark:bg-red-500/10 border border-red-100 dark:border-red-500/20 rounded-xl px-3 py-2 mb-3">
                    {error}
                  </p>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="text-[11px] font-bold text-charcoal-light dark:text-gray-400 block mb-1.5">Tarih</label>
                    <div className="flex flex-wrap gap-1.5">
                      {DATE_OPTIONS.map((opt) => (
                        <button
                          key={opt.label}
                          onClick={() => setDateOffset(opt.offset)}
                          className={`px-3 py-2 rounded-xl text-[11px] font-bold border transition-colors cursor-pointer ${
                            dateOffset === opt.offset
                              ? "bg-charcoal text-white border-charcoal dark:bg-white dark:text-charcoal dark:border-white"
                              : "bg-white dark:bg-white/5 border-charcoal-border dark:border-white/10 text-charcoal dark:text-white hover:border-charcoal"
                          }`}
                        >
                          {opt.label}
                        </button>
                      ))}
                    </div>
                    <p className="text-[11px] font-mono text-charcoal-light mt-1.5">{nextDate(dateOffset)}</p>
                  </div>

                  <div>
                    <label className="text-[11px] font-bold text-charcoal-light dark:text-gray-400 block mb-1.5">
                      Katılımcı Sayısı ({participants})
                    </label>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => setParticipants((p) => Math.max(1, p - 1))}
                        className="w-9 h-9 rounded-xl border border-charcoal-border dark:border-white/10 flex items-center justify-center text-lg font-bold text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 transition-colors cursor-pointer"
                      >
                        −
                      </button>
                      <span className="w-10 text-center font-mono font-black text-lg text-charcoal dark:text-white">{participants}</span>
                      <button
                        onClick={() => setParticipants((p) => Math.min(experience.maxParticipants, p + 1))}
                        className="w-9 h-9 rounded-xl border border-charcoal-border dark:border-white/10 flex items-center justify-center text-lg font-bold text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 transition-colors cursor-pointer"
                      >
                        +
                      </button>
                      <span className="text-[11px] text-charcoal-light ml-1">/ {experience.maxParticipants} kişi</span>
                    </div>
                  </div>
                </div>

                <button
                  onClick={handleReserve}
                  disabled={isSubmitting || !currentUser}
                  className="mt-5 w-full py-4 bg-airbnb hover:bg-airbnb-dark disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-2xl font-black text-sm transition-colors flex items-center justify-center gap-2 cursor-pointer"
                >
                  {isSubmitting ? (
                    <span className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  ) : (
                    <>
                      <span>
                        {currentUser
                          ? `Rezervasyonu Onayla · ${formatCurrency(totalPrice, currency)}`
                          : "Giriş Yapmanız Gerekiyor"}
                      </span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}