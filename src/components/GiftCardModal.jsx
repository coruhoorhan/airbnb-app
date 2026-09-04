import React, { useState, useEffect } from "react";
import { X, Loader2, Gift, ShoppingCart, Ticket, Copy, Check, CreditCard, User, FileText, Search } from "lucide-react";

function formatDate(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleDateString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function GiftCardModal({ isOpen, onClose, userId }) {
  const [activeTab, setActiveTab] = useState("buy");

  // Buy tab state
  const [purchasedCards, setPurchasedCards] = useState([]);
  const [loadingCards, setLoadingCards] = useState(true);
  const [cardsError, setCardsError] = useState(null);
  const [recipientName, setRecipientName] = useState("");
  const [amount, setAmount] = useState("");
  const [message, setMessage] = useState("");
  const [buying, setBuying] = useState(false);
  const [buyResult, setBuyResult] = useState(null);
  const [buyError, setBuyError] = useState(null);

  // Redeem tab state
  const [code, setCode] = useState("");
  const [cardInfo, setCardInfo] = useState(null);
  const [lookingUp, setLookingUp] = useState(false);
  const [lookupError, setLookupError] = useState(null);
  const [amountToApply, setAmountToApply] = useState("");
  const [redeeming, setRedeeming] = useState(false);
  const [redeemResult, setRedeemResult] = useState(null);
  const [redeemError, setRedeemError] = useState(null);

  // Copy code feedback
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen || !userId) return;
    setActiveTab("buy");
    resetBuyForm();
    resetRedeemForm();
  }, [isOpen, userId]);

  function resetBuyForm() {
    setRecipientName("");
    setAmount("");
    setMessage("");
    setBuyResult(null);
    setBuyError(null);
    setBuying(false);
    fetchPurchasedCards();
  }

  function resetRedeemForm() {
    setCode("");
    setCardInfo(null);
    setLookupError(null);
    setAmountToApply("");
    setRedeemResult(null);
    setRedeemError(null);
  }

  function fetchPurchasedCards() {
    if (!userId) return;
    setLoadingCards(true);
    setCardsError(null);
    fetch(`/api/gift-cards?buyerId=${userId}`)
      .then((r) => r.json())
      .then((res) => {
        if (res.success) {
          setPurchasedCards(res.data || []);
        } else {
          setCardsError(res.error || "Kartlar alinamadi.");
        }
      })
      .catch(() => setCardsError("Sunucu hatasi."))
      .finally(() => setLoadingCards(false));
  }

  function handleBuy() {
    if (!recipientName.trim() || !amount || parseInt(amount, 10) < 50) return;
    setBuying(true);
    setBuyError(null);
    setBuyResult(null);

    fetch("/api/gift-cards", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        buyerId: userId,
        recipientName: recipientName.trim(),
        amount: parseInt(amount, 10),
        message: message.trim() || undefined,
      }),
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.success) {
          setBuyResult(res.data);
        } else {
          setBuyError(res.error || "Hediye karti olusturulamadi.");
        }
      })
      .catch(() => setBuyError("Sunucu hatasi. Lutfen tekrar deneyin."))
      .finally(() => setBuying(false));
  }

  function handleLookup() {
    if (!code.trim()) return;
    setLookingUp(true);
    setLookupError(null);
    setCardInfo(null);
    setRedeemResult(null);
    setRedeemError(null);
    setAmountToApply("");

    fetch(`/api/gift-cards/${code.trim().toUpperCase()}`)
      .then((r) => r.json())
      .then((res) => {
        if (res.success) {
          setCardInfo(res.data);
        } else {
          setLookupError(res.error || "Kart bulunamadi.");
        }
      })
      .catch(() => setLookupError("Sunucu hatasi."))
      .finally(() => setLookingUp(false));
  }

  function handleRedeem() {
    const applyAmt = parseInt(amountToApply, 10);
    if (!cardInfo || !applyAmt || applyAmt < 1) return;
    setRedeeming(true);
    setRedeemError(null);
    setRedeemResult(null);

    fetch("/api/gift-cards/redeem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: cardInfo.code, amountToApply: applyAmt }),
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.success && res.data?.success) {
          setRedeemResult(res.data);
          setCardInfo((prev) =>
            prev ? { ...prev, remainingBalance: res.data.remainingBalance } : prev
          );
          setAmountToApply("");
        } else {
          setRedeemError(res.data?.error || "Kart kullanilamadi.");
        }
      })
      .catch(() => setRedeemError("Sunucu hatasi."))
      .finally(() => setRedeeming(false));
  }

  function handleCopyCode(text) {
    navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (!isOpen) return null;

  const amountNum = parseInt(amount, 10) || 0;
  const canBuy = recipientName.trim().length > 0 && amountNum >= 50 && amountNum <= 5000;
  const applyAmt = parseInt(amountToApply, 10) || 0;
  const canRedeem = cardInfo?.isActive && applyAmt >= 1 && applyAmt <= (cardInfo?.remainingBalance || 0);

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white w-full max-w-lg rounded-3xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-charcoal-border flex items-center justify-between bg-charcoal-bg">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-amber-100 text-amber-600 flex items-center justify-center">
              <Gift className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-charcoal">Hediye Kartlarim</h3>
              <p className="text-[11px] text-charcoal-light font-medium">Hediye kartlarini yonetin</p>
            </div>
          </div>
          <button aria-label="X" onClick={onClose} className="p-2 rounded-full hover:bg-white transition-colors"> <X /> </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-charcoal-border">
          <button
            onClick={() => { setActiveTab("buy"); resetBuyForm(); }}
            className={`flex-1 h-11 text-sm font-bold min-h-[44px] flex items-center justify-center gap-2 transition-colors ${
              activeTab === "buy"
                ? "text-airbnb border-b-2 border-airbnb bg-airbnb/5"
                : "text-charcoal-light hover:text-charcoal hover:bg-charcoal-bg"
            }`}
          >
            <ShoppingCart className="w-4 h-4" />
            Hediye Karti Al
          </button>
          <button
            onClick={() => { setActiveTab("redeem"); resetRedeemForm(); }}
            className={`flex-1 h-11 text-sm font-bold min-h-[44px] flex items-center justify-center gap-2 transition-colors ${
              activeTab === "redeem"
                ? "text-airbnb border-b-2 border-airbnb bg-airbnb/5"
                : "text-charcoal-light hover:text-charcoal hover:bg-charcoal-bg"
            }`}
          >
            <Ticket className="w-4 h-4" />
            Hediye Karti Kullan
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {activeTab === "buy" && (
            <>
              {/* Purchased Cards List */}
              <div>
                <h4 className="font-bold text-xs text-charcoal uppercase tracking-wider mb-2">
                  Gecmis Hediye Kartlarim
                </h4>
                {loadingCards ? (
                  <div className="flex items-center justify-center py-6">
                    <Loader2 className="w-5 h-5 text-airbnb animate-spin" />
                  </div>
                ) : cardsError ? (
                  <p className="text-xs text-red-500 font-medium">{cardsError}</p>
                ) : purchasedCards.length > 0 ? (
                  <div className="max-h-40 overflow-y-auto rounded-2xl border border-charcoal-border divide-y divide-charcoal-border/40">
                    {purchasedCards.map((card, i) => (
                      <div key={card.code || i} className="flex items-center justify-between px-4 py-3 text-xs">
                        <div className="flex items-center gap-2 min-w-0">
                          <div className="w-7 h-7 rounded-full bg-amber-100 text-amber-600 flex items-center justify-center shrink-0">
                            <CreditCard className="w-3.5 h-3.5" />
                          </div>
                          <div className="min-w-0">
                            <p className="font-bold text-charcoal truncate">{card.recipientName || "Alici belirtilmemis"}</p>
                            <p className="text-[10px] text-charcoal-light font-medium">
                              {card.isActive ? "Aktif" : "Kullanildi"} · {formatDate(card.createdAt)}
                            </p>
                          </div>
                        </div>
                        <div className="text-right shrink-0">
                          <p className="font-mono tabular-nums font-bold text-charcoal">
                            ₺{card.remainingBalance.toLocaleString("tr-TR")}
                          </p>
                          <p className="text-[10px] text-charcoal-light">
                            / ₺{card.amount.toLocaleString("tr-TR")}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-6 rounded-2xl border border-dashed border-charcoal-border/60">
                    <div className="w-10 h-10 rounded-full bg-charcoal-bg text-charcoal-light flex items-center justify-center mx-auto mb-2">
                      <Gift className="w-4 h-4" />
                    </div>
                    <p className="text-xs font-bold text-charcoal-light">Henuz hediye karti satin alinmamis</p>
                  </div>
                )}
              </div>

              {/* Buy Form */}
              <div className="rounded-2xl border border-charcoal-border p-4 space-y-3">
                <h4 className="font-bold text-xs text-charcoal uppercase tracking-wider">Yeni Hediye Karti</h4>
                <div className="space-y-3">
                  <div>
                    <label className="text-[11px] font-bold text-charcoal-light mb-1 block">Alici Adi</label>
                    <div className="relative">
                      <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-charcoal-light" />
                      <input
                        type="text"
                        value={recipientName}
                        onChange={(e) => setRecipientName(e.target.value)}
                        placeholder="Alici adi"
                        className="w-full h-11 pl-9 pr-3 rounded-2xl border border-charcoal-border text-sm font-bold text-charcoal focus:outline-none focus:ring-2 focus:ring-amber-400/50 focus:border-amber-400"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-[11px] font-bold text-charcoal-light mb-1 block">Tutar (₺50 - ₺5.000)</label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm font-bold text-charcoal-light">₺</span>
                      <input
                        type="number"
                        min={50}
                        max={5000}
                        value={amount}
                        onChange={(e) => setAmount(e.target.value)}
                        placeholder="50"
                        className="w-full h-11 pl-8 pr-3 rounded-2xl border border-charcoal-border text-sm font-mono font-bold text-charcoal focus:outline-none focus:ring-2 focus:ring-amber-400/50 focus:border-amber-400"
                      />
                    </div>
                    {amountNum > 0 && (amountNum < 50 || amountNum > 5000) && (
                      <p className="text-[11px] text-red-500 font-medium mt-1">Tutar 50 TL ile 5.000 TL arasinda olmalidir</p>
                    )}
                  </div>
                  <div>
                    <label className="text-[11px] font-bold text-charcoal-light mb-1 block">Mesaj (istege bagli)</label>
                    <div className="relative">
                      <FileText className="absolute left-3 top-3 w-4 h-4 text-charcoal-light" />
                      <textarea
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        placeholder="Hediye mesaji..."
                        rows={2}
                        className="w-full pl-9 pr-3 py-2.5 rounded-2xl border border-charcoal-border text-sm font-medium text-charcoal focus:outline-none focus:ring-2 focus:ring-amber-400/50 focus:border-amber-400 resize-none"
                      />
                    </div>
                  </div>
                </div>
                <button
                  onClick={handleBuy}
                  disabled={!canBuy || buying}
                  className="w-full h-11 bg-airbnb text-white rounded-2xl font-bold text-sm min-h-[44px] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-airbnb-hover transition-colors flex items-center justify-center gap-2"
                >
                  {buying ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Gift className="w-4 h-4" />
                  )}
                  {buying ? "Olusturuluyor..." : `Hediye Karti Al (₺${amountNum.toLocaleString("tr-TR")})`}
                </button>
                {buyError && (
                  <p className="text-sm text-red-500 font-medium">{buyError}</p>
                )}
                {buyResult && (
                  <div className="rounded-2xl bg-emerald-50 border border-emerald-200 p-4 space-y-2">
                    <p className="text-xs font-bold text-emerald-700 uppercase tracking-wider flex items-center gap-1.5">
                      <Check className="w-3.5 h-3.5" />
                      Hediye Karti Olusturuldu
                    </p>
                    <div className="bg-charcoal-dark rounded-xl px-4 py-3 flex items-center justify-between">
                      <code className="text-lg font-mono font-black text-emerald-400 tracking-widest select-all">
                        {buyResult.code}
                      </code>
                      <button
                        onClick={() => handleCopyCode(buyResult.code)}
                        className="p-2 rounded-full hover:bg-white/10 transition-colors"
                        title="Kodu kopyala"
                      >
                        {copied ? (
                          <Check className="w-4 h-4 text-emerald-400" />
                        ) : (
                          <Copy className="w-4 h-4 text-emerald-400" />
                        )}
                      </button>
                    </div>
                    <p className="text-sm font-bold text-emerald-700 text-center">
                      ₺{buyResult.amount.toLocaleString("tr-TR")} degerinde hediye karti · {buyResult.recipientName}
                    </p>
                  </div>
                )}
              </div>
            </>
          )}

          {activeTab === "redeem" && (
            <>
              {/* Code Lookup */}
              <div className="rounded-2xl border border-charcoal-border p-4 space-y-3">
                <h4 className="font-bold text-xs text-charcoal uppercase tracking-wider">Kart Kodu</h4>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={code}
                    onChange={(e) => setCode(e.target.value.toUpperCase())}
                    placeholder="HEDIVE-KODU"
                    className="flex-1 h-11 px-3 rounded-2xl border border-charcoal-border text-sm font-mono font-bold text-charcoal uppercase tracking-widest focus:outline-none focus:ring-2 focus:ring-amber-400/50 focus:border-amber-400"
                  />
                  <button
                    onClick={handleLookup}
                    disabled={!code.trim() || lookingUp}
                    className="px-5 h-11 bg-amber-500 text-white rounded-2xl font-bold text-sm min-h-[44px] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-amber-600 transition-colors flex items-center gap-2"
                  >
                    {lookingUp ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Search className="w-4 h-4" />
                    )}
                    Sorgula
                  </button>
                </div>
                {lookupError && (
                  <p className="text-sm text-red-500 font-medium">{lookupError}</p>
                )}
              </div>

              {/* Card Info */}
              {cardInfo && (
                <div className="rounded-2xl bg-gradient-to-br from-amber-50 to-amber-100/60 border border-amber-200/60 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-bold text-amber-700 uppercase tracking-wider">Kart Bilgisi</p>
                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                        cardInfo.isActive
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-red-100 text-red-600"
                      }`}
                    >
                      {cardInfo.isActive ? "Aktif" : "Kullanildi"}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-xs text-charcoal-light font-medium">Kart Degeri</p>
                      <p className="text-2xl font-mono tabular-nums font-black text-amber-600">
                        ₺{cardInfo.amount.toLocaleString("tr-TR")}
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-charcoal-light font-medium">Kalan Bakiye</p>
                      <p className="text-2xl font-mono tabular-nums font-black text-emerald-600">
                        ₺{cardInfo.remainingBalance.toLocaleString("tr-TR")}
                      </p>
                    </div>
                  </div>
                  {cardInfo.recipientName && (
                    <p className="text-xs text-charcoal-light font-medium">
                      Alici: <span className="font-bold text-charcoal">{cardInfo.recipientName}</span>
                    </p>
                  )}
                </div>
              )}

              {/* Redeem Form */}
              {cardInfo?.isActive && (
                <div className="rounded-2xl border border-charcoal-border p-4 space-y-3">
                  <h4 className="font-bold text-xs text-charcoal uppercase tracking-wider">Kart Kullan</h4>
                  <div>
                    <label className="text-[11px] font-bold text-charcoal-light mb-1 block">
                      Uygulanacak Tutar (maks. ₺{cardInfo.remainingBalance.toLocaleString("tr-TR")})
                    </label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm font-bold text-charcoal-light">₺</span>
                      <input
                        type="number"
                        min={1}
                        max={cardInfo.remainingBalance}
                        value={amountToApply}
                        onChange={(e) => setAmountToApply(e.target.value)}
                        placeholder={String(cardInfo.remainingBalance)}
                        className="w-full h-11 pl-8 pr-3 rounded-2xl border border-charcoal-border text-sm font-mono font-bold text-charcoal focus:outline-none focus:ring-2 focus:ring-emerald-400/50 focus:border-emerald-400"
                      />
                    </div>
                  </div>
                  <button
                    onClick={handleRedeem}
                    disabled={!canRedeem || redeeming}
                    className="w-full h-11 bg-emerald-600 text-white rounded-2xl font-bold text-sm min-h-[44px] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-emerald-700 transition-colors flex items-center justify-center gap-2"
                  >
                    {redeeming ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <Check className="w-4 h-4" />
                    )}
                    {redeeming ? "Kullaniliyor..." : "Karti Kullan"}
                  </button>
                  {redeemError && (
                    <p className="text-sm text-red-500 font-medium">{redeemError}</p>
                  )}
                  {redeemResult && (
                    <div className="rounded-2xl bg-emerald-50 border border-emerald-200 p-4 space-y-1">
                      <p className="text-xs font-bold text-emerald-700 uppercase tracking-wider flex items-center gap-1.5">
                        <Check className="w-3.5 h-3.5" />
                        Kart Basariyla Kullanildi
                      </p>
                      <p className="text-sm font-bold text-emerald-700">
                        ₺{redeemResult.amountUsed.toLocaleString("tr-TR")} kullanildi
                      </p>
                      <p className="text-xs text-emerald-600 font-medium">
                        Kalan bakiye: ₺{redeemResult.remainingBalance.toLocaleString("tr-TR")}
                      </p>
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
