import React from "react";
import { ArrowUpDown } from "lucide-react";

export const SORT_OPTIONS = [
  { id: "recommended", label: "Önerilen" },
  { id: "price_asc", label: "Fiyat ↑" },
  { id: "price_desc", label: "Fiyat ↓" },
  { id: "rating_desc", label: "Puan ↓" }
];

export function SortBar({ sortOrder = "recommended", onSortChange }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="flex items-center gap-1.5 text-xs font-bold text-charcoal-light dark:text-gray-600 mr-1 shrink-0">
        <ArrowUpDown className="w-4 h-4 text-airbnb" />
        Sırala:
      </span>
      {SORT_OPTIONS.map((opt) => {
        const isSelected = sortOrder === opt.id;
        return (
          <button
            key={opt.id}
            onClick={() => onSortChange(opt.id)}
            className={`flex items-center gap-1.5 px-4 min-h-[44px] rounded-2xl transition-all whitespace-nowrap cursor-pointer select-none border text-xs font-bold ${
              isSelected
                ? "bg-charcoal text-white border-charcoal shadow-sm"
                : "bg-charcoal-bg/60 text-charcoal-light border-charcoal-border/50 hover:border-charcoal-border hover:bg-charcoal-bg hover:text-charcoal"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
