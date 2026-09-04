import React, { useState, useRef, useEffect } from "react";
import { Sparkles, X, Send, Bot, Star, MapPin, RefreshCw } from "lucide-react";

export function MagdaConciergeWidget({ onSelectListing }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      sender: "magda",
      text: "Merhaba! Ben Fatsa Escapes AI Asistanınızım. Size en uygun tatil evini bulabilir, fiyatları ve müsaitlik durumunu kontrol edebilirim. Nasıl bir yer arıyorsunuz?",
      recommendations: [],
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [inputQuery, setInputQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
    }
  }, [messages, isOpen]);

  const handleSendMessage = async (queryToSend = null) => {
    const query = (queryToSend || inputQuery).trim();
    if (!query || isLoading) return;

    const userMsg = {
      sender: "user",
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery("");
    setIsLoading(true);

    try {
      const res = await fetch("/api/magda/concierge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          sender: "magda",
          text: data.response || "Talebinizi inceledim, işte bulduğum en popüler seçenekler:",
          recommendations: data.recommendations || [],
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "magda",
          text: "Bağlantı esnasında bir hata oluştu. Lütfen tekrar deneyin.",
          recommendations: [],
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 font-sans">
      {/* Floating Action Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="flex items-center gap-2.5 px-5 py-3.5 bg-gradient-to-r from-rose-500 via-pink-500 to-rose-600 text-white font-medium rounded-full shadow-2xl hover:scale-105 active:scale-95 transition-all duration-200 border border-white/20"
        >
          <div className="relative">
            <Sparkles className="w-5 h-5 text-amber-200 animate-pulse" />
            <span className="absolute -top-1 -right-1 flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
          </div>
          <span className="tracking-wide text-sm font-semibold">Magda AI Asistan</span>
        </button>
      )}

      {/* Clean Guest Chat Window */}
      {isOpen && (
        <div className="w-[380px] sm:w-[420px] h-[560px] bg-white rounded-3xl shadow-2xl border border-gray-100 flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-5 duration-200">
          
          {/* Header */}
          <div className="px-5 py-4 bg-gradient-to-r from-rose-500 via-pink-500 to-rose-600 text-white flex items-center justify-between shadow-md">
            <div className="flex items-center gap-2.5">
              <div className="p-2 bg-white/15 rounded-xl backdrop-blur-sm border border-white/20">
                <Bot className="w-5 h-5 text-white" />
              </div>
              <div>
                <div className="flex items-center gap-1.5">
                  <h3 className="text-sm font-bold tracking-tight leading-none">Fatsa Escapes Concierge</h3>
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-400"></span>
                </div>
                <p className="text-[11px] text-white/80 font-normal mt-0.5">Magda-Agent AI Canlı</p>
              </div>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="p-1.5 text-white/80 hover:text-white hover:bg-white/10 rounded-full transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Quick Action Chips */}
          <div className="px-3.5 py-2.5 bg-gray-50/80 border-b border-gray-100 flex gap-1.5 overflow-x-auto scrollbar-none text-[11px]">
            <button
              onClick={() => handleSendMessage("Bodrumda havuzlu villa")}
              className="px-3 py-1 bg-white hover:bg-rose-50 hover:text-rose-600 border border-gray-200 hover:border-rose-300 rounded-full text-gray-700 whitespace-nowrap transition shadow-xs"
            >
              🏖️ Bodrum Villa
            </button>
            <button
              onClick={() => handleSendMessage("Rize dağ kulübesi")}
              className="px-3 py-1 bg-white hover:bg-rose-50 hover:text-rose-600 border border-gray-200 hover:border-rose-300 rounded-full text-gray-700 whitespace-nowrap transition shadow-xs"
            >
              ⛰️ Rize Kulübe
            </button>
            <button
              onClick={() => handleSendMessage("Fatsa deniz kenarı evler")}
              className="px-3 py-1 bg-white hover:bg-rose-50 hover:text-rose-600 border border-gray-200 hover:border-rose-300 rounded-full text-gray-700 whitespace-nowrap transition shadow-xs"
            >
              🌊 Fatsa Sahil
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 p-4 overflow-y-auto space-y-3.5 bg-gray-50/40">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex flex-col ${msg.sender === "user" ? "items-end" : "items-start"}`}
              >
                <div
                  className={`max-w-[88%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                    msg.sender === "user"
                      ? "bg-rose-500 text-white rounded-br-none shadow-sm font-medium"
                      : "bg-white text-gray-800 border border-gray-100 rounded-bl-none shadow-sm"
                  }`}
                >
                  <p className="whitespace-pre-line">{msg.text}</p>
                </div>

                {/* Recommendation Cards */}
                {msg.recommendations && msg.recommendations.length > 0 && (
                  <div className="mt-2.5 space-y-2.5 w-full max-w-[95%]">
                    {msg.recommendations.map((rec) => (
                      <div
                        key={rec.id}
                        className="bg-white p-3 rounded-2xl border border-gray-200/90 shadow-sm hover:border-rose-400 hover:shadow-md transition flex gap-3 items-center cursor-pointer group"
                        onClick={() => onSelectListing && onSelectListing(rec.id)}
                      >
                        <img
                          src={rec.imageUrl}
                          alt={rec.title}
                          className="w-16 h-16 rounded-xl object-cover bg-gray-100 flex-shrink-0"
                          onError={(e) => {
                            e.target.src = "https://images.unsplash.com/photo-1580587771525-78b9dba3b914?auto=format&fit=crop&w=400&q=80";
                          }}
                        />
                        <div className="flex-1 min-w-0">
                          <h4 className="text-[12px] font-bold text-gray-900 truncate group-hover:text-rose-600 transition">
                            {rec.title}
                          </h4>
                          <p className="text-[11px] text-gray-500 flex items-center gap-1 mt-0.5">
                            <MapPin className="w-3 h-3 text-gray-400" /> {rec.city}
                          </p>
                          <div className="flex items-center justify-between mt-1">
                            <span className="text-[12px] font-bold text-gray-900">
                              ₺{Number(rec.pricePerNight).toLocaleString("tr-TR")}{" "}
                              <span className="text-[10px] font-normal text-gray-500">/ gece</span>
                            </span>
                            <span className="text-[11px] font-semibold text-amber-600 flex items-center gap-0.5">
                              <Star className="w-3.5 h-3.5 fill-amber-400 text-amber-400" /> {rec.rating}
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <span className="text-[10px] text-gray-400 mt-1 px-1">{msg.timestamp}</span>
              </div>
            ))}

            {isLoading && (
              <div className="flex items-center gap-2 text-xs text-gray-500 bg-white px-3.5 py-2.5 rounded-2xl border border-gray-100 w-fit shadow-xs">
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-rose-500" />
                <span>Magda uygun evleri arıyor...</span>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Footer */}
          <div className="p-3 bg-white border-t border-gray-100 flex items-center gap-2">
            <input
              type="text"
              value={inputQuery}
              onChange={(e) => setInputQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
              placeholder="Örn: Bodrum'da havuzlu villa..."
              className="flex-1 px-4 py-2.5 text-xs bg-gray-50 border border-gray-200 rounded-2xl focus:outline-none focus:border-rose-500 focus:bg-white transition"
            />
            <button
              onClick={() => handleSendMessage()}
              disabled={isLoading || !inputQuery.trim()}
              className="p-2.5 bg-rose-500 hover:bg-rose-600 disabled:opacity-40 text-white rounded-2xl transition shadow-sm"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>

        </div>
      )}
    </div>
  );
}
