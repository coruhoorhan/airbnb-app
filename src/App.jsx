import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "./components/Navbar.jsx";
import { CategoryBar } from "./components/CategoryBar.jsx";
import { ListingCard } from "./components/ListingCard.jsx";
import { SortBar, SORT_OPTIONS } from "./components/SortBar.jsx";
import { RecentlyViewed } from "./components/RecentlyViewed.jsx";
import { ListingDetail } from "./components/ListingDetail.jsx";
import { ListingGridSkeleton } from "./components/ListingSkeleton.jsx";
import { SearchModal } from "./components/SearchModal.jsx";
import { RentModal } from "./components/RentModal.jsx";
import { HostDashboard } from "./components/HostDashboard.jsx";
import { TripsView } from "./components/TripsView.jsx";
import { WishlistView } from "./components/WishlistView.jsx";
import { MapView } from "./components/MapView.jsx";
import { ChatModal } from "./components/ChatModal.jsx";
import { InboxModal } from "./components/InboxModal.jsx";
import { LoyaltyDashboard } from "./components/LoyaltyDashboard.jsx";
import { GiftCardModal } from "./components/GiftCardModal.jsx";
import { ExperienceCard } from "./components/ExperienceCard.jsx";
import { ExperienceDetailModal } from "./components/ExperienceDetailModal.jsx";
import { AdminMagdaDashboard } from "./components/AdminMagdaDashboard.jsx";
import { MagdaConciergeWidget } from "./components/MagdaConciergeWidget.jsx";
import { INITIAL_USERS } from "./data/users.js";
import { INITIAL_LISTINGS } from "./data/listings.js";
import { recomputeAverageRating } from "./lib/bookingEngine.js";
import { formatCurrency, SUPPORTED_CURRENCIES } from "./lib/currencyEngine.js";
import { Map, List, Globe, Shield, Sparkles, Waves, ArrowRight, Compass, Anchor, ShieldCheck, Sun, Star, Cloud, CloudSun, CloudRain, Droplets, Clock, Bell, Gift } from "lucide-react";

export function App() {
  const [isMagdaDashboardOpen, setIsMagdaDashboardOpen] = useState(false);
  const [users, setUsers] = useState(INITIAL_USERS);

  const [currentUserId, setCurrentUserId] = useState(() => {
    try {
      const token = document.cookie.split('; ').find(row => row.startsWith('token='))?.split('=')[1];
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (payload && payload.id) return payload.id;
      }
    } catch (e) {}
    return "usr_guest_01";
  });

  const [listings, setListings] = useState(INITIAL_LISTINGS);
  const [isLoadingListings, setIsLoadingListings] = useState(true);
  const [bookings, setBookings] = useState([
    {
      id: "bkg_01",
      listingId: "list_01",
      guestId: "usr_guest_01",
      hostId: "usr_host_01",
      checkIn: "2026-09-10",
      checkOut: "2026-09-14",
      numGuests: 4,
      nightlyPrice: 4850,
      cleaningFee: 750,
      serviceFee: 450,
      totalPrice: 20600,
      status: "confirmed",
      paymentStatus: "unpaid",
      createdAt: Date.now() - 86400000 * 2
    }
  ]);
  const [favorites, setFavorites] = useState(["list_01", "list_04"]);
  const [reviews, setReviews] = useState([
    {
      id: "rev_01",
      listingId: "list_01",
      bookingId: "bkg_01",
      reviewerId: "usr_guest_01",
      reviewerName: "Ahmet Yılmaz",
      rating: 5,
      comment: "Ev fotoğraflardan çok daha güzeldi! Deniz manzarası ve gün batımı muhteşemdi.",
      createdAt: Date.now() - 86400000 * 5
    }
  ]);
  const [notifications, setNotifications] = useState([
    {
      id: "notif_01",
      userId: "usr_guest_01",
      type: "booking_confirmed",
        title: "Rezervasyonunuz Onaylandı",
      body: "Fatsa Sahilinde Lüks Villa için 10-14 Eylül rezervasyonunuz hazır.",
      isRead: false,
      createdAt: Date.now() - 3600000
    }
  ]);
  const [messages, setMessages] = useState([]);

  const [selectedCategory, setSelectedCategory] = useState("all");
  const [searchParams, setSearchParams] = useState(null);
  const [selectedListing, setSelectedListing] = useState(null);
  const [currentView, setCurrentView] = useState("explore"); // "explore", "detail", "trips", "wishlist", "host_dashboard"
  const [showMap, setShowMap] = useState(false);
  const [sortOrder, setSortOrder] = useState(() => {
    const stored = localStorage.getItem("veys-sort-order");
    return stored && SORT_OPTIONS.some((opt) => opt.id === stored) ? stored : "recommended";
  });
  const [recentlyViewedIds, setRecentlyViewedIds] = useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("veys-recently-viewed") || "[]");
      return Array.isArray(stored) ? stored : [];
    } catch {
      return [];
    }
  });
  const [currency, setCurrency] = useState(() => {
    const stored = localStorage.getItem("veys-currency");
    return stored && SUPPORTED_CURRENCIES[stored] ? stored : "TRY";
  });
  const [isDarkMode, setIsDarkMode] = useState(() => localStorage.getItem("veys-dark-mode") === "true");
  const [isLoyaltyOpen, setIsLoyaltyOpen] = useState(false);
  const [isGiftCardOpen, setIsGiftCardOpen] = useState(false);
  const [weatherData, setWeatherData] = useState(null);
  const [lastMinuteDeals, setLastMinuteDeals] = useState([]);
  const [experiences, setExperiences] = useState([]);
  const [selectedExperience, setSelectedExperience] = useState(null);
  const [isExperienceOpen, setIsExperienceOpen] = useState(false);
  const [loyaltyTier, setLoyaltyTier] = useState(null);

  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isRentOpen, setIsRentOpen] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [chatListing, setChatListing] = useState(null);
  const [isInboxOpen, setIsInboxOpen] = useState(false);
  const [conversations, setConversations] = useState([]);
  const [chatSendError, setChatSendError] = useState("");
  useEffect(() => {
    localStorage.setItem("veys-currency", currency);
    localStorage.setItem("veys-dark-mode", String(isDarkMode));
    if (isDarkMode) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }
  }, [currency, isDarkMode]);

  useEffect(() => {
    localStorage.setItem("veys-sort-order", sortOrder);
  }, [sortOrder]);

  useEffect(() => {
    fetch("/api/weather?lat=41.0451&lng=37.5010")
      .then((r) => r.json())
      .then((d) => {
        if (d.success && d.data) setWeatherData(d.data);
      })
      .catch(() => {});

    fetch("/api/last-minute")
      .then((r) => r.json())
      .then((d) => {
        if (d.success && d.data) setLastMinuteDeals(d.data);
      })
      .catch(() => {});

    fetch(`/api/notifications?userId=${currentUserId}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.success && d.data) {
          setNotifications((prev) => {
            const existing = new Set(prev.map((n) => n.id));
            const newOnes = d.data.filter((n) => !existing.has(n.id));
            return [...newOnes, ...prev];
          });
        }
      })
      .catch(() => {});

    fetch(`/api/loyalty/${currentUserId}`)
      .then((r) => r.json())
      .then((d) => {
        if (d.success && d.data?.tier?.tier?.name) setLoyaltyTier(d.data.tier.tier.name);
      })
      .catch(() => {});
  }, [currentUserId]);

  useEffect(() => {
    fetch("/api/experiences")
      .then((r) => r.json())
      .then((d) => {
        if (d.success && d.data) setExperiences(d.data);
      })
      .catch(() => {});
  }, []);

  const refreshConversations = useCallback(() => {
    fetch("/api/conversations?userId=" + currentUserId)
      .then((r) => r.json())
      .then((d) => { if (d.success) setConversations(d.data || []); })
      .catch(() => {});
  }, [currentUserId]);

  const currentUser = users.find((u) => u.id === currentUserId) || users[0];

  useEffect(() => {
    setIsLoadingListings(true);
    fetch("/api/listings")
      .then((r) => r.json())
      .then((data) => {
        if (data.success && data.data) {
          setListings(data.data);
        }
      })
      .catch(() => {})
      .finally(() => {
        setTimeout(() => setIsLoadingListings(false), 300);
      });
  }, []);

  useEffect(() => {
    if (!isChatOpen || !chatListing) return;
    const es = new EventSource(`/api/messages/stream?listingId=${chatListing.id}&userId=${currentUserId}`);
    es.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        setMessages((prev) => (prev.some((m) => m.id === msg.id) ? prev : [...prev, msg]));
      } catch {/* ignore parse errors */}
    };
    return () => es.close();
  }, [isChatOpen, chatListing, currentUserId]);

  useEffect(() => {
    refreshConversations();
  }, [refreshConversations]);

  const handleCategorySelect = (cat) => {
    setSelectedCategory(cat);
    setIsLoadingListings(true);
    setTimeout(() => setIsLoadingListings(false), 200);
  };

  const handleSwitchUser = (userId) => {
    setCurrentUserId(userId);
    const targetUser = users.find((u) => u.id === userId);
    if (targetUser?.isHost) {
      setCurrentView("host_dashboard");
    } else {
      setCurrentView("explore");
    }
  };

  const handleToggleDarkMode = () => {
    setIsDarkMode((prev) => !prev);
  };

  const handleOpenListing = (listing) => {
    setSelectedListing(listing);
    setCurrentView("detail");
    setRecentlyViewedIds((prev) => [listing.id, ...prev.filter((id) => id !== listing.id)].slice(0, 6));
  };

  useEffect(() => {
    localStorage.setItem("veys-recently-viewed", JSON.stringify(recentlyViewedIds));
  }, [recentlyViewedIds]);

  const handleOpenLoyalty = () => setIsLoyaltyOpen(true);
  const handleOpenGiftCards = () => setIsGiftCardOpen(true);

  const handleToggleFavorite = async (listingId) => {
    try {
      const res = await fetch("/api/favorites/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ userId: currentUserId, listingId })
      });
      const data = await res.json();
      if (data.success) {
        if (data.isFavorited) {
          setFavorites((prev) => [...prev, listingId]);
        } else {
          setFavorites((prev) => prev.filter((id) => id !== listingId));
        }
        return;
      }
    } catch {
      // Fallback local toggle
    }

    setFavorites((prev) =>
      prev.includes(listingId)
        ? prev.filter((id) => id !== listingId)
        : [...prev, listingId]
    );
  };

  const handleCreateListing = (newListing) => {
    setListings((prev) => [newListing, ...prev]);
    setCurrentView("explore");
    setNotifications((prev) => [
      {
        id: `notif_${Date.now()}`,
        userId: currentUser.id,
        type: "listing_created",
        title: "İlanınız Yayında",
        body: `"${newListing.title}" başarıyla oluşturuldu ve misafirlere açıldı.`,
        isRead: false,
        createdAt: Date.now()
      },
      ...prev
    ]);
  };

  const handleBook = (bookingData) => {
    const newBooking = {
      id: bookingData.id || `bkg_${Date.now()}`,
      ...bookingData,
      createdAt: Date.now()
    };
    setBookings((prev) => [newBooking, ...prev]);

    setNotifications((prev) => [
      {
        id: `notif_${Date.now()}`,
        userId: bookingData.hostId,
        type: "new_booking",
        title: "Yeni Rezervasyon Talebi",
        body: `${bookingData.checkIn} - ${bookingData.checkOut} tarihleri için rezervasyon talebi alındı.`,
        isRead: false,
        createdAt: Date.now()
      },
      ...prev
    ]);
  };

  const handleCancelBooking = (bookingId) => {
    setBookings((prev) =>
      prev.map((b) =>
        b.id === bookingId ? { ...b, status: "cancelled" } : b
      )
    );
  };

  const handleConfirmBooking = (bookingId) => {
    setBookings((prev) =>
      prev.map((b) =>
        b.id === bookingId ? { ...b, status: "confirmed" } : b
      )
    );
  };

  const handleDeclineBooking = (bookingId) => {
    setBookings((prev) =>
      prev.map((b) =>
        b.id === bookingId ? { ...b, status: "cancelled" } : b
      )
    );
  };

  const handleSendMessage = async (msgData) => {
    setChatSendError("");
    try {
      const res = await fetch("/api/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          listingId: msgData.listingId,
          senderId: msgData.senderId,
          text: msgData.text
        })
      });
      const data = await res.json();
      if (!data.success) {
        setChatSendError(data.error || "Mesaj gönderilemedi.");
      } else {
        refreshConversations();
      }
    } catch {
      setChatSendError("Mesaj gönderilirken bir hata oluştu.");
    }
  };

  const handleOpenChat = async (listing) => {
    setChatListing(listing);
    setIsChatOpen(true);
    try {
      const res = await fetch("/api/messages?listingId=" + listing.id);
      const data = await res.json();
      if (data.success) setMessages(data.data || []);
    } catch {/* ignore */}
    try {
      await fetch("/api/messages/read", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listingId: listing.id, userId: currentUserId })
      });
    } catch {/* ignore */}
    refreshConversations();
  };

  const handleOpenInboxConversation = (c) => {
    const listing = listings.find((l) => l.id === c.listingId);
    if (listing) {
      setIsInboxOpen(false);
      handleOpenChat(listing);
    }
  };

  const handleAddReview = (reviewData) => {
    const newReview = {
      id: `rev_${Date.now()}`,
      ...reviewData,
      createdAt: Date.now()
    };
    setReviews((prev) => [newReview, ...prev]);

    const listingReviews = [...reviews.filter((r) => r.listingId === reviewData.listingId), newReview];
    const newRating = recomputeAverageRating(listingReviews);

    setListings((prev) =>
      prev.map((l) =>
        l.id === reviewData.listingId
          ? { ...l, avgRating: newRating, reviewCount: (l.reviewCount || 0) + 1 }
          : l
      )
    );
  };

  const handleMarkAllRead = () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, isRead: true })));
  };

  // Filter listings
  const getEffectivePrice = (l) => {
    return l.lastMinuteDiscount > 0 && l.lastMinuteOriginalPrice
      ? Math.round(l.lastMinuteOriginalPrice * (1 - l.lastMinuteDiscount / 100))
      : l.pricePerNight;
  };

  const filteredListings = listings.filter((l) => {
    if (selectedCategory !== "all" && l.category !== selectedCategory) {
      return false;
    }
    if (searchParams) {
      if (searchParams.destination) {
        const dest = searchParams.destination.toLowerCase();
        const matchesCity = l.city.toLowerCase().includes(dest);
        const matchesTitle = l.title.toLowerCase().includes(dest);
        if (!matchesCity && !matchesTitle) return false;
      }
      if (searchParams.guests && l.maxGuests < Number(searchParams.guests)) {
        return false;
      }
      if (searchParams.minPrice && Number(searchParams.minPrice) > 0 && getEffectivePrice(l) < Number(searchParams.minPrice)) {
        return false;
      }
      if (searchParams.maxPrice && Number(searchParams.maxPrice) > 0 && getEffectivePrice(l) > Number(searchParams.maxPrice)) {
        return false;
      }
      if (searchParams.lastMinute && !(l.lastMinuteDiscount > 0)) {
        return false;
      }
    }
    return true;
  });

  const sortedListings = sortOrder === "recommended"
    ? filteredListings
    : [...filteredListings].sort((a, b) => {
        if (sortOrder === "price_asc") return getEffectivePrice(a) - getEffectivePrice(b);
        if (sortOrder === "price_desc") return getEffectivePrice(b) - getEffectivePrice(a);
        if (sortOrder === "rating_desc") return (b.avgRating || 0) - (a.avgRating || 0);
        return 0;
      });
  const recentlyViewedListings = recentlyViewedIds
    .map((id) => listings.find((l) => l.id === id))
    .filter(Boolean);

  const featuredVilla = listings[0] || INITIAL_LISTINGS[0];

  const renderWeatherIcon = (code) => {
    if (code === 0) return <Sun className="w-5 h-5" />;
    if (code <= 3) return <CloudSun className="w-5 h-5" />;
    if (code >= 45 && code < 51) return <Cloud className="w-5 h-5" />;
    if (code >= 51) return <CloudRain className="w-5 h-5" />;
    return <Sun className="w-5 h-5" />;
  };

  return (
    <div className="min-h-[100dvh] flex flex-col bg-white dark:bg-charcoal-dark">
      {/* Coastal Navbar */}
      <Navbar
        currentUser={currentUser}
        onSwitchUser={handleSwitchUser}
        onOpenSearch={() => setIsSearchOpen(true)}
        onOpenRent={() => setIsRentOpen(true)}
        onViewChange={(view) => {
          setCurrentView(view);
          setSelectedListing(null);
        }}
        favoritesCount={favorites.length}
        notifications={notifications.filter((n) => n.userId === currentUser.id)}
        onMarkAllRead={handleMarkAllRead}
        currency={currency}
        onCurrencyChange={setCurrency}
        unreadMessages={conversations.reduce((s, c) => s + c.unreadCount, 0)}
        onOpenInbox={() => setIsInboxOpen(true)}
        isDarkMode={isDarkMode}
        onToggleDarkMode={handleToggleDarkMode}
        onOpenLoyalty={handleOpenLoyalty}
        onOpenGiftCards={handleOpenGiftCards}
        loyaltyTier={loyaltyTier}
        onOpenMagdaDashboard={() => setIsMagdaDashboardOpen(true)}
      />

      {/* Main Content View */}
      <main className="flex-1">
        {currentView === "explore" && (
          <div className="flex flex-col">
            {/* Luminous, Sunlit, Coastal Modernist Split Hero */}
            <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-6 pb-2 w-full">
              <div className="bg-gradient-to-br from-sky-50/40 via-white to-amber-50/30 border border-charcoal-border/70 rounded-3xl p-6 sm:p-10 shadow-md relative overflow-hidden grid grid-cols-1 lg:grid-cols-12 gap-8 items-center">
                {/* Background Subtle Watermark */}
                <div className="absolute right-0 bottom-0 opacity-5 pointer-events-none translate-x-8 translate-y-8">
                  <Waves className="w-80 h-80 text-charcoal" />
                </div>

                {/* Left Column: Editorial Sunlit Typography */}
                <div className="lg:col-span-7 flex flex-col gap-4 z-10">
                  <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white text-emerald-800 text-xs font-mono font-bold w-fit shadow-xs border border-emerald-200">
                    <Sun className="w-3.5 h-3.5 text-amber-500" />
                    <span>FATSA & DOĞU KARADENİZ KIYILARI</span>
                  </div>

                  <h1 className="text-4xl sm:text-5xl lg:text-6xl font-display font-black text-charcoal tracking-tight leading-[1.05]">
                    Karadeniz'in En Eşsiz <span className="text-airbnb">Kıyı Yalıları</span> ve Dağ Evleri
                  </h1>

                  <p className="text-xs sm:text-sm text-charcoal-light max-w-[55ch] font-medium leading-relaxed">
                    Masmavi deniz kıyısında müstakil villalar, fındık bahçelerinde taş konaklar ve huzurlu manzaralar.
                  </p>

                  <div className="flex flex-wrap items-center gap-3 pt-2">
                    <button
                      onClick={() => setIsSearchOpen(true)}
                      className="px-6 py-3.5 bg-airbnb hover:bg-airbnb-dark text-white rounded-2xl font-bold text-xs shadow-md hover:shadow-lg transition-[background-color,box-shadow,transform] flex items-center gap-2 active:scale-95 cursor-pointer"
                    >
                      <span>İlanları Keşfet</span>
                      <ArrowRight className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setShowMap(!showMap)}
                      className="px-5 py-3.5 bg-white hover:bg-charcoal-bg text-charcoal rounded-2xl font-bold text-xs border border-charcoal-border shadow-xs transition-[background-color,box-shadow,transform] flex items-center gap-2 active:scale-95 cursor-pointer"
                    >
                      <Map className="w-4 h-4 text-emerald-600" />
                      <span>{showMap ? "Liste Görünümü" : "Haritada İncele"}</span>
                    </button>
                  </div>
                </div>

                {/* Right Column: Luminous Showcase Villa Card */}
                <div className="lg:col-span-5 flex flex-col gap-3 z-10">
                {featuredVilla && (
                  <div 
                    onClick={() => {
                      handleOpenListing(featuredVilla);
                    }}
                    className="bg-white border border-charcoal-border rounded-3xl p-3.5 flex flex-col gap-3 shadow-md hover:shadow-xl transition-shadow cursor-pointer group z-10 dark:bg-white/5 dark:border-white/10"
                  >
                    <div className="relative aspect-video sm:aspect-[16/10] rounded-2xl overflow-hidden bg-charcoal-bg">
                      <img 
                        src={featuredVilla.images?.[0]} 
                        alt={featuredVilla.title}
                        className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" 
                      />
                      <div className="absolute top-2.5 left-2.5 bg-white/95 backdrop-blur-md text-charcoal px-2.5 py-1 rounded-lg text-[10px] font-mono font-bold shadow-xs border border-charcoal-border/50 flex items-center gap-1">
                        <Sparkles className="w-3 h-3 text-amber-500" />
                        <span>ÖNE ÇIKAN KIYI YALISI</span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between px-1">
                      <div>
                        <h3 className="font-extrabold text-sm text-charcoal">{featuredVilla.title}</h3>
                        <p className="text-[11px] text-charcoal-light">{featuredVilla.city}, {featuredVilla.country}</p>
                      </div>
                      <div className="text-right font-mono">
                        <span className="text-base font-black text-airbnb">
                          {formatCurrency(featuredVilla.pricePerNight, currency)}
                        </span>
                        <span className="text-[10px] text-charcoal-light block">/gece</span>
                      </div>
                    </div>
                  </div>
                )}
                {weatherData?.current && (
                  <div className="bg-white border border-charcoal-border rounded-2xl p-3.5 flex items-center justify-between gap-3 shadow-md dark:bg-white/5 dark:border-white/10">
                    <div className="flex items-center gap-3">
                      <div className="w-11 h-11 rounded-xl bg-sky-50 text-sky-600 flex items-center justify-center dark:bg-white/10 dark:text-sky-300">
                        {renderWeatherIcon(weatherData.current.weather_code)}
                      </div>
                      <div>
                        <p className="text-[10px] font-mono font-bold text-charcoal-light uppercase tracking-wider">Fatsa Hava Durumu</p>
                        <p className="text-xl font-black font-mono tabular-nums text-charcoal dark:text-white leading-tight">
                          {Math.round(weatherData.current.temperature_2m)}°C
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-charcoal-light">
                      <div className="flex items-center gap-1 text-[11px] font-medium">
                        <Droplets className="w-3.5 h-3.5 text-sky-500" />
                        <span className="font-mono tabular-nums">{Math.round(weatherData.current.relative_humidity_2m)}%</span>
                      </div>
                    </div>
                  </div>
                )}
                </div>
              </div>
            </section>

            {lastMinuteDeals.length > 0 && (
              <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-8 w-full">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-xl font-black text-charcoal dark:text-white tracking-tight flex items-center gap-2">
                    <Clock className="w-5 h-5 text-amber-500" />
                    <span>Son Dakika Fırsatları</span>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
                      {lastMinuteDeals.length} ilan
                    </span>
                  </h2>
                  <button
                    onClick={() => setSearchParams((s) => ({ ...(s || {}), lastMinute: true }))}
                    className="text-xs font-bold text-airbnb hover:text-airbnb-dark transition-colors flex items-center gap-1 cursor-pointer"
                  >
                    Tümünü Gör
                    <ArrowRight className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex gap-4 overflow-x-auto pb-2 -mx-4 px-4 snap-x">
                  {lastMinuteDeals.map((deal) => (
                    <div key={deal.id} className="min-w-[270px] max-w-[270px] snap-start">
                      <ListingCard
                        listing={deal}
                        onSelect={() => {
                          handleOpenListing(deal);
                        }}
                        isFavorite={favorites.includes(deal.id)}
                        onToggleFavorite={handleToggleFavorite}
                        currency={currency}
                        currentUserId={currentUserId}
                      />
                    </div>
                  ))}
                </div>
              </section>
            )}

            {recentlyViewedListings.length >= 2 && (
              <RecentlyViewed
                listings={recentlyViewedListings}
                onSelect={handleOpenListing}
                favorites={favorites}
                onToggleFavorite={handleToggleFavorite}
                currency={currency}
                currentUserId={currentUserId}
              />
            )}

            {/* Category Filter Bar */}
            <CategoryBar
              selectedCategory={selectedCategory}
              onSelectCategory={handleCategorySelect}
            />

            {/* Listings Grid or Map View */}
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
              {showMap ? (
                <MapView
                  listings={filteredListings}
                  onSelectListing={(l) => {
                    handleOpenListing(l);
                  }}
                  currency={currency}
                />
              ) : (
                <>
                  {filteredListings.length > 0 && (
                    <div className="mb-8">
                      <SortBar sortOrder={sortOrder} onSortChange={setSortOrder} />
                    </div>
                  )}
                  {isLoadingListings ? (
                    <ListingGridSkeleton count={8} />
                  ) : filteredListings.length === 0 ? (
                    <div className="text-center py-20 flex flex-col items-center gap-3">
                      <p className="text-lg font-bold text-charcoal">Eşleşen kıyı evi bulunamadı</p>
                      <p className="text-sm text-charcoal-light font-medium">Arama filtrelerinizi genişletmeyi veya farklı bir kategori seçmeyi deneyin.</p>
                      <button
                        onClick={() => {
                          setSelectedCategory("all");
                          setSearchParams(null);
                        }}
                        className="mt-2 px-5 py-2.5 bg-charcoal text-white rounded-xl text-xs font-bold hover:bg-black transition-colors cursor-pointer"
                      >
                        Filtreleri Temizle
                      </button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-x-6 gap-y-10">
                      {sortedListings.map((listing, index) => (
                        <ListingCard
                          key={listing.id}
                          featured={index === 0}
                          listing={listing}
                          onSelect={(l) => {
                            handleOpenListing(l);
                          }}
                          isFavorite={favorites.includes(listing.id)}
                          onToggleFavorite={handleToggleFavorite}
                          currency={currency}
                          currentUserId={currentUserId}
                        />
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>

            {/* Floating Map Toggle Button */}
            <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-30">
              <button
                onClick={() => setShowMap(!showMap)}
                className="bg-charcoal hover:bg-black text-white px-5 py-3.5 rounded-full font-extrabold text-xs tracking-wide shadow-xl flex items-center gap-2 transition-[background-color,box-shadow,transform] active:scale-95 border border-charcoal-border hover:shadow-2xl cursor-pointer"
              >
                {showMap ? (
                  <>
                    <List className="w-4 h-4" />
                    <span>Listeyi Göster</span>
                  </>
                ) : (
                  <>
                    <Map className="w-4 h-4 text-amber-400" />
                    <span>Haritayı Göster</span>
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {currentView === "detail" && selectedListing && (
          <ListingDetail
            listing={selectedListing}
            currentUser={currentUser}
            onBack={() => {
              setCurrentView("explore");
              setSelectedListing(null);
            }}
            onBook={handleBook}
            onOpenChat={handleOpenChat}
            bookings={bookings.filter((b) => b.listingId === selectedListing.id)}
            reviews={reviews.filter((r) => r.listingId === selectedListing.id)}
            isFavorite={favorites.includes(selectedListing.id)}
            onToggleFavorite={handleToggleFavorite}
            currency={currency}
            currentUserId={currentUserId}
          />
        )}

        {currentView === "trips" && (
          <TripsView
            bookings={bookings.filter((b) => b.guestId === currentUser.id)}
            listings={listings}
            onSelectListing={(l) => {
              handleOpenListing(l);
            }}
            onCancelBooking={handleCancelBooking}
            onAddReview={handleAddReview}
            onExplore={() => setCurrentView("explore")}
            currency={currency}
          />
        )}

        {currentView === "wishlist" && (
          <WishlistView
            favorites={favorites}
            listings={listings}
            onSelectListing={(l) => {
              handleOpenListing(l);
            }}
            onToggleFavorite={handleToggleFavorite}
            onExplore={() => setCurrentView("explore")}
            currency={currency}
          />
        )}

        {currentView === "host_dashboard" && (
          <HostDashboard
            listings={listings.filter((l) => l.hostId === currentUser.id || currentUser.id === "usr_host_01")}
            bookings={bookings.filter((b) => b.hostId === currentUser.id || currentUser.id === "usr_host_01")}
            onOpenRent={() => setIsRentOpen(true)}
            onConfirmBooking={handleConfirmBooking}
            onDeclineBooking={handleDeclineBooking}
          />
        )}

        {currentView === "experiences" && (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-2xl sm:text-3xl font-display font-black text-charcoal dark:text-white tracking-tight">
                  Fatsa'da Deneyimler
                </h1>
                <p className="text-xs font-medium text-charcoal-light dark:text-gray-400 mt-1">
                  Karadeniz'in eşsiz doğasında unutulmaz anlar yaşayın
                </p>
              </div>
              <button
                onClick={() => setCurrentView("explore")}
                className="text-xs font-bold text-airbnb hover:text-airbnb-dark transition-colors cursor-pointer"
              >
                ← İlanlara Dön
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
              {experiences.map((exp) => (
                <ExperienceCard
                  key={exp.id}
                  experience={exp}
                  currency={currency}
                  onSelect={(exp) => {
                    setSelectedExperience(exp);
                    setIsExperienceOpen(true);
                  }}
                />
              ))}
            </div>

            {experiences.length === 0 && (
              <div className="text-center py-20">
                <Compass className="w-12 h-12 mx-auto text-charcoal-light dark:text-gray-500 mb-3" />
                <p className="text-sm font-semibold text-charcoal-light dark:text-gray-400">Henüz deneyim bulunamadı.</p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Global Modals */}
      <SearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onSearch={(params) => {
          setSearchParams(params);
          setCurrentView("explore");
        }}
      />

      <RentModal
        isOpen={isRentOpen}
        onClose={() => setIsRentOpen(false)}
        currentUser={currentUser}
        onCreateListing={handleCreateListing}
      />

      {isChatOpen && chatListing && (
        <ChatModal
          isOpen={isChatOpen}
          onClose={() => {
            setIsChatOpen(false);
            setChatListing(null);
            setChatSendError("");
            refreshConversations();
          }}
          listing={chatListing}
          currentUser={currentUser}
          messages={messages.filter((m) => m.listingId === chatListing.id)}
          onSendMessage={handleSendMessage}
          host={users.find((u) => u.id === listings.find((l) => l.id === chatListing.id)?.hostId)}
          sendError={chatSendError}
      />)}

      <InboxModal
        isOpen={isInboxOpen}
        onClose={() => {
          setIsInboxOpen(false);
          refreshConversations();
        }}
        conversations={conversations}
        onOpenConversation={handleOpenInboxConversation}
        currentUser={currentUser}
      />

      <LoyaltyDashboard
        isOpen={isLoyaltyOpen}
        onClose={() => setIsLoyaltyOpen(false)}
        userId={currentUserId}
      />

      <GiftCardModal
        isOpen={isGiftCardOpen}
        onClose={() => setIsGiftCardOpen(false)}
        userId={currentUserId}
      />

      <ExperienceDetailModal
        experience={selectedExperience}
        currency={currency}
        currentUser={currentUser}
        onClose={() => {
          setSelectedExperience(null);
          setIsExperienceOpen(false);
        }}
        onReserve={() => {
          setIsExperienceOpen(false);
        }}
      />

      {/* Modernist Clean Footer */}
      <footer className="bg-charcoal-dark text-white py-10 mt-16 text-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="font-display font-extrabold text-sm tracking-tight text-amber-400">FATSA ESCAPES</span>
            <span className="text-white/40">·</span>
            <span className="text-white/70">Karadeniz Kıyı Mimarisi © 2026</span>
          </div>

          <div className="flex items-center gap-6 font-medium text-white/80">
            <div className="flex items-center gap-1.5">
              <Globe className="w-4 h-4 text-amber-400" />
              <span>Türkçe (TR)</span>
            </div>
            <div className="flex items-center gap-1.5 font-mono">
              <span>{currency}</span>
            </div>
            <div className="flex items-center gap-1 text-emerald-400 font-bold">
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>iyzico & SQLite WAL</span>
            </div>
          </div>
        </div>
      </footer>
      {/* Magda-Agent Admin & Bilişsel Kontrol Merkezi */}
      {isMagdaDashboardOpen && (
        <AdminMagdaDashboard onClose={() => setIsMagdaDashboardOpen(false)} />
      )}

      {/* Magda-Agent AI Concierge Floating Widget */}
      <MagdaConciergeWidget onSelectListing={(id) => setSelectedListing(id)} />

    </div>
  );
}
