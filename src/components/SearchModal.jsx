import React, { useState } from "react";
import { X, Search, MapPin, Calendar, Users } from "lucide-react";

export function SearchModal({ isOpen, onClose, onSearch }) {
  const [destination, setDestination] = useState("");
  const [category, setCategory] = useState("all");
  const [minPrice, setMinPrice] = useState(0);
  const [maxPrice, setMaxPrice] = useState(10000);
  const [guests, setGuests] = useState(1);
  const [lastMinute, setLastMinute] = useState(false);

  if (!isOpen) return null;

  const handleApplySearch = () => {
    onSearch({
      destination,
      category,
      minPrice,
      maxPrice,
      guests,
      lastMinute
    });
    onClose();
  };

  const handleClear = () => {
    setDestination("");
    setCategory("all");
    setMinPrice(0);
    setMaxPrice(10000);
    setGuests(1);
    setLastMinute(false);
    onSearch({ destination: "", category: "all", minPrice: 0, maxPrice: 10000, guests: 1, lastMinute: false });
    onClose();
  };


  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white w-full max-w-lg rounded-3xl p-6 shadow-2xl flex flex-col gap-6 relative animate-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between border-b border-charcoal-border/50 pb-4">
          <h3 className="text-lg font-bold text-charcoal">Filtreler ve Arama</h3>
          <button aria-label="X" onClick={onClose} className="p-2 rounded-full hover:bg-charcoal-bg"> <X /> </button>
        </div>

        <div className="flex flex-col gap-4">
          {/* Destination */}
          <div>
            <label className="block text-xs font-bold text-charcoal uppercase tracking-wider mb-1.5">Nereye?</label>
            <div className="flex items-center gap-2 border border-charcoal-border rounded-xl px-3 py-2.5 bg-charcoal-bg/30">
              <MapPin className="w-4 h-4 text-airbnb" />
              <input 
                type="text"
                placeholder="Şehir veya lokasyon arayın (Bodrum, Kaş, Kapadokya...)"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                className="w-full text-sm font-semibold text-charcoal bg-transparent outline-none"
              />
            </div>
          </div>

          {/* Price Range */}
          <div>
            <label className="block text-xs font-bold text-charcoal uppercase tracking-wider mb-1.5">
              Fiyat Aralığı (Gecelik ₺)
            </label>
            <div className="flex items-center gap-3">
              <input 
                type="number"
                placeholder="Min ₺"
                value={minPrice}
                onChange={(e) => setMinPrice(Number(e.target.value))}
                className="w-1/2 border border-charcoal-border rounded-xl px-3 py-2 text-sm font-semibold text-charcoal outline-none"
              />
              <span className="text-charcoal-light font-bold">-</span>
              <input 
                type="number"
                placeholder="Max ₺"
                value={maxPrice}
                onChange={(e) => setMaxPrice(Number(e.target.value))}
                className="w-1/2 border border-charcoal-border rounded-xl px-3 py-2 text-sm font-semibold text-charcoal outline-none"
              />
            </div>
          </div>

          {/* Guests */}
          <div>
            <label className="block text-xs font-bold text-charcoal uppercase tracking-wider mb-1.5">Misafir Sayısı</label>
            <div className="flex items-center gap-2 border border-charcoal-border rounded-xl px-3 py-2 bg-charcoal-bg/30">
              <Users className="w-4 h-4 text-charcoal-light" />
              <select 
                value={guests}
                onChange={(e) => setGuests(Number(e.target.value))}
                className="w-full text-sm font-semibold text-charcoal bg-transparent outline-none cursor-pointer"
              >
                {[1, 2, 3, 4, 5, 6, 8, 10].map((num) => (
                  <option key={num} value={num}>{num}+ Misafir</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-2 border border-charcoal-border rounded-xl px-3 py-2 bg-charcoal-bg/30">
              <Users className="w-4 h-4 text-charcoal-light" />
              <select 
                value={guests}
                onChange={(e) => setGuests(Number(e.target.value))}
                className="w-full text-sm font-semibold text-charcoal bg-transparent outline-none cursor-pointer"
              >
                {[1, 2, 3, 4, 5, 6, 8, 10].map((num) => (
                  <option key={num} value={num}>{num}+ Misafir</option>
                ))}
              </select>
            </div>
          </div>

          {/* Last Minute Toggle */}
          <div>
            <label className="flex items-center gap-3 cursor-pointer">
              <div className="relative">
                <input
                  type="checkbox"
                  checked={lastMinute}
                  onChange={(e) => setLastMinute(e.target.checked)}
                  className="sr-only"
                />
                <div className={`w-10 h-6 rounded-full transition-colors ${lastMinute ? "bg-airbnb" : "bg-charcoal-border"}`}>
                  <div className={`w-4 h-4 bg-white rounded-full shadow-xs absolute top-1 transition-transform ${lastMinute ? "translate-x-5" : "translate-x-1"}`} />
                </div>
              </div>
              <span className="text-xs font-bold text-charcoal">Sadece Son Dakika Fırsatları</span>
            </label>
          </div>
        </div>

        <div className="flex items-center justify-between pt-4 border-t border-charcoal-border/50">
          <button 
            onClick={handleClear}
            className="text-sm font-bold text-charcoal underline hover:text-black"
          >
            Filtreleri Temizle
          </button>
          <button 
            onClick={handleApplySearch}
            className="px-6 py-3 bg-charcoal text-white rounded-xl font-bold text-sm hover:bg-black transition-colors flex items-center gap-2"
          >
            <Search className="w-4 h-4" />
            <span>Sonuçları Göster</span>
          </button>
        </div>
      </div>
    </div>
  );
}
