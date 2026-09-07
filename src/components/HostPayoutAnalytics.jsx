import React, { useState, useEffect } from "react";
import { 
  DollarSign, 
  TrendingUp, 
  Calendar, 
  Clock, 
  Building2, 
  CheckCircle2, 
  AlertCircle, 
  ArrowUpRight, 
  Loader2 
} from "lucide-react";

export function HostPayoutAnalytics({ hostId, token }) {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    async function fetchAnalytics() {
      if (!hostId) {
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        const query = `
          query GetHostRevenue($hostId: ID!) {
            hostRevenueAnalytics(hostId: $hostId) {
              hostId
              totalEarnings
              pendingPayoutsTotal
              averageOccupancyRate
              earningsByMonth {
                month
                earnings
                bookingsCount
              }
              listingBreakdown {
                listingId
                title
                totalEarnings
                bookingsCount
              }
              pendingPayouts {
                bookingId
                amount
                payoutDate
                guestName
              }
            }
          }
        `;
        const res = await fetch("/graphql", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { "Authorization": `Bearer ${token}` } : {})
          },
          body: JSON.stringify({ query, variables: { hostId } })
        });
        const result = await res.json();
        if (result.errors && result.errors.length > 0) {
          throw new Error(result.errors[0].message);
        }
        setAnalytics(result.data?.hostRevenueAnalytics || null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }
    fetchAnalytics();
  }, [hostId, token]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12 text-charcoal-light">
        <Loader2 className="w-8 h-8 animate-spin text-coral mb-3" />
        <p className="text-sm font-medium">Gelir ve Hakediş Analitiği Yükleniyor...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-3xl text-red-600 flex items-center gap-3">
        <AlertCircle className="w-6 h-6 shrink-0" />
        <div>
          <h4 className="font-bold text-sm">Analitik Verisi Alınamadı</h4>
          <p className="text-xs">{error}</p>
        </div>
      </div>
    );
  }

  const {
    totalEarnings = 0,
    pendingPayoutsTotal = 0,
    averageOccupancyRate = 0,
    earningsByMonth = [],
    listingBreakdown = [],
    pendingPayouts = []
  } = analytics || {};

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-200">
      {/* Top Metrics Bento */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-charcoal-light">Toplam Kazanç</span>
            <div className="w-10 h-10 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
              <DollarSign className="w-5 h-5" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-black text-charcoal">₺{totalEarnings.toLocaleString("tr-TR")}</div>
            <div className="text-xs text-emerald-600 font-bold flex items-center gap-1 mt-1">
              <TrendingUp className="w-3.5 h-3.5" /> Onaylı rezervasyon net geliri
            </div>
          </div>
        </div>

        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-charcoal-light">Bekleyen Hakedişler</span>
            <div className="w-10 h-10 rounded-2xl bg-amber-50 text-amber-600 flex items-center justify-center">
              <Clock className="w-5 h-5" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-black text-charcoal">₺{pendingPayoutsTotal.toLocaleString("tr-TR")}</div>
            <div className="text-xs text-amber-600 font-bold flex items-center gap-1 mt-1">
              <Calendar className="w-3.5 h-3.5" /> İleriki tarihlerde aktarılacak
            </div>
          </div>
        </div>

        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col justify-between">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-charcoal-light">Ortalama Doluluk Oranı</span>
            <div className="w-10 h-10 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
              <Building2 className="w-5 h-5" />
            </div>
          </div>
          <div>
            <div className="text-2xl font-black text-charcoal">%{averageOccupancyRate}</div>
            <div className="text-xs text-indigo-600 font-bold flex items-center gap-1 mt-1">
              <ArrowUpRight className="w-3.5 h-3.5" /> Son 30 günlük portföy performansı
            </div>
          </div>
        </div>
      </div>

      {/* Monthly Earnings & Breakdown Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Monthly Earnings Chart/List */}
        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs">
          <h4 className="text-base font-extrabold text-charcoal mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-coral" /> Aylık Kazanç Dağılımı
          </h4>
          {earningsByMonth.length === 0 ? (
            <p className="text-xs text-charcoal-light py-8 text-center">Henüz aylık gelir kaydı bulunmuyor.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {earningsByMonth.map((item, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 rounded-2xl bg-gray-50 border border-gray-100">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-xl bg-white border border-gray-200 flex items-center justify-center text-xs font-bold text-charcoal">
                      {idx + 1}
                    </div>
                    <div>
                      <div className="text-sm font-bold text-charcoal">{item.month}</div>
                      <div className="text-xs text-charcoal-light">{item.bookingsCount} rezervasyon</div>
                    </div>
                  </div>
                  <div className="text-sm font-black text-charcoal">
                    ₺{item.earnings.toLocaleString("tr-TR")}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Listing Revenue Breakdown */}
        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs">
          <h4 className="text-base font-extrabold text-charcoal mb-4 flex items-center gap-2">
            <Building2 className="w-5 h-5 text-indigo-600" /> İlan Başına Gelir Dağılımı
          </h4>
          {listingBreakdown.length === 0 ? (
            <p className="text-xs text-charcoal-light py-8 text-center">İlan kaydı bulunamadı.</p>
          ) : (
            <div className="flex flex-col gap-3">
              {listingBreakdown.map((item) => (
                <div key={item.listingId} className="flex items-center justify-between p-3 rounded-2xl bg-gray-50 border border-gray-100">
                  <div className="truncate max-w-[200px]">
                    <div className="text-sm font-bold text-charcoal truncate">{item.title}</div>
                    <div className="text-xs text-charcoal-light">{item.bookingsCount} tamamlanan rezervasyon</div>
                  </div>
                  <div className="text-sm font-black text-emerald-600">
                    ₺{item.totalEarnings.toLocaleString("tr-TR")}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Pending Payouts Table */}
      <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs">
        <h4 className="text-base font-extrabold text-charcoal mb-4 flex items-center gap-2">
          <Clock className="w-5 h-5 text-amber-500" /> Bekleyen Hakediş Tablosu
        </h4>
        {pendingPayouts.length === 0 ? (
          <p className="text-xs text-charcoal-light py-8 text-center">Bekleyen hakediş ödemesi bulunmuyor.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-gray-100 text-charcoal-light uppercase font-bold">
                  <th className="py-2.5 px-3">Rezervasyon ID</th>
                  <th className="py-2.5 px-3">Misafir</th>
                  <th className="py-2.5 px-3">Hakediş Tutarı</th>
                  <th className="py-2.5 px-3">Tahmini Ödeme Tarihi</th>
                  <th className="py-2.5 px-3">Durum</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {pendingPayouts.map((p) => (
                  <tr key={p.bookingId} className="hover:bg-gray-50/50">
                    <td className="py-3 px-3 font-mono font-bold text-charcoal">{p.bookingId}</td>
                    <td className="py-3 px-3 font-medium text-charcoal">{p.guestName}</td>
                    <td className="py-3 px-3 font-bold text-emerald-600">₺{p.amount.toLocaleString("tr-TR")}</td>
                    <td className="py-3 px-3 text-charcoal-light">{p.payoutDate}</td>
                    <td className="py-3 px-3">
                      <span className="px-2.5 py-1 rounded-full text-[10px] font-bold bg-amber-50 text-amber-700 border border-amber-200">
                        Beklemede
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
export default HostPayoutAnalytics;
