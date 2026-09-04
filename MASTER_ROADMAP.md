# 🌌 Otonom Yapay Zekâ Ekosistemi — Ana Yol Haritası & Master Plan
**Proje Sahibi:** @coruhoorhan  
**Tarih:** 2026-09-03  
**Durum:** Faz 1 & 2 Aktif Geliştirme (YOLO Modu)  

---

## 🏛️ 1. Büyük Mimari Vizyon (Living AI Ecosystem)

Bu ekosistem; **insan müdahalesine ihtiyaç duymadan kendi kodunu geliştiren, kendi topluluğuyla konuşan ve kendi ürünlerini yaşatan bağımsız bir Yapay Zekâ Organizasyonudur.**

```text
                                 ┌─────────────────────────────────────────────────────────┐
                                 │           1. İLETİŞİM & BEDEN: SPACEBOT (Rust)          │
                                 │   • Discord, Telegram, Slack, Twitch, Tauri Desktop     │
                                 │   • Multi-User, Eşzamanlı Kanallar, SQLite Graf Bellek  │
                                 └────────────────────────────┬────────────────────────────┘
                                                              │ (A2A / MCP / ACP Protokolü)
                                                              ▼
                                 ┌─────────────────────────────────────────────────────────┐
                                 │          2. BEYİN & BİLİŞSEL MOTOR: MAGDA-AGENT         │
                                 │   • Hiyerarşik Planlayıcı (DAG) & Inception Mercury-2   │
                                 │   • ACS Güvenlik Sandbox'ı & Taint Tracking             │
                                 │   • AST Kod Tabanı Haritalayıcısı & Auto-Healer         │
                                 │   • OpenClaw-RL Canlı Öğrenme & MemGPT Bellek           │
                                 └────────────────────────────┬────────────────────────────┘
                                                              │ (Git Worktree & Kod Üretimi)
                                                              ▼
                                 ┌─────────────────────────────────────────────────────────┐
                                 │       3. ÜRÜNLER & ÇALIŞMA ALANLARI (Hedef Sistemler)   │
                                 │   • Çekirdek Repo  • Airbnb Klonu  • E-Belediye • CRM   │
                                 └─────────────────────────────────────────────────────────┘
```

---

## ✅ 2. Mevcut Durum & Tamamlanan Temel (Bugünün Çıktıları)

### A. Magda-Agent Bilişsel Çekirdeği (57 Modül %100 Doğrulandı)
* **Mimari & Planlama:** Magentic-One V3, DAG Dependency Graph V2, Claude Hierarchical Planner V3, Git Worktree İzolasyon & Senkronizasyon V5, Dağıtık Tracing V9.
* **Güvenlik & Sandbox:** ACS 5-Checkpoint Runtime Guard V7, MCPKernel Taint Tracking Sandbox V3, Token-Bucket Rate Limiter V1.
* **Bellek:** MemGPT Virtual Context Compressor V5, Letta Routine Builder V2, Prosedürel Bellek Yöneticisi.
* **Öğrenme:** OpenClaw-RL Online Reward Propagator V6, Habit Decay Manager V2, Hermes Skill Improver V1.
* **Test Durumu:** 57/57 test paketi yeşil. Kodlar `feature/magda-cognitive-v2-architecture` dalına pushlandı.

### B. Canlı Airbnb Entegrasyonu (`http://10.0.2.1:5173/`)
* **Canlı LLM:** Inception Labs `mercury-2` reasoning modeli entegre edildi.
* **AST Kod Haritası:** 63 Express API Rotası, 39 SQLite Fonksiyonu, 28 React Bileşeni ve 15 güvenlik açığı canlı indekslendi.
* **Arayüz Ayrımı:** Misafir için sade AI Concierge + Yönetici için "AI Guardian Bilişsel Kontrol Merkezi".
* **7/24 Daemon:** `magda-daemon.service` arka planda çalışıyor; `airbnb_tasks.json` içine 5 yeni özellik görevi keşfedip yazdı.

### C. Spacebot (`coruhoorhan/spacebot`)
* **PR #10 (Faz 2.2 Evidence Gate):** Test hatası çözüldü, GitHub Actions üzerinde **1.368 testin tamamı (%100) yeşile döndü** ve PR `clean` duruma getirildi.

---

## 🗺️ 3. Adım Adım Yol Haritası (Neler Yapacağız?)

### 📍 FAZ 1: Spacebot Rust Omurgasını Tamamlama & Upstream Hasadı (Öncelik: 1)

1. **PR #10'u Merge Etmek:**  
   * `coruhoorhan/spacebot` reposundaki yeşil olan PR #10'u (`Faz 2.2`) `main` dalına merge et.
2. **PR #11'i Tamamlamak (`Faz 2.3`):**  
   * `feat: built-in verify-after-work wake` PR'ını incele, testlerini çalıştır ve doğrula.
3. **Upstream (`spacedriveapp/spacebot`) PR Hasadı (Harvester):**  
   * Orijinal repodaki çözülmüş/hazır bekleyen kritik özellikleri kendi depomuza aktar (Cherry-pick):
     - **PR #652 & #653:** *Worker Controls & Result Relay Delivery Fix*
     - **PR #650 & #651:** *Resident Autonomy Channels*
     - **PR #649:** *Coding Worker Context & Observability*
     - **PR #641:** *Durable Reflection Timeline*
4. **Sıfır Hata Kuralı:**  
   * Her aktarılan PR'da `cargo test` ve `cargo clippy` çalıştırılacak, Magda/Jules ufak pürüzleri giderip %100 yeşil yapacak.

---

### 📍 FAZ 2: Spacebot (Rust) ↔ Magda-Agent (Python) Köprüsü

1. **MCP & ACP Protokol Entegrasyonu:**  
   * Spacebot'un PR #6 (MCP Server) ve PR #7 (ACP Server) yeteneklerini Magda-Agent'ın `mcp_export_v8.py` ve `a2a_auth_delegation_v3.py` modüllerine bağla.
2. **Çok Kanallı Görev Yönlendirme:**  
   * Discord veya Telegram'dan bir kullanıcı soru sorduğunda veya görev verdiğinde:
     - Spacebot mesajı alır -> Magda-Agent'a iletir -> Magda düşünür/planlar -> Spacebot yanıtı kullanıcıya döner.
3. **Cebinizden Yönetim (Telegram Komuta Merkezi):**  
   * Telegram botu üzerinden doğrudan sunucu durumu, görev onayları ve kod güncellemeleri tetiklenebilir hale getirilecek.

---

### 📍 FAZ 3: Otonom Ürün Geliştirme (Airbnb & Çekirdek Projeleri)

1. **`airbnb_tasks.json` Kuyruğunun Otonom Kodlanması:**  
   * Jules / Codex işçi ajanı sıradaki görevleri sırayla kodlayacak:
     - `feat-01-dynamic-pricing` (Dinamik Fiyatlandırma)
     - `feat-02-secure-auth` (OAuth2 & JWT)
     - `feat-03-graphql-api` (GraphQL Rotaları)
     - `feat-04-responsive-ui` (Mobil Uyum)
     - `feat-05-accessibility-audit` (Erişilebilirlik)
2. **Magda-Agent'ın Gözcü Rolü (Critic / Guardian):**  
   * Jules'un açtığı her PR, Magda'nın AST Smoke Tester'ı ve ACS Güvenlik Kalkanı tarafından otomatik incelenecek ve onaylanacak.

---

## 🤖 4. Ajanlar İçin Komut ve Prompt Kütüphanesi

### Jules / Codex İçin Görev Başlatma Promptu
```markdown
Sen projenin otonom kodlama işçisisin.
1. Hedef depodaki `tasks.json` (veya `airbnb_tasks.json`) manifestosunu oku.
2. Sıradaki 'todo' görevini al:
   - 'allowed_paths' kuralına sadık kalarak kodu yaz.
   - İlgili testleri oluştur ve çalıştır.
   - Durumu 'done' yap ve Pull Request aç.
```

### Upstream PR Çekme Komutu (Git)
```bash
git remote add upstream https://github.com/spacedriveapp/spacebot.git
git fetch upstream pull/<PR_NUMARASI>/head:upstream-feat-<PR_NUMARASI>
git checkout upstream-feat-<PR_NUMARASI>
cargo test --lib
```

---

*Bu belge, ekosistemin tek ve değişmez ana planıdır.*
