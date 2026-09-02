# Gorevatama — Kullanım Kılavuzu

> Bu kılavuz, gorevatama skill'ini ve web yeteneklerini (modsearch, wigolo, modlens, Agent-Reach) nasıl kullanacağını gösterir.

## 1. Temel Kullanım (bir chat penceresinde)

Gorevatama'yı çağırmanın iki yolu var:

### Yol A — Doğal dil (önerilen)
```
gorevatama: şunu ara — "opencode son sürüm"
gorevatama: bu sayfayı oku — https://github.com/...
gorevatama: şu özelliği planla — <açıklama>
gorevatama: şunu yap — <görev>
```
Sen normal Türkçe cümleyle istersin, gorevatama doğru aracı seçer.

### Yol B — Açık araç belirtme
```
gorevatama: modsearch ile ara — "DeepSeek V4 pricing"
gorevatama: wigolo ile araştır — "react 19 breaking changes"
gorevatama: modlens ile şu görsele bak — <görüntü yapıştır veya yol>
gorevatama: agent-reach ile youtube — <url>
```

## 2. Hangi Araç Ne Zaman? (seçim tablosu)

| Sen dersen... | Gorevatama ne yapar |
|---|---|
| "şunu ara / güncel bilgi ver" | **modsearch** — hızlı kanıtlı arama |
| "araştır / derinlemesine bak / karşılaştır" | **wigolo** — 18 motor + rerank |
| "bu sayfayı/siteyi tara" | **wigolo crawl** |
| "şu görsele bak / ekran görüntüsünü oku" | **modlens** — OCR + layout |
| "youtube'da / twitter'da / reddit'te ara" | **Agent-Reach** — platform erişimi |
| "bu videonun altyazısı" | **Agent-Reach youtube** (yt-dlp) |
| "x.com'daki şu tweet" | **Agent-Reach twitter** (cookie gerekli) |

## 3. Canlı Test Örnekleri (kopyala-yapıştır)

### 🔍 Web araması
```
gorevatama: şunu ara — "DeepSeek V4 Flash pricing"
```
Beklenen: kaynak URL'ler + tarih + özet (modsearch, ~10-15sn)

### 🕸️ Derin araştırma
```
gorevatama: wigolo ile araştır — "oh-my-openagent vs plain opencode"
```
Beklenen: skorlu sonuçlar (Bing+DuckDuckGo), ~4sn

### 👁️ Görsel okuma
```
gorevatama: modlens ile şu ekran görüntüsüne bak — <görüntüyü yapıştır>
```
Beklenen: OCR metin + layout bölgeleri + uncertainty

### 📺 YouTube
```
gorevatama: agent-reach ile youtube — https://www.youtube.com/watch?v=...
```
Beklenen: video bilgisi (başlık, süre) — altyazı için "altyazı çıkar" de

### 🐦 Twitter/X (cookie sonrası)
```
gorevatama: twitter'da ara — "opencode"
gorevatama: twitter'da şu konu ne diyor — "deepseek v4"
```
⚠️ Önce Twitter yapılandırması gerekli (aşağıda).

### 📖 RSS
```
gorevatama: hacker news'i oku
```
Beklenen: 20 girdi (feedparser)

### 💻 GitHub
```
gorevatama: şu repoyu incele — code-yeongyu/oh-my-openagent
```
Beklenen: star sayısı + açıklama (gh CLI)

## 4. Twitter/X Yapılandırması (bir kerelik, senin tarafında)

> Twitter cookie'lerini **sen** sağlamalısın — ben (gorevatama) göremem/giremem.
> ⚠️ **ÖNEMLİ: ana hesabını kullanma — yan hesap (burner) kullan.** Ban riski var.

### Adım adım:

1. **twitter-cli kuruldu** ✅ (v0.8.5, venv'de) — bu hazır.

2. **Cookie-Editor eklentisi kur** (tarayıcına):
   - Chrome/Firefox mağazasından "Cookie-Editor" eklentisini ekle

3. **Yan hesapla X'e gir** (twitter.com, yan hesap, tarayıcıda)

4. **Cookie'leri dışa aktar**:
   - Cookie-Editor ikonuna tıkla → "Export" → JSON kopyala
   - İçinden `auth_token` ve `ct0` değerlerini bul

5. **Bana şu komutu çalıştır** (değerleri senin cookie'lerinle değiştir):
```bash
~/.agent-reach-venv/bin/agent-reach configure twitter-cookies --stdin << 'EOF'
TWITTER_AUTH_TOKEN=<auth_token_değerin>
TWITTER_CT0=<ct0_değerin>
EOF
```
   - `--stdin` kullanıldığı için değerler terminal geçmişine yazılmaz (güvenli)

6. **Doğrula:**
```bash
~/.agent-reach-venv/bin/agent-reach doctor
```
   Twitter satırı `warn` → `ok` olmalı.

7. **Test:**
```bash
TWITTER_AUTH_TOKEN=<auth_token> TWITTER_CT0=<ct0> ~/.agent-reach-venv/bin/twitter search "opencode" -n 5
```

> Not: Her `twitter` komutu öncesi env değişkenleri gerekir — gorevatama bunu senin adına yönetir ama cookie'lerin `~/.agent-reach/config.yaml`'de saklanır (600 izin, sadece sana).

## 5. Sık Sorulanlar

| Soru | Cevap |
|---|---|
| "skill listede yok" | opencode'u yeniden başlat — skill'ler oturum başında yüklenir |
| "modsearch yavaş (10-30sn)" | Normal — agy motoru LLM kullanır. wigolo daha hızlı (~4sn) |
| "agy kotası bitti" | wigolo search devreye girer (kota yok) — ya da Tavily anahtarı |
| "modlens Türkçe karakter yanlış okuyor" | Ücretsiz Gemini anahtarı ekle → 5-10sn + daha iyi OCR |
| "wigolo research çalışmıyor" | LLM anahtarı gerekir (opsiyonel) — anahtarsız ham kanıt döner |
| "Agent-Reach x kanalı kapalı" | `agent-reach doctor` ile hangi backend aktif bak; login gerekenler için yan hesap + cookie |

## 6. Test Kanıtları

12 senaryonun tamamı test edildi — kanıtlar: `~/.agents/skills/gorevatama/TEST-KANITLARI.md`

## 7. Kural: Çalışma dosyaları nereye?

**Kesin kural: hiçbir ajan, çalışma belgesi (.md, plan, not, kanıt) `/tmp`'ye koymaz.**
- Planlar → `.omo/plans/<slug>.md`
- Kanıtlar/notlar → `~/.agents/skills/gorevatama/`
- Geçici kod/araç testleri → `/tmp` sadece **kalıcı olmayan** komut çıktıları için
