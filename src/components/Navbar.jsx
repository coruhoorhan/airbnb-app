import React, { useState } from "react";
import { Search, Menu, Heart, Briefcase, PlusCircle, Home, Bell, Check, Sparkles, Globe, Compass, Waves, MessageCircle, Sun, Moon, Gift, Star } from "lucide-react";
import { getAvailableCurrencies } from "../lib/currencyEngine.js";

export function Navbar({ 
  currentUser, 
  onSwitchUser, 
  onOpenSearch, 
  onOpenRent, 
  onViewChange, 
  favoritesCount, 
  notifications = [],
  onMarkAllRead,
  currency = "TRY",
  onCurrencyChange,
  unreadMessages = 0,
  onOpenInbox,
  isDarkMode = false,
  onToggleDarkMode,
  onOpenLoyalty,
  onOpenGiftCards,
  onOpenMagdaDashboard,
  loyaltyTier = null
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [currencyOpen, setCurrencyOpen] = useState(false);

  const unreadCount = notifications.filter((n) => !n.isRead).length;
  const currencies = getAvailableCurrencies();
  const currentCurrencyObj = currencies.find((c) => c.code === currency) || currencies[0];

  return (
    <header className="sticky top-0 z-40 bg-white/95 dark:bg-[#0D0F12]/95 backdrop-blur-md border-b border-charcoal-border/50 dark:border-white/10 shadow-xs transition-all">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 sm:h-20 flex items-center justify-between gap-2 sm:gap-4">
        {/* Coastal Modernist Brand Logo */}
        <div 
          onClick={() => onViewChange("explore")} 
          className="flex items-center gap-2.5 cursor-pointer group select-none"
         role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } }}>
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-br from-airbnb to-amber-600 text-white flex items-center justify-center shadow-md group-hover:scale-105 transition-transform">
            <Waves className="w-5 h-5" />
          </div>
          <div className="flex flex-col">
            <span className="text-xl font-display font-extrabold text-charcoal dark:text-white tracking-tight leading-none">
              FATSA<span className="text-airbnb">ESCAPES</span>
            </span>
            <span className="text-[9px] font-mono font-bold text-charcoal-light dark:text-gray-600 tracking-widest uppercase mt-0.5">
              COASTAL & MODERN HAVEN
            </span>
          </div>
        </div>

        {/* Central Kinetic Search Pill */}
        <div 
          onClick={onOpenSearch}
          className="hidden lg:flex items-center bg-charcoal-bg/70 dark:bg-white/5 hover:bg-charcoal-bg border border-charcoal-border dark:border-white/10 rounded-full py-2 px-4 shadow-xs hover:shadow-md transition-all cursor-pointer text-xs font-semibold divide-x divide-charcoal-border/80 dark:divide-white/10"
         role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } }}>
          <div className="px-3 text-charcoal dark:text-white font-bold">Fatsa & Karadeniz</div>
          <div className="px-3 text-charcoal dark:text-white">İstediğiniz Tarih</div>
          <div className="pl-3 pr-1 text-charcoal-light dark:text-gray-600 flex items-center gap-3">
            <span className="font-normal">Misafir Ekle</span>
            <div className="bg-charcoal dark:bg-white/20 text-white p-2 rounded-full shadow-xs hover:bg-airbnb transition-colors">
              <Search className="w-3.5 h-3.5 stroke-[2.5]" />
            </div>
          </div>
        </div>

        {/* Right Actions & Profile Menu */}
        <div className="flex items-center gap-2 sm:gap-3 relative">
          {/* Dark Mode Toggle */}
          <button
            onClick={onToggleDarkMode}
            className="flex items-center gap-1.5 px-3 py-2 rounded-full border border-charcoal-border dark:border-white/10 hover:bg-charcoal-bg dark:hover:bg-white/10 text-xs font-bold text-charcoal dark:text-white transition-colors active:scale-95"
            title={isDarkMode ? "Aydınlık Moda Geç" : "Karanlık Moda Geç"}
          >
            {isDarkMode ? (
              <Sun className="w-3.5 h-3.5 text-amber-400" />
            ) : (
              <Moon className="w-3.5 h-3.5 text-charcoal-light" />
            )}
          </button>

          {/* Currency Switcher */}
          <div className="relative">
            <button
              onClick={() => setCurrencyOpen(!currencyOpen)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-full border border-charcoal-border dark:border-white/10 hover:bg-charcoal-bg dark:hover:bg-white/10 text-xs font-bold text-charcoal dark:text-white transition-colors active:scale-95"
              title="Para Birimi Değiştir"
            >
              <Globe className="w-3.5 h-3.5 text-charcoal-light dark:text-gray-600" />
              <span>{currentCurrencyObj.symbol} {currentCurrencyObj.code}</span>
            </button>

            {currencyOpen && (
              <div 
                className="absolute right-0 mt-2 w-48 bg-white dark:bg-[#16191E] rounded-2xl shadow-xl border border-charcoal-border dark:border-white/10 p-2 z-50 animate-in fade-in"
                onClick={() => setCurrencyOpen(false)}
               role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } }}>
                <div className="px-3 py-1.5 text-[10px] font-extrabold text-charcoal-light dark:text-gray-600 uppercase border-b border-charcoal-border/50 dark:border-white/10">
                  Para Birimi Seçin
                </div>
                <div className="py-1">
                  {currencies.map((c) => (
                    <button
                      key={c.code}
                      onClick={() => onCurrencyChange && onCurrencyChange(c.code)}
                      className={`w-full text-left px-3 py-2 text-xs font-bold rounded-xl flex items-center justify-between transition-colors ${
                        currency === c.code ? "bg-airbnb text-white" : "text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/10"
                      }`}
                    >
                      <span>{c.symbol} {c.code} ({c.name})</span>
                      {currency === c.code && <Check className="w-3.5 h-3.5" />}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          <button 
            onClick={onOpenRent}
            className="hidden lg:flex items-center gap-1.5 px-3.5 py-2 rounded-full hover:bg-charcoal-bg dark:hover:bg-white/10 font-bold text-xs text-charcoal dark:text-white transition-colors cursor-pointer active:scale-95 border border-charcoal-border/60 dark:border-white/10"
          >
            <PlusCircle className="w-4 h-4 text-airbnb" />
            <span>Evinizi Ekleyin</span>
          </button>

          {/* User Mode Switcher Chip */}
          <div className="hidden sm:flex items-center bg-charcoal-bg dark:bg-white/5 border border-charcoal-border dark:border-white/10 rounded-full p-1 text-xs font-semibold">
            <button 
              onClick={() => onSwitchUser("usr_guest_01")}
              className={`px-3 py-1.5 rounded-full transition-all cursor-pointer ${!currentUser?.isHost ? "bg-white dark:bg-[#16191E] shadow-xs text-charcoal dark:text-white font-bold" : "text-charcoal-light dark:text-gray-600"}`}
            >
              Misafir
            </button>
            <button 
              onClick={() => onSwitchUser("usr_host_01")}
              className={`px-3 py-1.5 rounded-full transition-all cursor-pointer ${currentUser?.isHost ? "bg-white dark:bg-[#16191E] shadow-xs text-airbnb font-bold" : "text-charcoal-light dark:text-gray-600"}`}
            >
              Ev Sahibi
            </button>
          </div>

          {/* Messages Inbox Button */}
          <button 
            onClick={onOpenInbox}
            className="p-2.5 rounded-full hover:bg-charcoal-bg dark:hover:bg-white/10 transition-colors relative cursor-pointer"
            title="Mesajlar"
          >
            <MessageCircle className="w-5 h-5 text-charcoal dark:text-white" />
            {unreadMessages > 0 && (
              <span className="absolute top-1 right-1 w-4 h-4 bg-emerald-600 text-white text-[10px] font-black rounded-full flex items-center justify-center animate-pulse">
                {unreadMessages}
              </span>
            )}
          </button>

          {/* Magda AI Guardian Top Bar Button */}
          <button
            onClick={onOpenMagdaDashboard}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-full text-xs font-bold hover:scale-105 active:scale-95 transition shadow-xs cursor-pointer border border-white/20"
            title="Magda-Agent Bilişsel Kontrol Merkezi"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-200 animate-pulse" />
            <span className="hidden sm:inline">AI Guardian</span>
          </button>

          {/* Notification Bell Dropdown */}
          <div className="relative">
            <button 
              onClick={() => setNotifOpen(!notifOpen)}
              className="p-2.5 rounded-full hover:bg-charcoal-bg dark:hover:bg-white/10 transition-colors relative cursor-pointer"
            >
              <Bell className="w-5 h-5 text-charcoal dark:text-white" />
              {unreadCount > 0 && (
                <span className="absolute top-1 right-1 w-4 h-4 bg-airbnb text-white text-[10px] font-black rounded-full flex items-center justify-center animate-pulse">
                  {unreadCount}
                </span>
              )}
            </button>

            {notifOpen && (
              <div className="absolute right-0 mt-2 w-80 bg-white dark:bg-[#16191E] rounded-2xl shadow-xl border border-charcoal-border dark:border-white/10 p-3 z-50 animate-in fade-in slide-in-from-top-2">
                <div className="flex items-center justify-between pb-2 border-b border-charcoal-border/60 dark:border-white/10">
                  <h4 className="font-bold text-xs text-charcoal dark:text-white">Bildirimler ({notifications.length})</h4>
                  {unreadCount > 0 && (
                    <button 
                      onClick={onMarkAllRead}
                      className="text-[11px] text-airbnb font-bold hover:underline"
                    >
                      Tümünü Okundu Say
                    </button>
                  )}
                </div>

                <div className="divide-y divide-charcoal-border/40 dark:divide-white/10 max-h-64 overflow-y-auto my-1">
                  {notifications.map((n) => (
                    <div key={n.id} className="py-2.5 flex flex-col gap-1 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-charcoal dark:text-white">{n.title}</span>
                        {!n.isRead && <span className="w-2 h-2 bg-airbnb rounded-full" />}
                      </div>
                      <p className="text-charcoal-light dark:text-gray-600 text-[11px] leading-tight">{n.body}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Hamburger User Profile Pill */}
          <div className="relative">
            <button 
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex items-center gap-2.5 border border-charcoal-border dark:border-white/10 rounded-full p-1.5 pl-3 hover:shadow-md transition-all bg-white dark:bg-[#16191E] cursor-pointer active:scale-95"
            >
              <Menu className="w-4 h-4 text-charcoal dark:text-white" />
              <img 
                src={currentUser?.avatarUrl} 
                alt={currentUser?.name} 
                className="w-7 h-7 rounded-full object-cover ring-1 ring-charcoal-border" 
              />
              {loyaltyTier && (
                <span className="absolute -bottom-1.5 right-0 text-[9px] font-black px-1.5 py-0.5 rounded-full bg-gradient-to-r from-amber-400 to-purple-500 text-white shadow-sm border border-white">
                  {loyaltyTier}
                </span>
              )}
            </button>

            {menuOpen && (
              <div 
                className="absolute right-0 mt-2 w-64 bg-white dark:bg-[#16191E] rounded-2xl shadow-xl border border-charcoal-border/80 dark:border-white/10 py-2 z-50 animate-in fade-in slide-in-from-top-2 duration-150"
                onClick={() => setMenuOpen(false)}
               role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.currentTarget.click(); } }}>
                <div className="px-4 py-2.5 border-b border-charcoal-border/50 dark:border-white/10">
                  <p className="text-xs text-charcoal-light dark:text-gray-600 font-medium">Giriş Yapıldı:</p>
                  <p className="text-sm font-bold text-charcoal dark:text-white">{currentUser?.name}</p>
                  <span className="inline-block mt-1 text-[11px] px-2 py-0.5 rounded-full bg-airbnb/10 text-airbnb font-bold">
                    {currentUser?.isHost ? "★ Ev Sahibi Modu" : "Misafir Hesabı"}
                  </span>
                </div>

                <div className="py-1">
                  <button 
                    onClick={() => onViewChange("explore")}
                    className="w-full text-left px-4 py-2.5 text-sm text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 font-medium flex items-center gap-2.5 cursor-pointer"
                  >
                    <Home className="w-4 h-4 text-charcoal-light dark:text-gray-600" />
                    <span>Keşfet & İlanlar</span>
                  </button>
                  <button 
                    onClick={() => onViewChange("experiences")}
                    className="w-full text-left px-4 py-2.5 text-sm text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 font-medium flex items-center gap-2.5 cursor-pointer"
                  >
                    <Compass className="w-4 h-4 text-sky-600" />
                    <span>Deneyimler</span>
                  </button>
                  <button 
                    onClick={() => onViewChange("wishlist")}
                    className="w-full text-left px-4 py-2.5 text-sm text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 font-medium flex items-center justify-between cursor-pointer"
                  >
                    <div className="flex items-center gap-2.5">
                      <Heart className="w-4 h-4 text-airbnb" />
                      <span>Favorilerim</span>
                    </div>
                    {favoritesCount > 0 && (
                      <span className="bg-airbnb text-white text-xs px-2 py-0.5 rounded-full font-bold">
                        {favoritesCount}
                      </span>
                    )}
                  </button>
                  <button 
                    onClick={() => onViewChange("trips")}
                    className="w-full text-left px-4 py-2.5 text-sm text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 font-medium flex items-center gap-2.5 cursor-pointer"
                  >
                    <Briefcase className="w-4 h-4 text-charcoal-light dark:text-gray-600" />
                    <span>Seyahatlerim</span>
                  </button>
                  <button 
                    onClick={onOpenLoyalty}
                    className="w-full text-left px-4 py-2.5 text-sm text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 font-medium flex items-center gap-2.5 cursor-pointer"
                  >
                    <Sparkles className="w-4 h-4 text-emerald-600" />
                    <span>Sadakat Puanlarım</span>
                  </button>
                  <button 
                    onClick={onOpenGiftCards}
                    className="w-full text-left px-4 py-2.5 text-sm text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 font-medium flex items-center gap-2.5 cursor-pointer"
                  >
                    <Gift className="w-4 h-4 text-emerald-600" />
                    <span>Hediye Kartlarım</span>
                  </button>
                  <button 
                    onClick={onOpenMagdaDashboard}
                    className="w-full text-left px-4 py-2.5 text-sm text-purple-600 hover:bg-purple-50 font-bold flex items-center gap-2.5 cursor-pointer"
                  >
                    <Sparkles className="w-4 h-4 text-purple-600" />
                    <span>🤖 Magda AI Kontrol Merkezi</span>
                  </button>
                </div>


                <div className="border-t border-charcoal-border/50 dark:border-white/10 py-1">
                  <button
                    onClick={() => {
                      document.cookie = "token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
                      window.location.reload();
                    }}
                    className="w-full text-left px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 font-bold flex items-center gap-2.5 cursor-pointer"
                  >
                    <span>Çıkış Yap</span>
                  </button>
                  <button
                    onClick={() => {
                      fetch("/api/auth/oauth/callback", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email: "guest@fatsa.bel.tr" })
                      }).then(() => window.location.reload());
                    }}
                    className="w-full text-left px-4 py-2.5 text-sm text-blue-600 hover:bg-blue-50 font-bold flex items-center gap-2.5 cursor-pointer"
                  >
                    <span>OAuth2 Giriş (Misafir)</span>
                  </button>
                  <button
                    onClick={() => {
                      fetch("/api/auth/oauth/callback", {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ email: "host@fatsa.bel.tr" })
                      }).then(() => window.location.reload());
                    }}
                    className="w-full text-left px-4 py-2.5 text-sm text-green-600 hover:bg-green-50 font-bold flex items-center gap-2.5 cursor-pointer"
                  >
                    <span>OAuth2 Giriş (Ev Sahibi)</span>
                  </button>
                </div>

                <div className="border-t border-charcoal-border/50 dark:border-white/10 py-1">
                  {currentUser?.isHost ? (
                    <button 
                      onClick={() => onViewChange("host_dashboard")}
                      className="w-full text-left px-4 py-2.5 text-sm text-airbnb hover:bg-airbnb/5 font-bold flex items-center gap-2.5 cursor-pointer"
                    >
                      <PlusCircle className="w-4 h-4 text-airbnb" />
                      <span>Yönetim Merkezi</span>
                    </button>
                  ) : (
                    <button 
                      onClick={onOpenRent}
                      className="w-full text-left px-4 py-2.5 text-sm text-charcoal dark:text-white hover:bg-charcoal-bg dark:hover:bg-white/5 font-semibold flex items-center gap-2.5 cursor-pointer"
                    >
                      <PlusCircle className="w-4 h-4 text-charcoal-light dark:text-gray-600" />
                      <span>Evinizi Ekleyin</span>
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
