import React from "react";
import { Clock, Users, MapPin, Star, ArrowRight } from "lucide-react";
import { formatCurrency } from "../lib/currencyEngine.js";

export function ExperienceCard({ experience, currency = "TRY", onSelect }) {
  const durationHours = Math.round(experience.duration / 60 * 10) / 10;
  const durationLabel = experience.duration >= 60
    ? `${durationHours} saat`
    : `${experience.duration} dk`;

  return (
    <div
      onClick={() => onSelect?.(experience)}
      className="group bg-white dark:bg-white/5 border border-charcoal-border/70 dark:border-white/10 rounded-3xl overflow-hidden shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all cursor-pointer"
     role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } }}>
      <div className="relative aspect-[4/3] overflow-hidden bg-charcoal-bg">
        <img
          src={experience.images?.[0]}
          alt={experience.title}
          loading="lazy"
          srcSet={`${experience.images?.[0]}?w=300 300w, ${experience.images?.[0]}?w=600 600w, ${experience.images?.[0]}?w=1200 1200w`}
          sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
          className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
        />
        <div className="absolute top-3 left-3 bg-white/95 backdrop-blur-md text-charcoal px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold shadow-xs border border-charcoal-border/50">
          {experience.category}
        </div>
        {experience.avgRating > 0 && (
          <div className="absolute bottom-3 right-3 bg-charcoal-dark/80 backdrop-blur-md text-white px-2 py-1 rounded-lg text-[11px] font-bold flex items-center gap-1">
            <Star className="w-3 h-3 fill-amber-400 text-amber-400" />
            <span>{experience.avgRating.toFixed(1)}</span>
            <span className="text-white/50 font-medium">({experience.reviewCount})</span>
          </div>
        )}
      </div>

      <div className="p-4 flex flex-col gap-2.5">
        <h3 className="font-extrabold text-sm text-charcoal dark:text-white leading-snug line-clamp-2 group-hover:text-airbnb transition-colors">
          {experience.title}
        </h3>

        <div className="flex items-center gap-3 text-[11px] text-charcoal-light dark:text-gray-600 font-medium">
          <span className="flex items-center gap-1">
            <Clock className="w-3.5 h-3.5" />
            {durationLabel}
          </span>
          <span className="flex items-center gap-1">
            <Users className="w-3.5 h-3.5" />
            {experience.maxParticipants} kişi
          </span>
          <span className="flex items-center gap-1">
            <MapPin className="w-3.5 h-3.5" />
            {experience.city}
          </span>
        </div>

        <div className="flex items-end justify-between pt-1 mt-auto">
          <div>
            <span className="text-base font-black font-mono text-charcoal dark:text-white">
              {formatCurrency(experience.pricePerPerson, currency)}
            </span>
            <span className="text-[10px] text-charcoal-light dark:text-gray-600 font-medium"> / kişi</span>
          </div>
          <span className="flex items-center gap-1 text-airbnb text-xs font-bold opacity-0 group-hover:opacity-100 transition-opacity">
            İncele <ArrowRight className="w-3.5 h-3.5" />
          </span>
        </div>
      </div>
    </div>
  );
}