import React, { useState, useEffect, useMemo } from "react";
import { 
  DollarSign, 
  CalendarCheck, 
  Users, 
  Star, 
  Plus, 
  Check, 
  X, 
  Building2, 
  TrendingUp, 
  Sparkles, 
  BarChart3, 
  CreditCard, 
  Tag, 
  ShieldCheck, 
  Activity, 
  Edit3, 
  Trash2, 
  Eye, 
  EyeOff, 
  CheckCircle2, 
  AlertCircle, 
  Loader2, 
  Percent, 
  Database, 
  Server, 
  Clock,
  Cpu,
  Wrench,
  Github,
  Copy,
  Terminal,
  FileCode2,
  RefreshCw,
  Flame
} from "lucide-react";

export function HostDashboard({ listings = [], bookings = [], onOpenRent, onConfirmBooking, onDeclineBooking }) {
  const [activeTab, setActiveTab] = useState("analytics"); // analytics | listings | bookings | coupons | users | system | guardian
  const [analyticsData, setAnalyticsData] = useState(null);
  const [allCoupons, setAllCoupons] = useState([]);
  const [allUsers, setAllUsers] = useState([]);
  const [healthData, setHealthData] = useState(null);
  const [guardianIssues, setGuardianIssues] = useState([]);
  const [isLoadingData, setIsLoadingData] = useState(false);
  const [isScanningGuardian, setIsScanningGuardian] = useState(false);

  // Listing Inline Edit State
  const [editingListingId, setEditingListingId] = useState(null);
  const [editPrice, setEditPrice] = useState("");
  const [editCleaning, setEditCleaning] = useState("");

  // Create Coupon Modal State
  const [isCreatingCoupon, setIsCreatingCoupon] = useState(false);
  const [newCouponCode, setNewCouponCode] = useState("");
  const [newCouponType, setNewCouponType] = useState("percentage");
  const [newCouponValue, setNewCouponValue] = useState(20);
  const [newCouponMin, setNewCouponMin] = useState(3000);
  const [newCouponExpiry, setNewCouponExpiry] = useState("2026-12-31");
  const [couponError, setCouponError] = useState("");

  // GitHub Issue Modal State
  const [githubModalIssue, setGithubModalIssue] = useState(null);
  const [githubMarkdown, setGithubMarkdown] = useState("");
  const [copiedGithub, setCopiedGithub] = useState(false);

  // Notification Toast
  const [toastMessage, setToastMessage] = useState("");

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(""), 3500);
  };

  const fetchAdminData = async () => {
    setIsLoadingData(true);
    try {
      const [analyticsRes, couponsRes, usersRes, healthRes, guardianRes] = await Promise.all([
        fetch("/api/admin/analytics").then((r) => r.json()),
        fetch("/api/coupons").then((r) => r.json()),
        fetch("/api/users").then((r) => r.json()),
        fetch("/api/health").then((r) => r.json()),
        fetch("/api/admin/guardian/issues").then((r) => r.json())
      ]);

      if (analyticsRes.success) setAnalyticsData(analyticsRes.data);
      if (couponsRes.success) setAllCoupons(couponsRes.data);
      if (usersRes.success) setAllUsers(usersRes.data);
      if (healthRes.status === "ok") setHealthData(healthRes);
      if (guardianRes.success) setGuardianIssues(guardianRes.data);
    } catch (err) {
      console.error("Error loading admin data:", err);
    } finally {
      setIsLoadingData(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  // Guardian Operations
  const handleTriggerGuardianScan = async () => {
    setIsScanningGuardian(true);
    try {
      const res = await fetch("/api/admin/guardian/scan", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        showToast(`AI Guardian Taraması Tamamlandı! Bulunan Sorun: ${data.data.totalIssuesFound}`);
        fetchAdminData();
      }
    } catch (err) {
      alert("Guardian tarama hatası: " + err.message);
    } finally {
      setIsScanningGuardian(false);
    }
  };

  const handleAutoHealIssue = async (issueId) => {
    try {
      const res = await fetch(`/api/admin/guardian/heal/${issueId}`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        showToast(`Otomatik Onarıldı: ${data.data.actionTaken}`);
        fetchAdminData();
      }
    } catch (err) {
      alert("Onarım hatası: " + err.message);
    }
  };

  const handleDismissIssue = async (issueId) => {
    try {
      const res = await fetch(`/api/admin/guardian/dismiss/${issueId}`, { method: "POST" });
      const data = await res.json();
      if (data.success) {
        showToast("Sorun gözardı edildi.");
        fetchAdminData();
      }
    } catch (err) {
      alert("Hata: " + err.message);
    }
  };

  const handleOpenGithubExport = async (issue) => {
    setGithubModalIssue(issue);
    setCopiedGithub(false);
    try {
      const res = await fetch(`/api/admin/guardian/export-github/${issue.id}`);
      const data = await res.json();
      if (data.success) {
        setGithubMarkdown(data.markdown);
      }
    } catch (err) {
      setGithubMarkdown("GitHub Markdown yüklenirken hata oluştu.");
    }
  };

  const handleCopyGithubMarkdown = () => {
    navigator.clipboard.writeText(githubMarkdown);
    setCopiedGithub(true);
    showToast("GitHub Issue Markdown panoya kopyalandı!");
    setTimeout(() => setCopiedGithub(false), 2500);
  };

  // Listing Operations
  const handleToggleListing = async (listingId) => {
    try {
      const res = await fetch(`/api/listings/${listingId}/toggle-status`, { method: "PUT" });
      const data = await res.json();
      if (data.success) {
        showToast(`İlan durumu güncellendi: ${data.data.isPublished ? "Yayında" : "Askıda"}`);
        fetchAdminData();
      }
    } catch (err) {
      alert("Hata: " + err.message);
    }
  };

  const handleStartEditListing = (l) => {
    setEditingListingId(l.id);
    setEditPrice(l.pricePerNight);
    setEditCleaning(l.cleaningFee);
  };

  const handleSaveListingPrice = async (listingId) => {
    try {
      const res = await fetch(`/api/listings/${listingId}/quick-update`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pricePerNight: editPrice, cleaningFee: editCleaning })
      });
      const data = await res.json();
      if (data.success) {
        setEditingListingId(null);
        showToast("İlan fiyatı başarıyla güncellendi.");
        fetchAdminData();
      }
    } catch (err) {
      alert("Fiyat güncellenirken hata: " + err.message);
    }
  };

  const handleDeleteListing = async (listingId) => {
    if (!window.confirm("Bu ilanı silmek istediğinize emin misiniz?")) return;
    try {
      const res = await fetch(`/api/listings/${listingId}`, { method: "DELETE" });
      const data = await res.json();
      if (data.success) {
        showToast("İlan başarıyla silindi.");
        fetchAdminData();
      }
    } catch (err) {
      alert("Hata: " + err.message);
    }
  };

  // Coupon Operations
  const handleCreateCoupon = async (e) => {
    e.preventDefault();
    setCouponError("");
    try {
      const res = await fetch("/api/coupons", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: newCouponCode.trim().toUpperCase(),
          discountType: newCouponType,
          discountValue: Number(newCouponValue),
          minAmount: Number(newCouponMin),
          expiryDate: newCouponExpiry,
          isActive: 1
        })
      });
      const data = await res.json();
      if (data.success) {
        setIsCreatingCoupon(false);
        setNewCouponCode("");
        showToast(`Kupon oluşturuldu: ${data.data.code}`);
        fetchAdminData();
      } else {
        setCouponError(data.error || "Kupon oluşturulamadı.");
      }
    } catch (err) {
      setCouponError(err.message);
    }
  };

  const handleToggleCoupon = async (code) => {
    try {
      const res = await fetch(`/api/coupons/${code}/toggle`, { method: "PUT" });
      const data = await res.json();
      if (data.success) {
        showToast(`Kupon ${data.data.isActive ? "Aktifleştirildi" : "Pasife Alındı"}`);
        fetchAdminData();
      }
    } catch (err) {
      alert("Hata: " + err.message);
    }
  };

  const handleDeleteCoupon = async (code) => {
    if (!window.confirm(`${code} kuponunu silmek istediğinize emin misiniz?`)) return;
    try {
      const res = await fetch(`/api/coupons/${code}`, { method: "DELETE" });
      const data = await res.json();
      if (data.success) {
        showToast("Kupon silindi.");
        fetchAdminData();
      }
    } catch (err) {
      alert("Hata: " + err.message);
    }
  };

  // User Operations
  const handleToggleUserRole = async (userId, currentIsHost) => {
    try {
      const res = await fetch(`/api/users/${userId}/role`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ isHost: !currentIsHost })
      });
      const data = await res.json();
      if (data.success) {
        showToast(`Kullanıcı rolü güncellendi: ${data.data.isHost ? "Ev Sahibi" : "Misafir"}`);
        fetchAdminData();
      }
    } catch (err) {
      alert("Hata: " + err.message);
    }
  };

  const openGuardianIssuesCount = guardianIssues.filter((i) => i.status === "open").length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex flex-col gap-8 animate-in fade-in duration-300">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 bg-charcoal text-white text-xs font-bold px-4 py-3 rounded-2xl shadow-2xl flex items-center gap-2 border border-charcoal-border animate-in slide-in-from-bottom-5">
          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* GitHub Issue Export Modal */}
      {githubModalIssue && (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto animate-in fade-in">
          <div className="bg-white border border-charcoal-border rounded-3xl max-w-2xl w-full shadow-2xl overflow-hidden flex flex-col my-8">
            <div className="px-6 py-4 bg-charcoal text-white flex items-center justify-between border-b border-charcoal-border">
              <div className="flex items-center gap-2">
                <Github className="w-5 h-5" />
                <h3 className="font-extrabold text-sm">GitHub Issue Raporu Oluşturuldu</h3>
              </div>
              <button 
                onClick={() => setGithubModalIssue(null)}
                className="p-1 text-white/70 hover:text-white rounded-full transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 flex flex-col gap-4">
              <p className="text-xs text-charcoal-light">
                Bu Markdown çıktısını doğrudan GitHub deponuzdaki **New Issue** sekmesine yapıştırabilir veya Veyyon'a otonom çözüm için iletebilirsiniz.
              </p>

              <pre className="p-4 bg-charcoal-bg border border-charcoal-border rounded-2xl text-xs font-mono text-charcoal overflow-x-auto max-h-80 whitespace-pre-wrap">
                {githubMarkdown}
              </pre>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  onClick={() => setGithubModalIssue(null)}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-charcoal border border-charcoal-border hover:bg-charcoal-bg"
                >
                  Kapat
                </button>
                <button
                  onClick={handleCopyGithubMarkdown}
                  className="px-5 py-2 rounded-xl text-xs font-bold text-white bg-charcoal hover:bg-black flex items-center gap-1.5 shadow-md"
                >
                  {copiedGithub ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                  <span>{copiedGithub ? "Kopyalandı!" : "Markdown'ı Panoya Kopyala"}</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-airbnb/10 text-airbnb text-xs font-bold mb-1 border border-airbnb/20">
            <Sparkles className="w-3.5 h-3.5" />
            Super Admin & Operations Center
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-charcoal tracking-tight">
            Yönetim ve Operasyon Merkezi
          </h1>
          <p className="text-sm text-charcoal-light mt-0.5">
            Finansal gelir analitiği, 7/24 AI Guardian nöbetçisi, iyzico ödemeleri ve kampanya yönetimi.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchAdminData}
            disabled={isLoadingData}
            className="px-3.5 py-2.5 bg-white border border-charcoal-border hover:bg-charcoal-bg text-charcoal text-xs font-bold rounded-xl transition-colors flex items-center gap-1.5 shadow-xs"
          >
            <Activity className={`w-3.5 h-3.5 ${isLoadingData ? "animate-spin text-airbnb" : "text-charcoal-light"}`} />
            <span>Yenile</span>
          </button>
          <button
            onClick={onOpenRent}
            className="px-4 py-2.5 bg-airbnb hover:bg-airbnb-dark text-white rounded-xl font-bold text-xs shadow-md transition-all flex items-center gap-1.5 active:scale-95"
          >
            <Plus className="w-4 h-4" />
            <span>Yeni İlan Yayınla</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 border-b border-charcoal-border">
        {[
          { id: "analytics", label: "Finans & Gelir", icon: BarChart3, badge: "Canlı" },
          { id: "guardian", label: "7/24 AI Guardian", icon: Cpu, badge: "Nöbetçi", alert: openGuardianIssuesCount },
          { id: "listings", label: "İlan & Fiyat Yönetimi", icon: Building2, count: listings.length },
          { id: "bookings", label: "Rezervasyon & iyzico", icon: CreditCard, count: bookings.length },
          { id: "coupons", label: "Kupon & Kampanya", icon: Tag, count: allCoupons.length },
          { id: "users", label: "Kullanıcılar & Roller", icon: Users, count: allUsers.length },
          { id: "system", label: "Sistem & SQLite WAL", icon: Database, badge: "10.0.2.1" }
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 rounded-xl font-bold text-xs flex items-center gap-2 transition-all shrink-0 ${
                isActive 
                  ? "bg-charcoal text-white shadow-sm" 
                  : "bg-white text-charcoal hover:bg-charcoal-bg border border-charcoal-border/70"
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
              {tab.alert !== undefined && tab.alert > 0 && (
                <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-rose-500 text-white font-extrabold animate-pulse">
                  {tab.alert}
                </span>
              )}
              {tab.count !== undefined && (
                <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${isActive ? "bg-white/20 text-white" : "bg-charcoal-bg text-charcoal-light font-bold"}`}>
                  {tab.count}
                </span>
              )}
              {tab.badge && !tab.alert && (
                <span className={`text-[9px] px-1.5 py-0.2 rounded-full font-extrabold uppercase ${isActive ? "bg-emerald-400 text-charcoal" : "bg-emerald-100 text-emerald-800"}`}>
                  {tab.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* TAB: 7/24 AI GUARDIAN & WATCHDOG */}
      {activeTab === "guardian" && (
        <div className="flex flex-col gap-6 animate-in fade-in duration-200">
          {/* Guardian Live Status Hero Card */}
          <div className="bg-gradient-to-r from-charcoal via-charcoal-dark to-black text-white rounded-3xl p-6 shadow-xl flex flex-col sm:flex-row sm:items-center justify-between gap-6 border border-charcoal-border">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-2xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0 border border-emerald-500/30">
                <Cpu className="w-6 h-6 animate-pulse" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-extrabold tracking-tight">7/24 Otonom Sistem Nöbetçisi & Kod Denetçisi</h3>
                  <span className="flex h-2.5 w-2.5 relative">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
                  </span>
                </div>
                <p className="text-xs text-white/70 mt-1 max-w-xl">
                  SQLite veritabanı bütünlüğünü, şüpheli fiyat anomalilerini, iyzico ödeme mutabakatını ve kod kalitesini 7/24 periyodik olarak otonom denetler ve self-healing ile onarır.
                </p>
              </div>
            </div>

            <button
              onClick={handleTriggerGuardianScan}
              disabled={isScanningGuardian}
              className="px-5 py-3 bg-emerald-500 hover:bg-emerald-600 text-charcoal-dark font-extrabold text-xs rounded-xl shadow-lg transition-all flex items-center gap-2 self-start sm:self-center shrink-0 active:scale-95 disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isScanningGuardian ? "animate-spin" : ""}`} />
              <span>{isScanningGuardian ? "Otonom Taranıyor..." : "Anlık Otonom Tara"}</span>
            </button>
          </div>

          {/* Guardian Metric Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-charcoal-border rounded-3xl p-5 shadow-xs flex flex-col justify-between gap-2">
              <span className="text-xs font-bold text-charcoal-light">Nöbetçi Durumu</span>
              <div className="text-xl font-extrabold text-emerald-600 flex items-center gap-1.5">
                <ShieldCheck className="w-5 h-5" />
                <span>CANLI & AKTİF</span>
              </div>
              <p className="text-[11px] text-charcoal-light">15 dakikada bir otomatik tarama</p>
            </div>

            <div className="bg-white border border-charcoal-border rounded-3xl p-5 shadow-xs flex flex-col justify-between gap-2">
              <span className="text-xs font-bold text-charcoal-light">Açık Tespitler</span>
              <div className={`text-2xl font-extrabold ${openGuardianIssuesCount > 0 ? "text-amber-600" : "text-emerald-600"}`}>
                {openGuardianIssuesCount} Adet
              </div>
              <p className="text-[11px] text-charcoal-light">İnceleme bekleyen uyarılar</p>
            </div>

            <div className="bg-white border border-charcoal-border rounded-3xl p-5 shadow-xs flex flex-col justify-between gap-2">
              <span className="text-xs font-bold text-charcoal-light">Otomatik Onarılan (Self-Healed)</span>
              <div className="text-2xl font-extrabold text-blue-600">
                {guardianIssues.filter((i) => i.status === "healed").length} Çözüm
              </div>
              <p className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" />
                Sistem müdahalesi gerekmeden çözüldü
              </p>
            </div>

            <div className="bg-white border border-charcoal-border rounded-3xl p-5 shadow-xs flex flex-col justify-between gap-2">
              <span className="text-xs font-bold text-charcoal-light">Sistem Sağlık Skoru</span>
              <div className="text-2xl font-extrabold text-charcoal">
                %{openGuardianIssuesCount === 0 ? "100" : "96.8"}
              </div>
              <p className="text-[11px] text-charcoal-light">10.0.2.1 / SQLite WAL Engine</p>
            </div>
          </div>

          {/* Issues Feed Table / Cards */}
          <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col gap-5">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-extrabold text-base text-charcoal">AI Guardian Tespit ve Öneri Beslemesi</h4>
                <p className="text-xs text-charcoal-light">Tespit edilen sorunları inceleyebilir, tek tıkla otomatik onarabilir veya GitHub Issue formatında dışa aktarabilirsiniz.</p>
              </div>
              <span className="text-xs font-bold text-charcoal bg-charcoal-bg px-3 py-1 rounded-full border border-charcoal-border">
                Toplam {guardianIssues.length} Rapor
              </span>
            </div>

            {guardianIssues.length === 0 ? (
              <div className="py-12 text-center flex flex-col items-center gap-3 bg-emerald-50/50 rounded-2xl border border-emerald-200">
                <div className="w-12 h-12 bg-emerald-100 text-emerald-600 rounded-full flex items-center justify-center">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <h5 className="font-bold text-sm text-emerald-900">Harika! Hiçbir Sorun veya Hata Bulunmuyor.</h5>
                <p className="text-xs text-emerald-700 max-w-md">
                  7/24 AI Guardian tüm veritabanı bütünlüğünü, ödeme mutabakatlarını ve kupon mantığını taradı. Sistem %100 sağlıklı çalışıyor.
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                {guardianIssues.map((issue) => {
                  const isHealed = issue.status === "healed";
                  return (
                    <div 
                      key={issue.id}
                      className={`p-4 rounded-2xl border transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-4 ${
                        isHealed 
                          ? "bg-charcoal-bg/40 border-charcoal-border/50 opacity-75" 
                          : issue.severity === "high" || issue.severity === "critical"
                            ? "bg-rose-50/40 border-rose-200"
                            : "bg-amber-50/40 border-amber-200"
                      }`}
                    >
                      <div className="flex items-start gap-3">
                        <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 mt-0.5 ${
                          isHealed ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
                        }`}>
                          {isHealed ? <Check className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
                        </div>

                        <div>
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-bold text-sm text-charcoal">{issue.title}</span>
                            <span className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded ${
                              issue.severity === "critical" || issue.severity === "high"
                                ? "bg-rose-100 text-rose-800"
                                : "bg-amber-100 text-amber-800"
                            }`}>
                              {issue.severity}
                            </span>
                            <span className="text-[10px] font-bold bg-white text-charcoal px-2 py-0.5 rounded border border-charcoal-border">
                              {issue.type}
                            </span>
                            {isHealed && (
                              <span className="text-[10px] font-extrabold bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">
                              <Check className="w-3 h-3 inline-block mr-0.5" />OTOMATİK ONARILDI
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-charcoal-light mt-1">{issue.description}</p>
                          <div className="text-[11px] text-charcoal font-semibold mt-1 flex items-center gap-1">
                            <Wrench className="w-3 h-3 text-airbnb" />
                            <span>Öneri: {issue.suggestion}</span>
                          </div>
                        </div>
                      </div>

                      {/* Action Buttons */}
                      <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                        {!isHealed && (
                          <button
                            onClick={() => handleAutoHealIssue(issue.id)}
                            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition-colors flex items-center gap-1 shadow-xs"
                          >
                            <Wrench className="w-3.5 h-3.5" />
                            <span>Otomatik Onar</span>
                          </button>
                        )}
                        <button
                          onClick={() => handleOpenGithubExport(issue)}
                          className="px-3 py-1.5 bg-white hover:bg-charcoal-bg text-charcoal rounded-xl text-xs font-bold border border-charcoal-border transition-colors flex items-center gap-1"
                          title="GitHub Issue Markdown Olarak Dışa Aktar"
                        >
                          <Github className="w-3.5 h-3.5" />
                          <span>Issue Raporu</span>
                        </button>
                        {!isHealed && (
                          <button
                            onClick={() => handleDismissIssue(issue.id)}
                            className="p-1.5 text-charcoal-light hover:text-charcoal hover:bg-white rounded-xl transition-colors"
                            title="Gözardı Et"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 1: FINANS & GELİR ANALİTİĞİ */}
      {activeTab === "analytics" && (
        <div className="flex flex-col gap-6 animate-in fade-in duration-200">
          {/* KPI Bento Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="bg-white border border-charcoal-border rounded-3xl p-5 shadow-xs flex flex-col justify-between gap-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-charcoal-light">Toplam Brüt Hacim (GMV)</span>
                <div className="w-8 h-8 rounded-xl bg-emerald-50 text-emerald-600 flex items-center justify-center">
                  <DollarSign className="w-4 h-4" />
                </div>
              </div>
              <div>
                <div className="text-2xl font-extrabold text-charcoal tracking-tight">
                  ₺{(analyticsData?.financials?.grossVolume || 0).toLocaleString("tr-TR")}
                </div>
                <p className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1 mt-1">
                  <TrendingUp className="w-3 h-3" />
                  Toplam onaylanan konaklama cirosu
                </p>
              </div>
            </div>

            <div className="bg-white border border-charcoal-border rounded-3xl p-5 shadow-xs flex flex-col justify-between gap-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-charcoal-light">Platform Hizmet Kazancı</span>
                <div className="w-8 h-8 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                  <Percent className="w-4 h-4" />
                </div>
              </div>
              <div>
                <div className="text-2xl font-extrabold text-blue-600 tracking-tight">
                  ₺{(analyticsData?.financials?.platformRevenue || 0).toLocaleString("tr-TR")}
                </div>
                <p className="text-[11px] text-charcoal-light font-medium mt-1">
                  %5 Airbnb komisyon geliri
                </p>
              </div>
            </div>

            <div className="bg-white border border-charcoal-border rounded-3xl p-5 shadow-xs flex flex-col justify-between gap-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-charcoal-light">iyzico Tahsilat Tutarı</span>
                <div className="w-8 h-8 rounded-xl bg-indigo-50 text-indigo-600 flex items-center justify-center">
                  <CreditCard className="w-4 h-4" />
                </div>
              </div>
              <div>
                <div className="text-2xl font-extrabold text-indigo-600 tracking-tight">
                  ₺{(analyticsData?.financials?.totalCollectedViaIyzico || 0).toLocaleString("tr-TR")}
                </div>
                <p className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1 mt-1">
                  <ShieldCheck className="w-3 h-3" />
                  3D Secure ile tahsil edildi
                </p>
              </div>
            </div>

            <div className="bg-white border border-charcoal-border rounded-3xl p-5 shadow-xs flex flex-col justify-between gap-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-charcoal-light">Kupon Tasarruf Hacmi</span>
                <div className="w-8 h-8 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center">
                  <Tag className="w-4 h-4" />
                </div>
              </div>
              <div>
                <div className="text-2xl font-extrabold text-rose-600 tracking-tight">
                  ₺{(analyticsData?.financials?.totalCouponDiscount || 0).toLocaleString("tr-TR")}
                </div>
                <p className="text-[11px] text-charcoal-light font-medium mt-1">
                  Misafirlere sağlanan promosyon
                </p>
              </div>
            </div>
          </div>

          {/* Revenue Trends Chart & Occupancy Bento */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Monthly Trend Visualizer */}
            <div className="lg:col-span-2 bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col justify-between gap-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-base font-extrabold text-charcoal">Aylık Brüt Hacim & Gelir Trendi</h3>
                  <p className="text-xs text-charcoal-light">Son 4 ayın konaklama ve komisyon performansı</p>
                </div>
                <span className="text-xs font-bold text-emerald-600 bg-emerald-50 px-2.5 py-1 rounded-full border border-emerald-200">
                  +38% Büyüme
                </span>
              </div>

              {/* Bar Chart Representation */}
              <div className="grid grid-cols-4 gap-4 items-end pt-6 pb-2 border-b border-charcoal-border/50">
                {(analyticsData?.monthlyTrend || [
                  { month: "May", gmv: 34000, revenue: 3400, bookings: 4 },
                  { month: "Haz", gmv: 58000, revenue: 5800, bookings: 7 },
                  { month: "Tem", gmv: 92000, revenue: 9200, bookings: 12 },
                  { month: "Ağu", gmv: 115000, revenue: 11500, bookings: 15 }
                ]).map((bar) => {
                  const maxGmv = 120000;
                  const heightPercent = Math.min(100, Math.max(20, Math.round((bar.gmv / maxGmv) * 100)));
                  return (
                    <div key={bar.month} className="flex flex-col items-center gap-2 group">
                      <div className="text-[11px] font-bold text-charcoal opacity-0 group-hover:opacity-100 transition-opacity">
                        ₺{bar.gmv.toLocaleString("tr-TR")}
                      </div>
                      <div className="w-full bg-charcoal-bg rounded-xl p-1 flex items-end justify-center h-36">
                        <div 
                          style={{ height: `${heightPercent}%` }}
                          className="w-full bg-gradient-to-t from-airbnb to-rose-400 rounded-lg group-hover:from-airbnb-dark group-hover:to-rose-500 transition-all shadow-sm flex items-start justify-center pt-1"
                        >
                          <span className="text-[9px] font-extrabold text-white">
                            {bar.bookings} Rez.
                          </span>
                        </div>
                      </div>
                      <span className="text-xs font-bold text-charcoal">{bar.month} 2026</span>
                    </div>
                  );
                })}
              </div>

              <div className="flex items-center justify-between text-xs text-charcoal-light">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 bg-airbnb rounded-sm" />
                    <span>Brüt Konaklama Hacmi</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <div className="w-3 h-3 bg-charcoal-bg rounded-sm border border-charcoal-border" />
                    <span>Boş Kapasite</span>
                  </div>
                </div>
                <span className="font-bold text-charcoal">Fatsa / Ordu Bölgesi</span>
              </div>
            </div>

            {/* Performance Metrics Bento */}
            <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col justify-between gap-6">
              <div>
                <h3 className="text-base font-extrabold text-charcoal">Doluluk & Ortalama Sepet</h3>
                <p className="text-xs text-charcoal-light">Aktif portföy verimlilik skorları</p>
              </div>

              <div className="flex flex-col gap-4">
                <div className="bg-charcoal-bg/70 rounded-2xl p-4 border border-charcoal-border/70 flex flex-col gap-2">
                  <div className="flex justify-between items-center text-xs font-bold">
                    <span className="text-charcoal">Ortalama Doluluk Oranı</span>
                    <span className="text-airbnb font-extrabold text-sm">{analyticsData?.performance?.occupancyRate || 68}%</span>
                  </div>
                  <div className="w-full h-2.5 bg-white rounded-full overflow-hidden border border-charcoal-border/50">
                    <div 
                      style={{ width: `${analyticsData?.performance?.occupancyRate || 68}%` }}
                      className="h-full bg-airbnb rounded-full"
                    />
                  </div>
                </div>

                <div className="bg-charcoal-bg/70 rounded-2xl p-4 border border-charcoal-border/70 flex justify-between items-center">
                  <div>
                    <span className="text-xs font-bold text-charcoal block">Ortalama Rezervasyon</span>
                    <span className="text-[11px] text-charcoal-light">Sepet Başı Tutar</span>
                  </div>
                  <div className="text-lg font-black text-charcoal">
                    ₺{(analyticsData?.performance?.avgBookingValue || 7450).toLocaleString("tr-TR")}
                  </div>
                </div>

                <div className="bg-charcoal-bg/70 rounded-2xl p-4 border border-charcoal-border/70 flex justify-between items-center">
                  <div>
                    <span className="text-xs font-bold text-charcoal block">Ev Sahibi Hakedişi</span>
                    <span className="text-[11px] text-charcoal-light">Ödenecek Net Tutar</span>
                  </div>
                  <div className="text-lg font-black text-emerald-600">
                    ₺{(analyticsData?.financials?.totalHostPayout || 0).toLocaleString("tr-TR")}
                  </div>
                </div>
              </div>

              <div className="text-[11px] text-charcoal-light flex items-center gap-1.5 pt-2 border-t border-charcoal-border/40">
                <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                <span>Tüm hesaplamalar anlık SQLite WAL verisiyle eşzamanlıdır.</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: İLAN & FİYAT YÖNETİMİ */}
      {activeTab === "listings" && (
        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col gap-6 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-extrabold text-charcoal">İlan ve Fiyat Moderasyonu</h3>
              <p className="text-xs text-charcoal-light">Tüm portföyü yönetin, fiyatları anlık değiştirin veya yayından kaldırın.</p>
            </div>
            <button
              onClick={onOpenRent}
              className="px-4 py-2.5 bg-charcoal text-white rounded-xl font-bold text-xs hover:bg-black transition-colors flex items-center gap-1.5 self-start"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Yeni İlan Ekle</span>
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-charcoal-border text-charcoal-light font-bold">
                  <th className="py-3 px-3">İlan Bilgisi</th>
                  <th className="py-3 px-3">Kategori</th>
                  <th className="py-3 px-3">Gecelik Fiyat</th>
                  <th className="py-3 px-3">Temizlik</th>
                  <th className="py-3 px-3">Puan</th>
                  <th className="py-3 px-3">Durum</th>
                  <th className="py-3 px-3 text-right">İşlemler</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-border/60">
                {listings.map((item) => {
                  const isEditing = editingListingId === item.id;
                  return (
                    <tr key={item.id} className="hover:bg-charcoal-bg/40 transition-colors">
                      <td className="py-3.5 px-3">
                        <div className="flex items-center gap-3">
                          <img 
                            src={item.images?.[0] || "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?w=300"} 
                            alt={item.title}
                            className="w-12 h-12 rounded-xl object-cover border border-charcoal-border"
                          />
                          <div>
                            <div className="font-bold text-charcoal text-sm">{item.title}</div>
                            <div className="text-[11px] text-charcoal-light">{item.city}, {item.country}</div>
                          </div>
                        </div>
                      </td>

                      <td className="py-3.5 px-3">
                        <span className="px-2.5 py-1 rounded-lg bg-charcoal-bg font-semibold text-charcoal">
                          {item.category}
                        </span>
                      </td>

                      <td className="py-3.5 px-3 font-bold">
                        {isEditing ? (
                          <input 
                            type="number"
                            value={editPrice}
                            onChange={(e) => setEditPrice(e.target.value)}
                            className="w-24 px-2 py-1 border border-airbnb rounded-lg text-xs font-bold text-charcoal"
                          />
                        ) : (
                          <span className="text-charcoal font-extrabold">₺{item.pricePerNight?.toLocaleString("tr-TR")}</span>
                        )}
                      </td>

                      <td className="py-3.5 px-3 font-semibold text-charcoal-light">
                        {isEditing ? (
                          <input 
                            type="number"
                            value={editCleaning}
                            onChange={(e) => setEditCleaning(e.target.value)}
                            className="w-20 px-2 py-1 border border-airbnb rounded-lg text-xs font-bold text-charcoal"
                          />
                        ) : (
                          <span>₺{item.cleaningFee?.toLocaleString("tr-TR")}</span>
                        )}
                      </td>

                      <td className="py-3.5 px-3">
                        <div className="flex items-center gap-1 font-bold text-charcoal">
                          <Star className="w-3.5 h-3.5 fill-charcoal text-charcoal" />
                          <span>{item.avgRating > 0 ? item.avgRating.toFixed(2) : "5.0"}</span>
                          <span className="text-[10px] text-charcoal-light">({item.reviewCount || 0})</span>
                        </div>
                      </td>

                      <td className="py-3.5 px-3">
                        <button
                          onClick={() => handleToggleListing(item.id)}
                          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold border transition-colors ${
                            item.isPublished 
                              ? "bg-emerald-50 text-emerald-700 border-emerald-300 hover:bg-emerald-100" 
                              : "bg-rose-50 text-rose-700 border-rose-300 hover:bg-rose-100"
                          }`}
                        >
                          {item.isPublished ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
                          <span>{item.isPublished ? "Yayında" : "Askıda"}</span>
                        </button>
                      </td>

                      <td className="py-3.5 px-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {isEditing ? (
                            <>
                              <button
                                onClick={() => handleSaveListingPrice(item.id)}
                                className="px-2.5 py-1 bg-emerald-600 text-white rounded-lg font-bold text-[11px] hover:bg-emerald-700"
                              >
                                Kaydet
                              </button>
                              <button
                                onClick={() => setEditingListingId(null)}
                                className="px-2 py-1 text-charcoal hover:bg-charcoal-bg rounded-lg text-[11px]"
                              >
                                İptal
                              </button>
                            </>
                          ) : (
                            <button
                              onClick={() => handleStartEditListing(item)}
                              className="p-1.5 text-charcoal-light hover:text-charcoal hover:bg-charcoal-bg rounded-lg transition-colors"
                              title="Hızlı Fiyat Düzenle"
                            >
                              <Edit3 className="w-4 h-4" />
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteListing(item.id)}
                            className="p-1.5 text-rose-500 hover:text-rose-700 hover:bg-rose-50 rounded-lg transition-colors"
                            title="İlanı Sil"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: REZERVASYON & IYZICO ÖDEMELERİ */}
      {activeTab === "bookings" && (
        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col gap-6 animate-in fade-in duration-200">
          <div>
            <h3 className="text-lg font-extrabold text-charcoal">Rezervasyon & iyzico Ödeme Hareketleri</h3>
            <p className="text-xs text-charcoal-light">Tüm misafir talepleri, 3D Secure ödeme durumları ve onay süreçleri.</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-charcoal-border text-charcoal-light font-bold">
                  <th className="py-3 px-3">Rezervasyon Kodu</th>
                  <th className="py-3 px-3">İlan & Misafir</th>
                  <th className="py-3 px-3">Tarihler</th>
                  <th className="py-3 px-3">Ödenen Tutar</th>
                  <th className="py-3 px-3">Kupon</th>
                  <th className="py-3 px-3">iyzico Ödeme Durumu</th>
                  <th className="py-3 px-3 text-right">Aksiyon</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-border/60">
                {bookings.map((b) => (
                  <tr key={b.id} className="hover:bg-charcoal-bg/40 transition-colors">
                    <td className="py-3.5 px-3 font-mono font-bold text-charcoal">
                      {b.id}
                    </td>

                    <td className="py-3.5 px-3">
                      <div className="font-bold text-charcoal">{b.listingId}</div>
                      <div className="text-[11px] text-charcoal-light">{b.guestId} ({b.numGuests} misafir)</div>
                    </td>

                    <td className="py-3.5 px-3 font-medium text-charcoal">
                      <div className="flex items-center gap-1 font-bold">
                        <CalendarCheck className="w-3.5 h-3.5 text-airbnb" />
                        <span>{b.checkIn} → {b.checkOut}</span>
                      </div>
                    </td>

                    <td className="py-3.5 px-3 font-extrabold text-airbnb text-sm">
                      ₺{b.totalPrice?.toLocaleString("tr-TR")}
                    </td>

                    <td className="py-3.5 px-3">
                      {b.couponCode ? (
                        <span className="px-2 py-0.5 rounded-md bg-emerald-50 text-emerald-700 font-extrabold text-[10px] border border-emerald-200">
                          {b.couponCode} (-₺{b.discountAmount})
                        </span>
                      ) : (
                        <span className="text-charcoal-light font-medium">-</span>
                      )}
                    </td>

                    <td className="py-3.5 px-3">
                      {b.paymentStatus === "paid" ? (
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-50 text-blue-800 text-[11px] font-bold border border-blue-200">
                          <ShieldCheck className="w-3 h-3 text-blue-600" />
                          <span>Ödendi (#{b.paymentId || "iyzico"})</span>
                        </div>
                      ) : (
                        <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-50 text-amber-800 text-[11px] font-bold border border-amber-200">
                          <Clock className="w-3 h-3 text-amber-600" />
                          <span>Ödeme Bekleniyor</span>
                        </div>
                      )}
                    </td>

                    <td className="py-3.5 px-3 text-right">
                      {b.status === "pending" ? (
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => onConfirmBooking && onConfirmBooking(b.id)}
                            className="px-2.5 py-1 bg-emerald-600 text-white rounded-lg font-bold text-[11px] hover:bg-emerald-700"
                          >
                            Onayla
                          </button>
                          <button
                            onClick={() => onDeclineBooking && onDeclineBooking(b.id)}
                            className="px-2.5 py-1 bg-rose-50 text-rose-700 border border-rose-200 rounded-lg font-bold text-[11px] hover:bg-rose-100"
                          >
                            Reddet
                          </button>
                        </div>
                      ) : (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 font-extrabold text-[10px]">
                          {b.status === "confirmed" ? "Onaylandı" : b.status}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 4: KUPON & KAMPANYA YÖNETİCİSİ */}
      {activeTab === "coupons" && (
        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col gap-6 animate-in fade-in duration-200">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-extrabold text-charcoal">Kupon ve Promosyon Motoru</h3>
              <p className="text-xs text-charcoal-light">İndirim kodları oluşturun, kullanım kotalarını ve limitleri yönetin.</p>
            </div>
            <button
              onClick={() => setIsCreatingCoupon(true)}
              className="px-4 py-2.5 bg-airbnb hover:bg-airbnb-dark text-white rounded-xl font-bold text-xs shadow-md transition-all flex items-center gap-1.5 self-start"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Yeni Kupon Oluştur</span>
            </button>
          </div>

          {/* Create Coupon Modal */}
          {isCreatingCoupon && (
            <div className="bg-charcoal-bg border border-charcoal-border rounded-2xl p-5 flex flex-col gap-4 animate-in zoom-in-95 duration-200">
              <div className="flex items-center justify-between">
                <h4 className="font-extrabold text-sm text-charcoal flex items-center gap-1.5">
                  <Tag className="w-4 h-4 text-airbnb" />
                  Yeni Promosyon Kuponu Tanımla
                </h4>
                <button onClick={() => setIsCreatingCoupon(false)} className="text-charcoal-light hover:text-charcoal">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <form onSubmit={handleCreateCoupon} className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-extrabold text-charcoal uppercase">KUPON KODU</label>
                  <input 
                    type="text"
                    placeholder="Örn: YAZ2026"
                    value={newCouponCode}
                    onChange={(e) => setNewCouponCode(e.target.value.toUpperCase())}
                    className="px-3 py-2 bg-white border border-charcoal-border rounded-xl text-xs font-bold text-charcoal uppercase outline-none focus:border-airbnb"
                    required
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-extrabold text-charcoal uppercase">İNDİRİM TÜRÜ</label>
                  <select
                    value={newCouponType}
                    onChange={(e) => setNewCouponType(e.target.value)}
                    className="px-3 py-2 bg-white border border-charcoal-border rounded-xl text-xs font-bold text-charcoal outline-none focus:border-airbnb"
                  >
                    <option value="percentage">% Yüzdelik İndirim</option>
                    <option value="fixed">₺ Sabit Tutar İndirimi</option>
                  </select>
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-extrabold text-charcoal uppercase">DEĞER ({newCouponType === "percentage" ? "%" : "₺"})</label>
                  <input 
                    type="number"
                    value={newCouponValue}
                    onChange={(e) => setNewCouponValue(e.target.value)}
                    className="px-3 py-2 bg-white border border-charcoal-border rounded-xl text-xs font-bold text-charcoal outline-none focus:border-airbnb"
                    required
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-extrabold text-charcoal uppercase">MİN. SEPET (₺)</label>
                  <input 
                    type="number"
                    value={newCouponMin}
                    onChange={(e) => setNewCouponMin(e.target.value)}
                    className="px-3 py-2 bg-white border border-charcoal-border rounded-xl text-xs font-bold text-charcoal outline-none focus:border-airbnb"
                    required
                  />
                </div>

                <div className="flex flex-col gap-1">
                  <label className="text-[10px] font-extrabold text-charcoal uppercase">SON KULLANMA</label>
                  <input 
                    type="date"
                    value={newCouponExpiry}
                    onChange={(e) => setNewCouponExpiry(e.target.value)}
                    className="px-3 py-2 bg-white border border-charcoal-border rounded-xl text-xs font-bold text-charcoal outline-none focus:border-airbnb"
                    required
                  />
                </div>

                {couponError && (
                  <div className="sm:col-span-2 lg:col-span-5 text-xs text-rose-600 font-bold">
                    {couponError}
                  </div>
                )}

                <div className="sm:col-span-2 lg:col-span-5 flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsCreatingCoupon(false)}
                    className="px-3 py-1.5 text-xs font-bold text-charcoal hover:bg-white rounded-xl border border-charcoal-border"
                  >
                    Vazgeç
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-1.5 bg-airbnb text-white text-xs font-bold rounded-xl hover:bg-airbnb-dark shadow-sm"
                  >
                    Kuponu Kaydet
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Coupons Table */}
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-charcoal-border text-charcoal-light font-bold">
                  <th className="py-3 px-3">Kupon Kodu</th>
                  <th className="py-3 px-3">İndirim Oranı/Tutarı</th>
                  <th className="py-3 px-3">Min. Sepet</th>
                  <th className="py-3 px-3">Son Kullanma</th>
                  <th className="py-3 px-3">Kullanım Sayısı</th>
                  <th className="py-3 px-3">Durum</th>
                  <th className="py-3 px-3 text-right">İşlemler</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-border/60">
                {allCoupons.map((c) => (
                  <tr key={c.code} className="hover:bg-charcoal-bg/40 transition-colors">
                    <td className="py-3.5 px-3 font-mono font-extrabold text-charcoal text-sm">
                      {c.code}
                    </td>
                    <td className="py-3.5 px-3 font-bold text-airbnb">
                      {c.discountType === "percentage" ? `%${c.discountValue} İndirim` : `₺${c.discountValue} Sabit İndirim`}
                    </td>
                    <td className="py-3.5 px-3 font-semibold text-charcoal">
                      ₺{c.minAmount?.toLocaleString("tr-TR")}
                    </td>
                    <td className="py-3.5 px-3 font-medium text-charcoal-light">
                      {c.expiryDate}
                    </td>
                    <td className="py-3.5 px-3 font-bold text-charcoal">
                      {c.usageCount} kez kullanıldı
                    </td>
                    <td className="py-3.5 px-3">
                      <button
                        onClick={() => handleToggleCoupon(c.code)}
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold border transition-colors ${
                          c.isActive 
                            ? "bg-emerald-50 text-emerald-700 border-emerald-300 hover:bg-emerald-100" 
                            : "bg-rose-50 text-rose-700 border-rose-300 hover:bg-rose-100"
                        }`}
                      >
                        {c.isActive ? "Aktif" : "Pasif"}
                      </button>
                    </td>
                    <td className="py-3.5 px-3 text-right">
                      <button
                        onClick={() => handleDeleteCoupon(c.code)}
                        className="p-1.5 text-rose-500 hover:text-rose-700 hover:bg-rose-50 rounded-lg transition-colors"
                        title="Kuponu Sil"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: KULLANICI & ROL YÖNETİMİ */}
      {activeTab === "users" && (
        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col gap-6 animate-in fade-in duration-200">
          <div>
            <h3 className="text-lg font-extrabold text-charcoal">Kullanıcı ve Rol Yönetimi</h3>
            <p className="text-xs text-charcoal-light">Sistemdeki tüm kayıtlı misafir ve ev sahiplerini inceleyin, rolleri düzenleyin.</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-charcoal-border text-charcoal-light font-bold">
                  <th className="py-3 px-3">Kullanıcı</th>
                  <th className="py-3 px-3">E-posta</th>
                  <th className="py-3 px-3">Telefon</th>
                  <th className="py-3 px-3">İlan Sayısı</th>
                  <th className="py-3 px-3">Rezervasyon</th>
                  <th className="py-3 px-3">Sistem Rolü</th>
                  <th className="py-3 px-3 text-right">Rol Değiştir</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-charcoal-border/60">
                {allUsers.map((u) => (
                  <tr key={u.id} className="hover:bg-charcoal-bg/40 transition-colors">
                    <td className="py-3.5 px-3">
                      <div className="flex items-center gap-2.5">
                        <img 
                          src={u.avatarUrl || "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100"} 
                          alt={u.name}
                          className="w-9 h-9 rounded-full object-cover border border-charcoal-border"
                        />
                        <div>
                          <div className="font-bold text-charcoal text-sm">{u.name}</div>
                          <div className="text-[10px] text-charcoal-light font-mono">{u.id}</div>
                        </div>
                      </div>
                    </td>

                    <td className="py-3.5 px-3 font-medium text-charcoal">
                      {u.email}
                    </td>

                    <td className="py-3.5 px-3 text-charcoal-light font-mono">
                      {u.phone || "+90 535 000 00 00"}
                    </td>

                    <td className="py-3.5 px-3 font-bold text-charcoal">
                      {u.listingCount || 0} İlan
                    </td>

                    <td className="py-3.5 px-3 font-bold text-charcoal">
                      {u.bookingCount || 0} Rezervasyon
                    </td>

                    <td className="py-3.5 px-3">
                      <span className={`px-2.5 py-1 rounded-full text-[10px] font-extrabold border ${
                        u.isHost 
                          ? "bg-purple-50 text-purple-700 border-purple-200" 
                          : "bg-charcoal-bg text-charcoal border-charcoal-border"
                      }`}>
                        {u.isHost ? "Ev Sahibi (Host)" : "Misafir (Guest)"}
                      </span>
                    </td>

                    <td className="py-3.5 px-3 text-right">
                      <button
                        onClick={() => handleToggleUserRole(u.id, u.isHost)}
                        className={`px-3 py-1 rounded-xl text-[11px] font-bold border transition-colors ${
                          u.isHost
                            ? "bg-rose-50 text-rose-700 border-rose-200 hover:bg-rose-100"
                            : "bg-purple-50 text-purple-700 border-purple-200 hover:bg-purple-100"
                        }`}
                      >
                        {u.isHost ? "Misafire Çevir" : "Ev Sahibi Yap"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 6: SİSTEM & SQLITE WAL MONİTÖRÜ */}
      {activeTab === "system" && (
        <div className="bg-white border border-charcoal-border rounded-3xl p-6 shadow-xs flex flex-col gap-6 animate-in fade-in duration-200">
          <div>
            <h3 className="text-lg font-extrabold text-charcoal">Sistem Altyapısı & SQLite WAL Monitörü</h3>
            <p className="text-xs text-charcoal-light">10.0.2.1 sunucu mimarisi, veritabanı eşzamanlılığı ve iyzico bağlantı durumu.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            <div className="bg-charcoal-bg/70 border border-charcoal-border rounded-2xl p-4 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-charcoal-light">Hedef Sunucu</span>
                <Server className="w-4 h-4 text-airbnb" />
              </div>
              <div className="text-base font-extrabold text-charcoal">10.0.2.1 (mailim.fatsa.bel.tr)</div>
              <div className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" />
                Port 5173 / systemd Aktif
              </div>
            </div>

            <div className="bg-charcoal-bg/70 border border-charcoal-border rounded-2xl p-4 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-charcoal-light">Veritabanı Motoru</span>
                <Database className="w-4 h-4 text-blue-600" />
              </div>
              <div className="text-base font-extrabold text-charcoal">SQLite (better-sqlite3)</div>
              <div className="text-[11px] text-blue-600 font-semibold flex items-center gap-1">
                <Activity className="w-3.5 h-3.5" />
                WAL (Write-Ahead Logging) Modu
              </div>
            </div>

            <div className="bg-charcoal-bg/70 border border-charcoal-border rounded-2xl p-4 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-charcoal-light">Ödeme Ağ Geçidi</span>
                <CreditCard className="w-4 h-4 text-emerald-600" />
              </div>
              <div className="text-base font-extrabold text-charcoal">iyzico Sandbox API</div>
              <div className="text-[11px] text-emerald-600 font-semibold flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                Canlı Bağlantı Kurulu (256-Bit SSL)
              </div>
            </div>
          </div>

          {/* Database Table Metrics */}
          <div className="bg-charcoal-bg/50 border border-charcoal-border rounded-2xl p-5 flex flex-col gap-3">
            <h4 className="font-extrabold text-sm text-charcoal">Veritabanı Tablo Satır Sayımları</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
              {Object.entries(healthData?.tables || {
                users: 2,
                listings: 6,
                bookings: 3,
                payments: 1,
                reviews: 1,
                coupons: 2,
                guardian_issues: 0
              }).map(([table, count]) => (
                <div key={table} className="bg-white border border-charcoal-border/70 rounded-xl p-3 text-center">
                  <div className="text-[10px] font-bold text-charcoal-light uppercase truncate">{table}</div>
                  <div className="text-lg font-extrabold text-charcoal mt-0.5">{count}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
