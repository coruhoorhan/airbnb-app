import React, { useState, useEffect } from "react";
import { X, Loader2, Gift, TrendingUp, TrendingDown, Sparkles } from "lucide-react";

function formatDate(ts) {
  if (!ts) return "";
  return new Date(ts).toLocaleDateString("tr-TR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

export function LoyaltyDashboard({ isOpen, onClose, userId }) {
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [points, setPoints] = useState("");
  const [redeeming, setRedeeming] = useState(false);
  const [redeemResult, setRedeemResult] = useState(null);
  const [redeemError, setRedeemError] = useState(null);

  useEffect(() => {
    if (!isOpen || !userId) return;
    setLoading(true);
    setError(null);
    setRedeemResult(null);
    setRedeemError(null);
    setPoints("");

    fetch(`/api/loyalty/${userId}`)
      .then((r) => r.json())
      .then((res) => {
        if (res.success) {
          setData(res.data);
        } else {
          setError(res.error || "Puan bilgileri alinamadi.");
        }
      })
      .catch(() => setError("Sunucu hatasi. Lutfen tekrar deneyin."))
      .finally(() => setLoading(false));
  }, [isOpen, userId]);

  if (!isOpen) return null;

  const pointsNum = parseInt(points, 10) || 0;
  const discount = pointsNum * 0.1; // 10 kuruş indirim = ₺0.1 per point
  const canRedeem = pointsNum >= 1000 && data && data.balance >= pointsNum;

  function handleRedeem() {
    if (!canRedeem || redeeming) return;
    setRedeeming(true);
    setRedeemError(null);
    setRedeemResult(null);

    fetch("/api/loyalty/redeem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ userId, points: pointsNum }),
    })
      .then((r) => r.json())
      .then((res) => {
        if (res.success && res.data?.success) {
          setRedeemResult(res.data);
          setData((prev) =>
            prev
              ? { ...prev, balance: res.data.newBalance, transactions: [{ id: "new", type: "redeem", amount: -pointsNum, description: "Puan kullanimi", createdAt: new Date().toISOString() }, ...prev.transactions] }
              : prev
          );
          setPoints("");
        } else {
          setRedeemError(res.data?.error || "Kupon olusturulamadi.");
        }
      })
      .catch(() => setRedeemError("Sunucu hatasi. Lutfen tekrar deneyin."))
      .finally(() => setRedeeming(false));
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-white w-full max-w-lg rounded-3xl shadow-2xl flex flex-col max-h-[90vh] overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-charcoal-border flex items-center justify-between bg-charcoal-bg">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-emerald-100 text-emerald-600 flex items-center justify-center">
              <Gift className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-charcoal">Sadakat Puanlarim</h3>
              <p className="text-[11px] text-charcoal-light font-medium">Puanlarinizi yonetin</p>
            </div>
          </div>
          <button aria-label="X" onClick={onClose} className="p-2 rounded-full hover:bg-white transition-colors"> <X /> </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <Loader2 className="w-8 h-8 text-airbnb animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-16 flex flex-col items-center gap-3">
              <div className="w-14 h-14 rounded-full bg-red-50 text-red-500 flex items-center justify-center">
                <X className="w-6 h-6" />
              </div>
              <p className="text-sm font-bold text-red-500">{error}</p>
              <button
                onClick={onClose}
                className="mt-2 px-6 py-2.5 bg-airbnb text-white rounded-2xl font-bold text-sm min-h-[44px]"
              >
                Kapat
              </button>
            </div>
          ) : data ? (
            <>
              {/* Tier Card */}
              {data.tier && (
                <div className="rounded-2xl border border-charcoal-border p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <p className="text-xs font-bold text-charcoal uppercase tracking-wider">Sadakat Seviyesi</p>
                    <span className={`inline-block text-[11px] font-black px-3 py-1 rounded-full ${data.tier.tier.bg} ${data.tier.tier.color}`}>
                      {data.tier.tier.name}
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-xs font-medium text-charcoal-light">
                    <span>Seviye ilerlemesi</span>
                    <span className="font-mono font-bold text-charcoal">
                      {data.tier.progress}%
                    </span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-charcoal-bg overflow-hidden">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-amber-400 via-emerald-400 to-purple-500 transition-all duration-700"
                      style={{ width: `${data.tier.progress}%` }}
                    />
                  </div>
                  {data.tier.nextTier ? (
                    <p className="text-[11px] text-charcoal-light font-medium">
                      <span className="font-bold text-charcoal">{data.tier.nextTier.name}</span> seviyesine ulaşmak için{" "}
                      <span className="font-mono font-bold text-charcoal">{data.tier.pointsToNext.toLocaleString("tr-TR")}</span> puan daha kazanın.
                    </p>
                  ) : (
                    <p className="text-[11px] text-charcoal-light font-medium">En yüksek seviyedesiniz. 🏆</p>
                  )}
                </div>
              )}
              {/* Balance Card */}
              <div className="bg-gradient-to-br from-emerald-50 to-emerald-100/60 rounded-2xl p-5 border border-emerald-200/60">
                <p className="text-xs font-bold text-emerald-700 uppercase tracking-wider">Kullanilabilir Puan</p>
                <p className="text-4xl font-mono tabular-nums font-black text-emerald-600 mt-1">
                  {data.balance.toLocaleString("tr-TR")}
                </p>
                <div className="flex gap-4 mt-3 text-xs text-emerald-800">
                  <span className="flex items-center gap-1">
                    <TrendingUp className="w-3.5 h-3.5" />
                    Kazanilan: {data.lifetimeEarned.toLocaleString("tr-TR")}
                  </span>
                  <span className="flex items-center gap-1">
                    <TrendingDown className="w-3.5 h-3.5" />
                    Kullanilan: {data.lifetimeRedeemed.toLocaleString("tr-TR")}
                  </span>
                </div>
              </div>

              {/* Redeem Section */}
              <div className="rounded-2xl border border-charcoal-border p-4 space-y-3">
                <h4 className="font-bold text-xs text-charcoal uppercase tracking-wider">Puan Kullan</h4>
                <div className="flex gap-2">
                  <input
                    type="number"
                    min={1000}
                    step={1000}
                    max={data.balance}
                    value={points}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === "" || parseInt(val, 10) >= 0) setPoints(val);
                    }}
                    placeholder="Puan miktari"
                    className="flex-1 h-11 px-3 rounded-2xl border border-charcoal-border text-sm font-bold text-charcoal focus:outline-none focus:ring-2 focus:ring-emerald-400/50 focus:border-emerald-400"
                  />
                </div>
                {pointsNum > 0 && (
                  <p className="text-sm font-bold text-emerald-600 tabular-nums">
                    {pointsNum.toLocaleString("tr-TR")} puan = ₺{discount.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} indirim
                  </p>
                )}
                <button
                  onClick={handleRedeem}
                  disabled={!canRedeem || redeeming}
                  className="w-full h-11 bg-airbnb text-white rounded-2xl font-bold text-sm min-h-[44px] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-airbnb-hover transition-colors flex items-center justify-center gap-2"
                >
                  {redeeming ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4" />
                  )}
                  {redeeming ? "Kupon olusturuluyor..." : "Kupon Olustur"}
                </button>
                {redeemError && (
                  <p className="text-sm text-red-500 font-medium">{redeemError}</p>
                )}
                {redeemResult && (
                  <div className="rounded-2xl bg-emerald-50 border border-emerald-200 p-4 space-y-2">
                    <p className="text-xs font-bold text-emerald-700 uppercase tracking-wider">Kupon Olusturuldu</p>
                    <div className="bg-charcoal-dark rounded-xl px-4 py-3 text-center">
                      <code className="text-lg font-mono font-black text-emerald-400 tracking-widest select-all">
                        {redeemResult.couponCode}
                      </code>
                    </div>
                    <p className="text-sm font-bold text-emerald-700 text-center">
                      -₺{redeemResult.discountAmount.toLocaleString("tr-TR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} indirim kuponu hazir
                    </p>
                  </div>
                )}
              </div>

              {/* Transaction History */}
              <div>
                <h4 className="font-bold text-xs text-charcoal uppercase tracking-wider mb-2">Puan Hareketleri</h4>
                {data.transactions && data.transactions.length > 0 ? (
                  <div className="max-h-48 overflow-y-auto rounded-2xl border border-charcoal-border divide-y divide-charcoal-border/40">
                    {data.transactions.map((t) => (
                      <div key={t.id} className="flex items-center justify-between px-4 py-3 text-xs">
                        <div className="flex items-center gap-2 min-w-0">
                          <span
                            className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 ${
                              t.type === "earn" || t.amount > 0
                                ? "bg-emerald-100 text-emerald-600"
                                : "bg-amber-100 text-amber-600"
                            }`}
                          >
                            {t.type === "earn" || t.amount > 0 ? (
                              <TrendingUp className="w-3.5 h-3.5" />
                            ) : (
                              <TrendingDown className="w-3.5 h-3.5" />
                            )}
                          </span>
                          <div className="min-w-0">
                            <p className="font-bold text-charcoal truncate">
                              {t.description || (t.type === "earn" ? "Puan kazanimi" : "Puan kullanimi")}
                            </p>
                            <p className="text-[10px] text-charcoal-light font-medium">{formatDate(t.createdAt)}</p>
                          </div>
                        </div>
                        <span
                          className={`font-mono tabular-nums font-bold shrink-0 ${
                            t.type === "earn" || t.amount > 0 ? "text-emerald-600" : "text-amber-600"
                          }`}
                        >
                          {t.type === "earn" || t.amount > 0 ? "+" : ""}
                          {Math.abs(t.amount).toLocaleString("tr-TR")}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 rounded-2xl border border-dashed border-charcoal-border/60">
                    <div className="w-12 h-12 rounded-full bg-charcoal-bg text-charcoal-light flex items-center justify-center mx-auto mb-2">
                      <Gift className="w-5 h-5" />
                    </div>
                    <p className="text-sm font-bold text-charcoal-light">Henuz puan hareketiniz bulunmuyor</p>
                    <p className="text-[11px] text-charcoal-light/70 mt-1">Rezervasyon yaparak puan kazanmaya baslayin</p>
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}