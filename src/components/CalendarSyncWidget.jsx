import React, { useState } from "react";
import { Calendar, Download, RefreshCw, Link as LinkIcon, CheckCircle2, AlertCircle, Trash2, Loader2 } from "lucide-react";

export function CalendarSyncWidget({ listing, onSyncUpdated }) {
  const [icalUrl, setIcalUrl] = useState(listing?.calendarSyncUrl || "");
  const [syncing, setSyncing] = useState(false);
  const [statusMsg, setStatusMsg] = useState(null);

  const icsExportUrl = `/api/calendar/${listing.id}.ics`;

  const handleSaveAndSync = async () => {
    if (!icalUrl.trim()) return;
    try {
      setSyncing(true);
      setStatusMsg(null);
      const res = await fetch(`/api/calendar/${listing.id}/sync`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ icalUrl: icalUrl.trim() })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error || "Senkronizasyon başarısız oldu.");
      setStatusMsg({ type: "success", text: `Harici takvim senkronize edildi (${data.data.syncedCount} yeni engel).` });
      if (onSyncUpdated) onSyncUpdated();
    } catch (err) {
      setStatusMsg({ type: "error", text: err.message });
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col gap-6 animate-in fade-in duration-200">
      <div>
        <h4 className="text-base font-extrabold text-charcoal flex items-center gap-2">
          <Calendar className="w-5 h-5 text-coral" /> iCal Takvim Senkronizasyonu
        </h4>
        <p className="text-xs text-charcoal-light mt-1">
          Airbnb, Booking.com ve Google Takvim ile çift yönlü müsaitlik senkronizasyonu kurun.
        </p>
      </div>

      {/* Export iCal Feed */}
      <div className="p-4 rounded-2xl bg-gray-50 border border-gray-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <span className="text-xs font-bold text-charcoal block">Bu İlanın iCal Takvim Akışı</span>
          <span className="text-[11px] font-mono text-charcoal-light break-all">{window?.location?.origin || ""}{icsExportUrl}</span>
        </div>
        <a
          href={icsExportUrl}
          download={`${listing.id}.ics`}
          className="px-4 py-2 bg-white border border-gray-200 rounded-xl text-xs font-bold text-charcoal hover:bg-gray-100 flex items-center gap-1.5 shrink-0"
        >
          <Download className="w-3.5 h-3.5 text-coral" /> .ICS İndir
        </a>
      </div>

      {/* Import External iCal */}
      <div className="flex flex-col gap-3">
        <label className="text-xs font-bold text-charcoal">Harici Takvim URL'si (Airbnb / Booking.com / Google)</label>
        <div className="flex flex-col sm:flex-row gap-2">
          <div className="relative flex-1">
            <LinkIcon className="w-4 h-4 text-charcoal-light absolute left-3 top-3" />
            <input
              type="url"
              placeholder="https://example.com/calendar.ics"
              value={icalUrl}
              onChange={(e) => setIcalUrl(e.target.value)}
              className="w-full pl-9 pr-3 py-2.5 rounded-xl border border-charcoal-border text-xs focus:outline-none focus:ring-2 focus:ring-coral/20 font-mono"
            />
          </div>
          <button
            onClick={handleSaveAndSync}
            disabled={syncing || !icalUrl.trim()}
            className="px-5 py-2.5 bg-charcoal text-white rounded-xl text-xs font-bold hover:bg-black transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {syncing ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4 text-coral" />}
            <span>Senkronize Et</span>
          </button>
        </div>
      </div>

      {statusMsg && (
        <div className={`p-3 rounded-xl text-xs font-medium flex items-center gap-2 ${
          statusMsg.type === "success" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-red-50 text-red-600 border border-red-200"
        }`}>
          {statusMsg.type === "success" ? <CheckCircle2 className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />}
          <span>{statusMsg.text}</span>
        </div>
      )}
    </div>
  );
}
export default CalendarSyncWidget;
