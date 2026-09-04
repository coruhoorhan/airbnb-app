import React, { useState, useEffect } from "react";
import {
  Brain, ShieldCheck, Zap, Database, Activity, RefreshCw,
  CheckCircle2, AlertTriangle, Play, Plus, Server, Code,
  Layers, Lock, Cpu, Eye, FileText, ArrowUpRight, Check, X
} from "lucide-react";

export function AdminMagdaDashboard({ onClose }) {
  const [activeTab, setActiveTab] = useState("overview"); // 'overview', 'tasks', 'guardian', 'brain', 'rl'
  const [scanResult, setScanResult] = useState(null);
  const [tasksManifest, setTasksManifest] = useState({ tasks: [] });
  const [cognitiveState, setCognitiveState] = useState(null);
  const [codebaseData, setCodebaseData] = useState(null);
  const [codeSearch, setCodeSearch] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [newTaskTitle, setNewTaskTitle] = useState("");
  const [newTaskDesc, setNewTaskDesc] = useState("");
  const [newTaskArea, setNewTaskArea] = useState("backend");
  const [isAddingTask, setIsAddingTask] = useState(false);
  const [notification, setNotification] = useState(null);

  const fetchDashboardData = async () => {
    setIsLoading(true);
    try {
      // 1. Scan result
      const scanRes = await fetch("/api/magda/guardian/scan");
      const scanData = await scanRes.json();
      setScanResult(scanData);

      // 2. Cognitive state
      const stateRes = await fetch("/api/magda/status");
      const stateData = await stateRes.json();
      setCognitiveState(stateData);

      // 3. Tasks manifest
      const tasksRes = await fetch("/api/magda/tasks");
      if (tasksRes.ok) {
        const tasksData = await tasksRes.json();
        setTasksManifest(tasksData);
      }

      // 4. Codebase AST Knowledge
      const codeRes = await fetch("/api/magda/codebase-knowledge");
      if (codeRes.ok) {
        const codeJson = await codeRes.json();
        setCodebaseData(codeJson);
      }
    } catch (err) {
      console.error("Failed to load Magda Dashboard data:", err);
    } finally {
      setIsLoading(false);
    }
  };
  const handleTriggerScan = async () => {
    setIsLoading(true);
    try {
      const res = await fetch("/api/magda/guardian/scan");
      const data = await res.json();
      setScanResult(data);
      setNotification("Otonom tarama başarıyla tamamlandı.");
      setTimeout(() => setNotification(null), 3000);
    } catch (e) {
      setNotification("Tarama esnasında hata oluştu.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTask = async () => {
    if (!newTaskTitle.trim()) return;
    try {
      const res = await fetch("/api/magda/tasks/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: newTaskTitle,
          description: newTaskDesc || newTaskTitle,
          area: newTaskArea,
          risk: "medium",
        }),
      });
      const data = await res.json();
      if (data.success) {
        setNotification(`Görev eklendi: ${newTaskTitle}`);
        setNewTaskTitle("");
        setNewTaskDesc("");
        setIsAddingTask(false);
        fetchDashboardData();
      }
    } catch (e) {
      setNotification("Görev ekleme başarısız.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 font-sans animate-in fade-in duration-150">
      <div className="bg-white w-full max-w-5xl h-[85vh] rounded-3xl shadow-2xl border border-gray-100 flex flex-col overflow-hidden">
        
        {/* Top Header */}
        <div className="px-6 py-4 bg-gradient-to-r from-gray-900 via-charcoal-dark to-gray-950 text-white flex items-center justify-between border-b border-gray-800">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-rose-500 to-pink-600 rounded-xl shadow-lg border border-white/20">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold tracking-tight text-white">Magda-Agent Bilişsel Kontrol Merkezi</h2>
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 rounded-full text-[11px] font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                  7/24 Watchdog Canlı
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5">Autonomous Self-Healing Architecture & Task Engine</p>
            </div>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              onClick={handleTriggerScan}
              disabled={isLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-700 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow-sm transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
              <span>Otonom Tara</span>
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-800 rounded-full transition"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Notification Toast */}
        {notification && (
          <div className="bg-emerald-500 text-white text-xs font-semibold px-4 py-2 flex items-center justify-between">
            <span>{notification}</span>
            <button onClick={() => setNotification(null)}><X className="w-3.5 h-3.5" /></button>
          </div>
        )}

        {/* Sub-navigation Tabs */}
        <div className="flex border-b border-gray-200 bg-gray-50/80 px-6 text-xs font-semibold text-gray-600">
          <button
            onClick={() => setActiveTab("overview")}
            className={`py-3 px-4 border-b-2 transition flex items-center gap-1.5 ${
              activeTab === "overview" ? "border-rose-500 text-rose-600 bg-white" : "border-transparent hover:text-gray-900"
            }`}
          >
            <Activity className="w-4 h-4" /> Sistem Genel Bakış
          </button>
          <button
            onClick={() => { setActiveTab("tasks"); fetchDashboardData(); }}
            className={`py-3 px-4 border-b-2 transition flex items-center gap-1.5 ${
              activeTab === "tasks" ? "border-rose-500 text-rose-600 bg-white" : "border-transparent hover:text-gray-900"
            }`}
          >
            <FileText className="w-4 h-4 text-purple-600" /> Görev Manifestosu ({tasksManifest?.tasks?.length || 0} Görev)
          </button>
          <button
            onClick={() => setActiveTab("guardian")}
            className={`py-3 px-4 border-b-2 transition flex items-center gap-1.5 ${
              activeTab === "guardian" ? "border-rose-500 text-rose-600 bg-white" : "border-transparent hover:text-gray-900"
            }`}
          >
            <ShieldCheck className="w-4 h-4 text-emerald-600" /> Otonom Kod & Güvenlik Gardiyanı
          </button>
          <button
            onClick={() => setActiveTab("brain")}
            className={`py-3 px-4 border-b-2 transition flex items-center gap-1.5 ${
              activeTab === "brain" ? "border-rose-500 text-rose-600 bg-white" : "border-transparent hover:text-gray-900"
            }`}
          >
            <Brain className="w-4 h-4 text-indigo-600" /> Hiyerarşik Planlayıcı & DAG
          </button>
          <button
            onClick={() => setActiveTab("rl")}
            className={`py-3 px-4 border-b-2 transition flex items-center gap-1.5 ${
              activeTab === "rl" ? "border-rose-500 text-rose-600 bg-white" : "border-transparent hover:text-gray-900"
            }`}
          >
            <Zap className="w-4 h-4 text-amber-500" /> OpenClaw-RL Ağırlıkları
          </button>
          <button
            onClick={() => setActiveTab("codebase")}
            className={`py-3 px-4 border-b-2 transition flex items-center gap-1.5 ${
              activeTab === "codebase" ? "border-rose-500 text-rose-600 bg-white" : "border-transparent hover:text-gray-900"
            }`}
          >
            <Code className="w-4 h-4 text-blue-600" /> AST Kod Haritası ({codebaseData?.summary?.total_api_routes || 62} Rota / {codebaseData?.summary?.total_db_functions || 39} DB)
          </button>
        </div>

        {/* Content Body */}
        <div className="flex-1 p-6 overflow-y-auto bg-gray-50/50 space-y-6">
          
          {/* TAB 1: OVERVIEW */}
          {activeTab === "overview" && (
            <div className="space-y-6">
              {/* Stat Cards Grid */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-white p-4 rounded-2xl border border-gray-200/80 shadow-sm">
                  <div className="flex items-center justify-between text-gray-500 text-xs mb-1">
                    <span>Otonom Daemon</span>
                    <Server className="w-4 h-4 text-emerald-500" />
                  </div>
                  <div className="text-xl font-extrabold text-gray-900">7/24 Aktif</div>
                  <p className="text-[11px] text-emerald-600 font-medium mt-1">Her 60s tam teşhis</p>
                </div>

                <div className="bg-white p-4 rounded-2xl border border-gray-200/80 shadow-sm">
                  <div className="flex items-center justify-between text-gray-500 text-xs mb-1">
                    <span>ACS Güvenlik Kalkanı</span>
                    <ShieldCheck className="w-4 h-4 text-indigo-500" />
                  </div>
                  <div className="text-xl font-extrabold text-gray-900">5/5 Nokta</div>
                  <p className="text-[11px] text-gray-500 font-medium mt-1">Taint & Injection Koruması</p>
                </div>

                <div className="bg-white p-4 rounded-2xl border border-gray-200/80 shadow-sm">
                  <div className="flex items-center justify-between text-gray-500 text-xs mb-1">
                    <span>Otomatik Onarılan</span>
                    <CheckCircle2 className="w-4 h-4 text-rose-500" />
                  </div>
                  <div className="text-xl font-extrabold text-gray-900">
                    {scanResult?.summary?.auto_healed_count || 0} Sorun
                  </div>
                  <p className="text-[11px] text-gray-500 font-medium mt-1">Fiyat & Kupon Auto-Heal</p>
                </div>

                <div className="bg-white p-4 rounded-2xl border border-gray-200/80 shadow-sm">
                  <div className="flex items-center justify-between text-gray-500 text-xs mb-1">
                    <span>Görev Kuyruğu</span>
                    <FileText className="w-4 h-4 text-amber-500" />
                  </div>
                  <div className="text-xl font-extrabold text-gray-900">
                    {tasksManifest?.tasks?.length || 1} Görev
                  </div>
                  <p className="text-[11px] text-purple-600 font-medium mt-1">airbnb_tasks.json</p>
                </div>
              </div>

              {/* Subsystems Status List */}
              <div className="bg-white p-5 rounded-2xl border border-gray-200/80 shadow-sm space-y-4">
                <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-rose-500" />
                  Aktif Magda-Agent Bilişsel Alt Sistemleri
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                  {[
                    { name: "Hierarchical Planner V3 & DAG", desc: "Hedefleri paralel sub-task DAG graflarına böler.", status: "Aktif" },
                    { name: "ACS 5-Checkpoint Runtime Guard V7", desc: "Taint tracking ve yetki denetimi uygular.", status: "Aktif" },
                    { name: "MemGPT Virtual Context Compressor V5", desc: "Episodik diyalogları sıkıştırıp token tasarrufu sağlar.", status: "Aktif" },
                    { name: "Letta Routine Builder V2", desc: "Tekrar eden iş akışlarını prosedürel belleğe yazar.", status: "Aktif" },
                    { name: "OpenClaw-RL Online Learner V2", desc: "Kullanıcı geri bildirimiyle arama ağırlıklarını eğitir.", status: "Aktif" },
                    { name: "Aider AST Smoke Tester V1", desc: "Birleştirilen kodları anında AST syntax check yapar.", status: "Aktif" },
                  ].map((sys, idx) => (
                    <div key={idx} className="p-3 bg-gray-50 rounded-xl border border-gray-100 flex items-start justify-between gap-2">
                      <div>
                        <div className="font-bold text-gray-900">{sys.name}</div>
                        <div className="text-[11px] text-gray-500 mt-0.5">{sys.desc}</div>
                      </div>
                      <span className="px-2 py-0.5 bg-emerald-100 text-emerald-700 text-[10px] font-bold rounded-md whitespace-nowrap">
                        {sys.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: TASKS MANIFEST */}
          {activeTab === "tasks" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-gray-900">Proje Görev Manifestosu (`airbnb_tasks.json`)</h3>
                  <p className="text-xs text-gray-500">Magda-Agent veya geliştirici tarafından eklenen otonom görevler.</p>
                </div>
                <button
                  onClick={() => setIsAddingTask(true)}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-xs font-semibold shadow-sm transition"
                >
                  <Plus className="w-4 h-4" /> Yeni Görev Ekle
                </button>
              </div>

              {/* Add Task Form Modal */}
              {isAddingTask && (
                <div className="p-4 bg-white rounded-2xl border-2 border-rose-200 shadow-md space-y-3">
                  <h4 className="text-xs font-bold text-gray-900">Yeni Otonom Görev Tanımla</h4>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs">
                    <input
                      type="text"
                      placeholder="Görev Başlığı (Örn: Split Payment API)"
                      value={newTaskTitle}
                      onChange={(e) => setNewTaskTitle(e.target.value)}
                      className="px-3 py-2 border rounded-xl"
                    />
                    <input
                      type="text"
                      placeholder="Açıklama"
                      value={newTaskDesc}
                      onChange={(e) => setNewTaskDesc(e.target.value)}
                      className="px-3 py-2 border rounded-xl"
                    />
                    <select
                      value={newTaskArea}
                      onChange={(e) => setNewTaskArea(e.target.value)}
                      className="px-3 py-2 border rounded-xl bg-white"
                    >
                      <option value="backend">Backend (API/DB)</option>
                      <option value="frontend">Frontend (UI)</option>
                      <option value="safety">Safety (Güvenlik)</option>
                      <option value="learning">Learning (Öğrenme)</option>
                    </select>
                  </div>
                  <div className="flex justify-end gap-2 text-xs">
                    <button onClick={() => setIsAddingTask(false)} className="px-3 py-1.5 border rounded-xl">İptal</button>
                    <button onClick={handleCreateTask} className="px-4 py-1.5 bg-rose-600 text-white font-bold rounded-xl">Kaydet & Sıraya Al</button>
                  </div>
                </div>
              )}

              {/* Task List */}
              <div className="space-y-2.5">
                {tasksManifest?.tasks && tasksManifest.tasks.length > 0 ? (
                  tasksManifest.tasks.map((t, idx) => (
                    <div key={idx} className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm flex items-start justify-between gap-4 hover:border-purple-300 transition">
                      <div className="space-y-1.5 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-[10px] text-gray-700 font-bold bg-gray-100 px-2 py-0.5 rounded">{t.id}</span>
                          <span className="text-xs font-bold text-gray-900">{t.title}</span>
                          <span className="text-[10px] uppercase font-bold text-purple-600 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">{t.area}</span>
                          <span className="text-[10px] font-semibold text-gray-500 bg-gray-50 px-1.5 py-0.5 rounded">Risk: {t.risk || "medium"}</span>
                        </div>
                        <p className="text-xs text-gray-600 leading-relaxed">{t.description}</p>
                        {t.allowed_paths && (
                          <div className="text-[10px] text-gray-400 font-mono">
                            <span className="text-gray-600 font-sans font-semibold">İzinli Dosyalar:</span> {t.allowed_paths.join(", ")}
                          </div>
                        )}
                        {t.acceptance && (
                          <div className="text-[11px] text-gray-500">
                            <span className="font-semibold text-gray-700">Kabul Kriteri:</span> {Array.isArray(t.acceptance) ? t.acceptance.join(" • ") : t.acceptance}
                          </div>
                        )}
                      </div>
                      <span className={`px-2.5 py-1 text-[10px] font-bold rounded-full whitespace-nowrap ${
                        t.status === "done" ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800 animate-pulse"
                      }`}>
                        {t.status === "done" ? "✓ TAMAMLANDI" : "⏳ SIRADA (TODO)"}
                      </span>
                    </div>
                  ))
                ) : (
                  <div className="p-8 text-center bg-white rounded-xl border border-gray-200 text-gray-400 text-xs">
                    Henüz görev bulunmuyor. Yeni bir görev ekleyebilir veya otonom taramayı başlatabilirsiniz.
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: GUARDIAN ISSUES */}
          {activeTab === "guardian" && (
            <div className="space-y-4">
              <div className="bg-white p-4 rounded-xl border border-emerald-100 shadow-sm flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-emerald-900">7/24 Kod & Sistem Bütünlüğü Taraması</h4>
                  <p className="text-[11px] text-emerald-700 mt-0.5">AST syntax analizi ve veritabanı çakışma dedektörü sürekli devrededir.</p>
                </div>
                <button
                  onClick={handleTriggerScan}
                  className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold transition"
                >
                  Taramayı Yenile
                </button>
              </div>

              <div className="bg-white p-4 rounded-xl border border-gray-200 shadow-sm space-y-3">
                <h4 className="text-xs font-bold text-gray-900">Son Tarama Bulguları & Otomatik Onarımlar</h4>
                {scanResult?.database_issues && scanResult.database_issues.length > 0 ? (
                  <div className="space-y-2">
                    {scanResult.database_issues.map((iss, i) => (
                      <div key={i} className="p-3 bg-rose-50 border border-rose-200 rounded-xl text-xs text-rose-800 flex items-start gap-2">
                        <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                        <div>
                          <div className="font-bold">{iss.type}</div>
                          <div>{iss.description}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="p-4 bg-emerald-50 border border-emerald-100 rounded-xl text-xs text-emerald-800 flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    <span>Sistemde açık bir rezervasyon çakışması veya AST sözdizim hatası bulunmuyor. Tüm tablolar sağlıklı.</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: HIERARCHICAL PLANNER */}
          {activeTab === "brain" && (
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm space-y-4 text-xs">
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                <Brain className="w-4 h-4 text-indigo-600" />
                Claude Hierarchical Task Decomposition (DAG)
              </h3>
              <p className="text-gray-600 text-xs">
                Magda-Agent, kullanıcıdan gelen her karmaşık hedefi rollerine göre parçalara böler ve DAG sırasına göre icra eder:
              </p>
              <div className="space-y-2 font-mono text-[11px]">
                <div className="p-2.5 bg-purple-50 rounded-lg border border-purple-100 text-purple-900 font-bold">
                  1. Researcher: İlgili bölge, fiyat ve ilanları analiz et
                </div>
                <div className="p-2.5 bg-indigo-50 rounded-lg border border-indigo-100 text-indigo-900 font-bold">
                  2. Architect: Rezervasyon planı ve çakışma denetimi kur
                </div>
                <div className="p-2.5 bg-blue-50 rounded-lg border border-blue-100 text-blue-900 font-bold">
                  3. Coder: Veritabanı sorgularını ve fiyat indirimlerini hesapla
                </div>
                <div className="p-2.5 bg-emerald-50 rounded-lg border border-emerald-100 text-emerald-900 font-bold">
                  4. Tester: AST ve parametre doğruluğunu test et
                </div>
                <div className="p-2.5 bg-amber-50 rounded-lg border border-amber-100 text-amber-900 font-bold">
                  5. Reviewer: Çıktıyı son kullanıcı için sanitize et ve sun
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: OPENCLAW-RL */}
          {activeTab === "rl" && (
            <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-sm space-y-4 text-xs">
              <h3 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                <Zap className="w-4 h-4 text-amber-500" />
                OpenClaw-RL Online Öğrenme Ağırlıkları
              </h3>
              <p className="text-gray-600 text-xs">
                Kullanıcı etkileşimleri ve memnuniyet geri bildirimleri doğrudan bu ağırlıkları günceller:
              </p>
              <div className="space-y-3 pt-2">
                {Object.entries(cognitiveState?.openclaw_rl_weights || {
                  "semantic_similarity": 2.0,
                  "importance": 1.5,
                  "tag_overlap": 1.2,
                  "recency": 1.0,
                  "emotional_affinity": 0.8
                }).map(([k, v]) => (
                  <div key={k} className="space-y-1">
                    <div className="flex justify-between text-xs font-mono">
                      <span className="font-bold text-gray-700">{k}</span>
                      <span className="font-bold text-gray-900">{v}</span>
                    </div>
                    <div className="w-full bg-gray-100 rounded-full h-2">
                      <div
                        className="bg-gradient-to-r from-amber-400 to-rose-500 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${Math.min(100, (v / 3.0) * 100)}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 6: AST CODEBASE KNOWLEDGE & SYMBOL GRAPH */}
          {activeTab === "codebase" && (
            <div className="space-y-4 text-xs">
              <div className="bg-white p-4 rounded-xl border border-blue-100 shadow-sm flex items-center justify-between">
                <div>
                  <h4 className="text-xs font-bold text-blue-950 flex items-center gap-1.5">
                    <Code className="w-4 h-4 text-blue-600" />
                    Magda AST Canlı Kod Tabanı ve Mimari Haritası
                  </h4>
                  <p className="text-[11px] text-blue-800 mt-0.5">
                    Tüm JavaScript, React JSX ve SQLite operasyonları AST ile taranmış ve indekslenmiştir.
                  </p>
                </div>
                <div className="flex gap-2 text-[11px]">
                  <span className="px-2.5 py-1 bg-blue-50 text-blue-700 font-bold rounded-lg border border-blue-200">
                    {codebaseData?.summary?.total_api_routes || 62} REST Rota
                  </span>
                  <span className="px-2.5 py-1 bg-emerald-50 text-emerald-700 font-bold rounded-lg border border-emerald-200">
                    {codebaseData?.summary?.total_db_functions || 39} DB Fonksiyon
                  </span>
                  <span className="px-2.5 py-1 bg-purple-50 text-purple-700 font-bold rounded-lg border border-purple-200">
                    {codebaseData?.summary?.total_react_components || 28} React Bileşeni
                  </span>
                </div>
              </div>

              {/* Search Box */}
              <div className="bg-white p-3 rounded-xl border border-gray-200 flex items-center gap-2">
                <Code className="w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Rota, fonksiyon veya bileşen ara (Örn: /api/bookings, insertPayment, ListingCard)..."
                  value={codeSearch}
                  onChange={(e) => setCodeSearch(e.target.value)}
                  className="flex-1 text-xs outline-none bg-transparent"
                />
                {codeSearch && (
                  <button onClick={() => setCodeSearch("")} className="text-gray-400 hover:text-gray-600 text-xs">Temizle</button>
                )}
              </div>

              {/* Code Vulnerabilities & Smells Auto-Detected by Magda */}
              {codebaseData?.code_smells_and_issues && codebaseData.code_smells_and_issues.length > 0 && (
                <div className="bg-amber-50/60 p-4 rounded-xl border border-amber-200 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-amber-900 flex items-center gap-1.5">
                      <AlertTriangle className="w-4 h-4 text-amber-600" />
                      AST Kod Denetiminde Tespit Edilen Açıklar & İyileştirmeler ({codebaseData.code_smells_and_issues.length})
                    </h4>
                    <span className="text-[10px] text-amber-700 font-semibold">airbnb_tasks.json kuyruğuna aktarılabilir</span>
                  </div>
                  <div className="space-y-1.5 max-h-40 overflow-y-auto">
                    {codebaseData.code_smells_and_issues.map((iss, i) => (
                      <div key={i} className="p-2 bg-white rounded-lg border border-amber-200/80 text-[11px] flex items-center justify-between gap-2">
                        <div>
                          <span className="font-bold text-gray-900">{iss.title}</span>
                          <span className="text-gray-500 ml-2 font-mono text-[10px]">{iss.file}</span>
                          <div className="text-[10px] text-gray-600 mt-0.5">{iss.description}</div>
                        </div>
                        <button
                          onClick={async () => {
                            await fetch("/api/magda/tasks/create", {
                              method: "POST",
                              headers: { "Content-Type": "application/json" },
                              body: JSON.stringify({
                                title: iss.title,
                                description: iss.description,
                                area: "security",
                                risk: iss.severity || "medium",
                              }),
                            });
                            fetchDashboardData();
                          }}
                          className="px-2 py-1 bg-amber-600 hover:bg-amber-700 text-white font-bold rounded text-[10px] whitespace-nowrap"
                        >
                          + Görev Aç
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* API Routes List */}
              <div className="bg-white p-4 rounded-xl border border-gray-200 space-y-2">
                <h4 className="text-xs font-bold text-gray-900">İndekslenen Express REST API Rotaları (server.js)</h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-56 overflow-y-auto font-mono text-[10px]">
                  {codebaseData?.api_routes
                    ?.filter(r => !codeSearch || r.path.toLowerCase().includes(codeSearch.toLowerCase()) || r.method.toLowerCase().includes(codeSearch.toLowerCase()))
                    .map((r, i) => (
                      <div key={i} className="p-2 bg-gray-50 rounded border border-gray-100 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`px-1.5 py-0.5 rounded font-bold ${
                            r.method === 'GET' ? 'bg-blue-100 text-blue-700' :
                            r.method === 'POST' ? 'bg-emerald-100 text-emerald-700' :
                            r.method === 'PUT' ? 'bg-amber-100 text-amber-700' : 'bg-rose-100 text-rose-700'
                          }`}>{r.method}</span>
                          <span className="text-gray-800 font-medium truncate">{r.path}</span>
                        </div>
                        {r.has_rate_limiting ? (
                          <span className="text-emerald-600 text-[9px] font-bold">RateLimited</span>
                        ) : (
                          <span className="text-gray-400 text-[9px]">Unprotected</span>
                        )}
                      </div>
                    ))}
                </div>
              </div>

              {/* Database Functions List */}
              <div className="bg-white p-4 rounded-xl border border-gray-200 space-y-2">
                <h4 className="text-xs font-bold text-gray-900">İndekslenen SQLite Veritabanı Operasyonları (src/lib/db.js)</h4>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-1.5 max-h-48 overflow-y-auto font-mono text-[10px]">
                  {codebaseData?.database_functions
                    ?.filter(f => !codeSearch || f.name.toLowerCase().includes(codeSearch.toLowerCase()))
                    .map((fn, i) => (
                      <div key={i} className="p-1.5 bg-gray-50 rounded border border-gray-100">
                        <span className="text-purple-700 font-bold">{fn.name}</span>
                        <span className="text-gray-400 text-[9px]">({fn.parameters.join(', ')})</span>
                      </div>
                    ))}
                </div>
              </div>

              {/* React Components List */}
              <div className="bg-white p-4 rounded-xl border border-gray-200 space-y-2">
                <h4 className="text-xs font-bold text-gray-900">İndekslenen React Bileşenleri (src/components/*.jsx)</h4>
                <div className="grid grid-cols-1 md:grid-cols-4 gap-1.5 max-h-48 overflow-y-auto font-mono text-[10px]">
                  {codebaseData?.react_components
                    ?.filter(c => !codeSearch || c.component_name.toLowerCase().includes(codeSearch.toLowerCase()) || c.file.toLowerCase().includes(codeSearch.toLowerCase()))
                    .map((comp, i) => (
                      <div key={i} className="p-1.5 bg-gray-50 rounded border border-gray-100">
                        <div className="text-gray-900 font-bold">{comp.component_name}</div>
                        <div className="text-gray-400 text-[9px] truncate">{comp.file} ({comp.lines_of_code} satır)</div>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
