import React from "react";
import { X, MessageCircle, ChevronRight } from "lucide-react";

const FALLBACK_AVATAR = "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=100&q=80";

function formatTime(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" });
}

export function InboxModal({ isOpen, onClose, conversations = [], onOpenConversation, currentUser }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white w-full max-w-lg rounded-3xl shadow-2xl flex flex-col max-h-[600px] overflow-hidden">
        {/* Inbox Header */}
        <div className="p-4 border-b border-charcoal-border flex items-center justify-between bg-charcoal-bg">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-airbnb/10 text-airbnb flex items-center justify-center">
              <MessageCircle className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-charcoal">Mesajlarım</h3>
              <p className="text-[11px] text-charcoal-light font-medium">{conversations.length} sohbet</p>
            </div>
          </div>
          <button aria-label="X" onClick={onClose} className="p-2 rounded-full hover:bg-white transition-colors"> <X /> </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto">
          {conversations.length === 0 ? (
            <div className="text-center py-16 flex flex-col items-center gap-3">
              <div className="w-14 h-14 rounded-full bg-charcoal-bg text-charcoal-light flex items-center justify-center">
                <MessageCircle className="w-6 h-6" />
              </div>
              <p className="text-sm font-bold text-charcoal">Henüz mesajınız yok.</p>
              <p className="text-xs text-charcoal-light font-medium">
                Bir ilanın detay sayfasından ev sahibiyle yazışmaya başlayabilirsiniz.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-charcoal-border/40">
              {conversations.map((c) => {
                const counterpart = c.counterpart || {};
                const preview = c.lastMessage?.text || "";
                return (
                  <button
                    key={c.listingId}
                    onClick={() => onOpenConversation(c)}
                    className="w-full text-left px-4 py-3.5 flex items-center gap-3 hover:bg-charcoal-bg transition-colors cursor-pointer"
                  >
                    <img
                      src={counterpart.avatarUrl || FALLBACK_AVATAR}
                      alt={counterpart.name || "Kullanıcı"}
                      className="w-11 h-11 rounded-full object-cover ring-1 ring-charcoal-border shrink-0"
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-xs text-charcoal truncate">
                          {counterpart.name || "Kullanıcı"}
                        </span>
                        <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-full bg-charcoal-bg text-charcoal-light shrink-0">
                          {counterpart.isHost ? "Ev Sahibi" : "Misafir"}
                        </span>
                      </div>
                      <p className="text-[11px] text-charcoal-light truncate mt-0.5">
                        {c.listingTitle} • {c.city}
                      </p>
                      <p className="text-xs text-charcoal font-medium truncate mt-1">
                        {preview.slice(0, 40) || "—"}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-1.5 shrink-0">
                      <span className="text-[10px] text-charcoal-light font-medium">
                        {formatTime(c.lastMessage?.createdAt)}
                      </span>
                      {c.unreadCount > 0 && (
                        <span className="bg-emerald-600 text-white text-[10px] font-black px-2 py-0.5 rounded-full min-w-5 text-center">
                          {c.unreadCount}
                        </span>
                      )}
                      <ChevronRight className="w-4 h-4 text-charcoal-light/60" />
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
