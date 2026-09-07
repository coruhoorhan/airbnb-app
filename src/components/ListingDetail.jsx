import React, { useState, useEffect } from "react";
import { Star, Heart, Bell, BellOff, ArrowLeft, Shield, Award, MapPin, Wifi, Waves, Utensils, Wind, Flame, Car, MessageCircle, Send, CheckCircle2, Clock, TrendingDown, Share2 } from "lucide-react";
import { BookingWidget } from "./BookingWidget.jsx";
import { PhotoLightbox } from "./PhotoLightbox.jsx";
import { formatCurrency } from "../lib/currencyEngine.js";

const AMENITY_ICONS = {
  wifi: { label: "Hızlı Wi-Fi", icon: Wifi },
  pool: { label: "Özel Yüzme Havuzu", icon: Waves },
  kitchen: { label: "Tam Donanımlı Mutfak", icon: Utensils },
  ac: { label: "Klima", icon: Wind },
  fireplace: { label: "Şömine", icon: Flame },
  parking: { label: "Ücretsiz Otopark", icon: Car }
};

export function ListingDetail({ 
  listing, 
  onBack, 
  isFavorite, 
  onToggleFavorite, 
  bookings = [], 
  availability = [], 
  onBook, 
  currentUser, 
  onOpenChat,
  reviews = [],
  onAddReview,
  currency = "TRY",
  currentUserId = "usr_guest_01"
}) {
  const [newComment, setNewComment] = useState("");
  const [newRating, setNewRating] = useState(5);
  const [isWatched, setIsWatched] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);

  useEffect(() => {
    fetch(`/api/price-watches?userId=${currentUserId}`)
      .then(r => r.json())
      .then(d => {
        if (d.success && d.data) {
          setIsWatched(d.data.some(w => w.listingId === listing.id));
        }
      })
      .catch(() => {});
  }, [currentUserId, listing.id]);

  const handlePriceWatch = async () => {
    if (isWatched) {
      try {
        await fetch(`/api/price-watches/${listing.id}?userId=${currentUserId}`, { method: "DELETE" });
      } catch {/* ignore */}
      setIsWatched(false);
    } else {
      try {
        await fetch("/api/price-watches", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userId: currentUserId, listingId: listing.id })
        });
      } catch {/* ignore */}
      setIsWatched(true);
    }
  };

  const effectivePrice = listing.lastMinuteDiscount > 0 && listing.lastMinuteOriginalPrice
    ? Math.round(listing.lastMinuteOriginalPrice * (1 - listing.lastMinuteDiscount / 100))
    : listing.pricePerNight;

  const savings = listing.lastMinuteDiscount > 0 && listing.lastMinuteOriginalPrice
    ? listing.lastMinuteOriginalPrice - effectivePrice
    : 0;


  const images = listing.images && listing.images.length > 0 ? listing.images : [];
  const primaryImage = images[0] || "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=1200&q=80";
  const subImages = images.slice(1, 5);

  const listingReviews = reviews.filter((r) => r.listingId === listing.id);

  const handleReviewSubmit = (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    onAddReview({
      listingId: listing.id,
      reviewerId: currentUser.id,
      reviewerName: currentUser.name,
      rating: Number(newRating),
      comment: newComment.trim(),
      createdAt: Date.now()
    });
    setNewComment("");
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 flex flex-col gap-6 animate-in fade-in duration-300">
      {/* Header Action Bar */}
      <div className="flex items-center justify-between">
        <button 
          onClick={onBack}
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-full hover:bg-charcoal-bg dark:hover:bg-white/10 text-xs font-bold text-charcoal dark:text-white border border-charcoal-border/70 dark:border-white/10 transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Tüm İlanlara Dön</span>
        </button>

        <div className="flex items-center gap-3">
          <button
            onClick={handlePriceWatch}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-full hover:bg-charcoal-bg dark:hover:bg-white/10 text-xs font-bold text-charcoal dark:text-white border border-charcoal-border/70 dark:border-white/10 transition-colors cursor-pointer"
          >
            {isWatched ? (
              <BellOff className="w-4 h-4 text-amber-500" />
            ) : (
              <Bell className="w-4 h-4 text-charcoal" />
            )}
            <span>{isWatched ? "Fiyat Takibi Aktif" : "Fiyat Takibi"}</span>
          </button>
          <button 
            onClick={() => onToggleFavorite(listing.id)}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-full hover:bg-charcoal-bg dark:hover:bg-white/10 text-xs font-bold text-charcoal dark:text-white border border-charcoal-border/70 dark:border-white/10 transition-colors cursor-pointer"
          >
            <Heart className={`w-4 h-4 ${isFavorite ? "text-airbnb fill-airbnb" : "text-charcoal"}`} />
            <span>{isFavorite ? "Kaydedildi" : "Kaydet"}</span>
          </button>
          <button
            onClick={() => {
              const url = window.location.origin + "/?listing=" + listing.id;
              const text = `${listing.title} — Fatsa Escapes'te ${formatCurrency(listing.pricePerNight, currency)}/gece`;
              if (navigator.share) {
                navigator.share({ title: listing.title, text, url }).catch(() => {});
              } else {
                navigator.clipboard.writeText(url + "\n" + text).catch(() => {});
                alert("Link kopyalandı!");
              }
            }}
            className="flex items-center gap-2 px-3.5 py-1.5 rounded-full hover:bg-charcoal-bg dark:hover:bg-white/10 text-xs font-bold text-charcoal dark:text-white border border-charcoal-border/70 dark:border-white/10 transition-colors cursor-pointer"
          >
            <Share2 className="w-4 h-4 text-charcoal" />
            <span>Paylaş</span>
          </button>
        </div>
      </div>

      {/* Listing Title & Location Header */}
      <div>
        <h1 className="text-3xl sm:text-4xl font-display font-black text-charcoal dark:text-white tracking-tight">{listing.title}</h1>
        <div className="flex flex-wrap items-center gap-3 text-xs font-semibold text-charcoal dark:text-white mt-2">
          <div className="flex items-center gap-1 font-bold">
            <Star className="w-3.5 h-3.5 fill-charcoal text-charcoal" />
            <span>{listing.avgRating > 0 ? listing.avgRating.toFixed(2) : "Yeni"}</span>
            <span className="text-charcoal-light dark:text-gray-600 font-normal">({listing.reviewCount} yorum)</span>
          </div>
          <span>•</span>
          <div className="flex items-center gap-1 underline cursor-pointer">
            <MapPin className="w-3.5 h-3.5 text-airbnb" />
            <span>{listing.address}, {listing.city}, {listing.country}</span>
          </div>
        </div>
      </div>
        {/* Last-Minute Deal Banner */}
        {listing.lastMinuteDiscount > 0 && (
          <div className="mt-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-300 dark:border-amber-700 rounded-2xl p-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="bg-amber-500 text-white p-2 rounded-xl">
                <Clock className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="bg-amber-500 text-white px-2.5 py-0.5 rounded-lg text-[11px] font-mono font-bold">SON DAKİKA FIRSATI</span>
                  <span className="text-lg font-black font-mono text-amber-600 dark:text-amber-400">-%{listing.lastMinuteDiscount}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-sm text-charcoal-light dark:text-gray-600 line-through">{formatCurrency(listing.lastMinuteOriginalPrice, currency)}</span>
                  <span className="text-lg font-black text-amber-600 dark:text-amber-400">{formatCurrency(effectivePrice, currency)}</span>
                  <span className="text-[11px] text-charcoal-light">/gece</span>
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-bold text-sm">
                <TrendingDown className="w-4 h-4" />
                <span className="font-mono">-{formatCurrency(savings, currency)}</span>
              </div>
              <p className="text-[11px] text-charcoal-light dark:text-gray-600">Tasarruf</p>
            </div>
          </div>
        )}

      {/* 5-Photo Asymmetric Collage */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-2.5 rounded-3xl overflow-hidden aspect-video max-h-[480px]">
        <div className="md:col-span-2 h-full overflow-hidden bg-charcoal-bg">
          <img 
            src={primaryImage} 
            srcSet={`${primaryImage} 400w, ${primaryImage} 800w, ${primaryImage} 1200w`}
            sizes="(max-width: 768px) 100vw, 50vw"
            loading="lazy"
            alt="Ana Görsel" 
            className="w-full h-full object-cover hover:scale-105 transition-transform duration-500 cursor-pointer" 
            onClick={() => { setLightboxIndex(0); setLightboxOpen(true); }}
          />
        </div>
        <div className="hidden md:grid md:col-span-2 grid-cols-2 gap-2.5 h-full">
          {subImages.map((img, idx) => (
            <div key={idx} className="h-full overflow-hidden bg-charcoal-bg">
              <img 
                src={img} 
                srcSet={`${img} 400w, ${img} 800w, ${img} 1200w`}
                sizes="(max-width: 768px) 100vw, 25vw"
                loading="lazy"
                alt={`Detay ${idx + 1}`} 
                className="w-full h-full object-cover hover:scale-105 transition-transform duration-500 cursor-pointer" 
                onClick={() => { setLightboxIndex(idx + 1); setLightboxOpen(true); }}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Main Two-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12 mt-6">
        {/* Left 2 Columns */}
        <div className="lg:col-span-2 flex flex-col gap-8">
          {/* Host Overview */}
          <div className="flex items-center justify-between pb-6 border-b border-charcoal-border/70">
            <div>
              <h2 className="text-xl font-bold text-charcoal dark:text-white">
                {listing.propertyType} • Ev Sahibi: Zeynep Kaya
              </h2>
              <p className="text-xs text-charcoal-light dark:text-gray-600 mt-1 font-medium">
                {listing.maxGuests} misafir • {listing.bedrooms} yatak odası • {listing.beds} yatak • {listing.baths} banyo
              </p>
            </div>
            <img 
              src="https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=120&q=80" 
              alt="Host Avatar"
              className="w-14 h-14 rounded-full object-cover ring-2 ring-airbnb/20" 
            />
          </div>

          {/* Highlights */}
          <div className="flex flex-col gap-4 pb-6 border-b border-charcoal-border/70">
            <div className="flex items-start gap-4">
              <Award className="w-5 h-5 text-airbnb shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-sm text-charcoal dark:text-white">Süper Ev Sahibi</h3>
                <p className="text-xs text-charcoal-light dark:text-gray-600 font-normal">Deneyimli ve yüksek puanlı ev sahibi.</p>
              </div>
            </div>
            <div className="flex items-start gap-4">
              <Shield className="w-5 h-5 text-airbnb shrink-0 mt-0.5" />
              <div>
                <h3 className="font-bold text-sm text-charcoal dark:text-white">Ücretsiz İptal İmkanı</h3>
                <p className="text-xs text-charcoal-light dark:text-gray-600 font-normal">Girişe 24 saat kalana kadar %100 kesintisiz iade.</p>
              </div>
            </div>
          </div>

          {/* Description */}
          <div className="pb-6 border-b border-charcoal-border/70">
            <h3 className="text-lg font-bold text-charcoal dark:text-white mb-3">Bu mekan hakkında</h3>
            <p className="text-charcoal dark:text-white text-xs leading-relaxed whitespace-pre-line font-normal">
              {listing.description}
            </p>
          </div>

          {/* Amenities Grid */}
          <div className="pb-6 border-b border-charcoal-border/70">
            <h3 className="text-lg font-bold text-charcoal dark:text-white mb-4">Bu yerin sunduğu olanaklar</h3>
            <div className="grid grid-cols-2 gap-3.5">
              {listing.amenities?.map((amenityKey) => {
                const item = AMENITY_ICONS[amenityKey] || { label: amenityKey, icon: Star };
                const Icon = item.icon;
                return (
                  <div key={amenityKey} className="flex items-center gap-3 text-xs text-charcoal dark:text-white font-medium">
                    <Icon className="w-4 h-4 text-charcoal-light dark:text-gray-600" />
                    <span>{item.label}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Host Contact Trigger Button */}
          <div className="bg-charcoal-bg/70 dark:bg-white/5 rounded-2xl p-5 flex items-center justify-between border border-charcoal-border dark:border-white/10">
            <div>
              <h4 className="font-bold text-sm text-charcoal dark:text-white">Ev Sahibiyle İletişime Geçin</h4>
              <p className="text-xs text-charcoal-light dark:text-gray-600">Sorularınız ve özel talepleriniz için anında mesaj gönderin.</p>
            </div>
            <button
              onClick={() => onOpenChat(listing)}
              className="px-4 py-2.5 bg-white dark:bg-[#16191E] border border-charcoal-border dark:border-white/10 rounded-xl font-bold text-xs text-charcoal dark:text-white hover:bg-charcoal hover:text-white transition-colors flex items-center gap-2 cursor-pointer"
            >
              <MessageCircle className="w-4 h-4" />
              <span>Mesaj Gönder</span>
            </button>
          </div>

          {/* Reviews & Star Rating Distribution */}
          <div className="pt-4 flex flex-col gap-6">
            <div className="flex items-center gap-2">
              <Star className="w-5 h-5 fill-charcoal text-charcoal" />
              <h3 className="text-xl font-black text-charcoal dark:text-white">
                {listing.avgRating > 0 ? listing.avgRating.toFixed(2) : "5.0"} • {listing.reviewCount || listingReviews.length} Değerlendirme
              </h3>
            </div>

            {/* Rating Breakdown Bar */}
            <div className="grid grid-cols-2 gap-3 bg-charcoal-bg/50 dark:bg-white/5 p-4 rounded-2xl border border-charcoal-border/50 dark:border-white/10 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-medium text-charcoal dark:text-white">Temizlik</span>
                <span className="font-bold">4.9 ★</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium text-charcoal dark:text-white">Doğruluk</span>
                <span className="font-bold">5.0 ★</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium text-charcoal dark:text-white">İletişim</span>
                <span className="font-bold">5.0 ★</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium text-charcoal dark:text-white">Konum</span>
                <span className="font-bold">4.8 ★</span>
              </div>
            </div>

            {/* Review Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
              {listingReviews.map((r, i) => (
                <div key={i} className="p-4 rounded-2xl border border-charcoal-border dark:border-white/10 bg-white dark:bg-[#16191E] flex flex-col gap-2 shadow-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-xs text-charcoal dark:text-white">{r.reviewerName}</span>
                    <span className="text-xs font-bold text-airbnb">{"★".repeat(r.rating)}</span>
                  </div>
                  <p className="text-xs text-charcoal-light dark:text-gray-600 leading-relaxed">{r.comment}</p>
                </div>
              ))}
            </div>

            {/* Review Submit Form */}
            <form onSubmit={handleReviewSubmit} className="bg-charcoal-bg dark:bg-white/5 p-5 rounded-3xl border border-charcoal-border dark:border-white/10 flex flex-col gap-3">
              <h4 className="font-bold text-sm text-charcoal dark:text-white">Bu Mekanı Değerlendirin</h4>
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-charcoal dark:text-white">Puanınız:</span>
                <select 
                  value={newRating}
                  onChange={(e) => setNewRating(Number(e.target.value))}
                  className="bg-white dark:bg-[#16191E] border border-charcoal-border dark:border-white/10 rounded-lg px-2.5 py-1 text-xs font-bold text-charcoal dark:text-white"
                >
                  <option value="5">5 Yıldız (Mükemmel)</option>
                  <option value="4">4 Yıldız (Çok İyi)</option>
                  <option value="3">3 Yıldız (Ortalama)</option>
                  <option value="2">2 Yıldız (Kötü)</option>
                  <option value="1">1 Yıldız (Çok Kötü)</option>
                </select>
              </div>
              <textarea 
                rows={2}
                placeholder="Konaklama deneyiminiz nasıldı? Diğer misafirlerle paylaşın..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                className="w-full bg-white dark:bg-[#16191E] border border-charcoal-border dark:border-white/10 rounded-xl p-3 text-xs text-charcoal dark:text-white outline-none"
              />
              <button 
                type="submit"
                className="self-end px-5 py-2 bg-charcoal text-white rounded-xl text-xs font-bold hover:bg-black transition-colors cursor-pointer active:scale-95"
              >
                Yorumu Yayınla
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Sticky Booking Widget */}
        <div className="lg:col-span-1">
          <BookingWidget 
            listing={listing} 
            bookings={bookings} 
            availability={availability} 
            onBook={onBook} 
            currentUser={currentUser}
            currency={currency}
          />
        </div>
      </div>

      {lightboxOpen && (
        <PhotoLightbox
          images={images}
          startIndex={lightboxIndex}
          onClose={() => setLightboxOpen(false)}
        />
      )}
    </div>
  );
}

