import React, { useState } from "react";
import { X, Send } from "lucide-react";

export function ChatModal({ isOpen, onClose, listing, currentUser, messages = [], onSendMessage, host, sendError = "" }) {
  const [inputText, setInputText] = useState("");

  if (!isOpen || !listing) return null;

  const handleSend = (e) => {
    e.preventDefault();
    if (!inputText.trim()) return;

    onSendMessage({
      listingId: listing.id,
      senderId: currentUser.id,
      senderName: currentUser.name,
      text: inputText.trim()
    });
    setInputText("");
  };

  const listingMessages = messages.filter((m) => m.listingId === listing.id);
  const hostName = host?.name || "Ev Sahibi";
  const hostRole = host ? (host.isHost ? "Ev Sahibi" : "Misafir") : "Ev Sahibi";

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white w-full max-w-lg rounded-3xl shadow-2xl flex flex-col h-[520px] overflow-hidden">
        {/* Chat Header */}
        <div className="p-4 border-b border-charcoal-border flex items-center justify-between bg-charcoal-bg">
          <div className="flex items-center gap-3">
            <img 
              src={host?.avatarUrl || "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=100&q=80"} 
              alt={hostName}
              className="w-10 h-10 rounded-full object-cover ring-1 ring-charcoal-border" 
            />
            <div>
              <h3 className="font-bold text-sm text-charcoal flex items-center gap-2">
                {hostName}
                <span className="text-[9px] font-mono font-bold text-airbnb bg-airbnb/10 px-1.5 py-0.5 rounded-full">
                  {hostRole}
                </span>
              </h3>
              <p className="text-[11px] text-charcoal-light truncate max-w-[240px] font-medium">{listing.title}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-white transition-colors">
            <X className="w-5 h-5 text-charcoal" />
          </button>
        </div>

        {/* Message Bubble Feed */}
        <div className="flex-1 p-4 overflow-y-auto flex flex-col gap-3">
          <div className="text-center my-2">
            <span className="text-[11px] bg-charcoal-bg text-charcoal-light px-3 py-1 rounded-full font-medium">
              Sohbet Başlatıldı • {listing.city}
            </span>
          </div>

          {listingMessages.length === 0 && (
            <div className="text-center text-xs text-charcoal-light my-auto">
              Ev sahibine rezervasyon veya ev hakkında merak ettiklerinizi sorabilirsiniz.
            </div>
          )}

          {listingMessages.map((msg) => {
            const isMe = msg.senderId === currentUser.id;
            return (
              <div 
                key={msg.id}
                className={`flex flex-col max-w-[75%] ${isMe ? "ml-auto items-end" : "mr-auto items-start"}`}
              >
                <span className="text-[10px] text-charcoal-light mb-0.5">
                  {msg.senderName}
                  <span className="ml-1 text-[9px] text-charcoal-light/70">
                    {new Date(msg.createdAt).toLocaleTimeString("tr-TR", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </span>
                <div className={`p-3 rounded-2xl text-xs font-medium ${
                  isMe ? "bg-airbnb text-white rounded-br-none" : "bg-charcoal-bg text-charcoal rounded-bl-none border border-charcoal-border/50"
                }`}>
                  {msg.text}
                </div>
              </div>
            );
          })}
        </div>

        {/* Input Bar */}
        <form onSubmit={handleSend} className="p-3 border-t border-charcoal-border flex items-center gap-2 bg-white">
          <input 
            type="text"
            placeholder="Bir mesaj yazın..."
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            className="flex-1 bg-charcoal-bg rounded-xl px-4 py-2.5 text-xs font-medium text-charcoal outline-none focus:ring-1 focus:ring-charcoal"
          />
          <button 
            type="submit"
            disabled={!inputText.trim()}
            className="p-2.5 bg-airbnb text-white rounded-xl hover:bg-airbnb-dark disabled:opacity-40 transition-all"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
        {sendError && (
          <p className="px-4 pb-2 text-[11px] font-semibold text-rose-600">{sendError}</p>
        )}
      </div>
    </div>
  );
}
