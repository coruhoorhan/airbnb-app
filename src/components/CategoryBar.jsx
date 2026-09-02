import React from "react";
import { Sparkles, Waves, Castle, TreePine, Home, Compass, Building2, Flame, Anchor } from "lucide-react";

export const CATEGORIES = [
  { id: "all", label: "Tüm Kıyılar", icon: Sparkles },
  { id: "Lüks Villa", label: "Kıyı Yalıları", icon: Waves },
  { id: "Plaj", label: "Sahil Evleri", icon: Anchor },
  { id: "Tarihi Evler", label: "Tarihi Konaklar", icon: Building2 },
  { id: "Kulübe", label: "Dağ Kulübesi", icon: TreePine },
  { id: "Göl Kenarı", label: "Göl & Nehir", icon: Compass },
  { id: "Tiny House", label: "Tiny House", icon: Home },
  { id: "Popüler", label: "Trendler", icon: Flame }
];

export function CategoryBar({ selectedCategory, onSelectCategory }) {
  return (
    <div className="bg-white/80 backdrop-blur-xs border-b border-charcoal-border/40 py-3 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center justify-between gap-4">
        {/* Scrollable Coastal Category Bar */}
        <div className="flex items-center gap-4 sm:gap-6 overflow-x-auto no-scrollbar py-1 flex-1">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isSelected = selectedCategory === cat.id;
            return (
              <button
                key={cat.id}
                onClick={() => onSelectCategory(cat.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl transition-all group whitespace-nowrap cursor-pointer select-none border ${
                  isSelected
                    ? "bg-charcoal text-white border-charcoal shadow-sm font-bold scale-102"
                    : "bg-charcoal-bg/60 text-charcoal-light border-charcoal-border/50 hover:border-charcoal-border hover:bg-charcoal-bg font-medium hover:text-charcoal"
                }`}
              >
                <Icon className={`w-4 h-4 transition-transform group-hover:scale-110 ${isSelected ? "text-amber-400" : "text-charcoal-light"}`} />
                <span className="text-xs tracking-tight">{cat.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
