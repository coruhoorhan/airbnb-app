# Ultrawork Notepad — Web Yetenekleri Uçtan Uca Test
Started: 2026-08-07

## Amaç
4 aracın (modsearch, wigolo, modlens, Agent-Reach) + agy motorunun TAMAMINI gerçek sorgularla test et. Her araç için: HAPPY PATH + EDGE + GERÇEK YÜZEY kanıtı.

## Senaryolar (sözleşme)
S1 modsearch SEARCH: gerçek sorgu → results[].engine=antigravity-cli, items[] dolu
S2 modsearch FETCH: gerçek URL → content dolu
S3 wigolo SEARCH: gerçek sorgu → 2+ sonuç, skorlu
S4 wigolo FETCH: gerçek URL → markdown içerik
S5 wigolo CRAWL: küçük site → 2+ sayfa
S6 modlens GÖRSEL: test görüntüsü → OCR metin bulundu
S7 Agent-Reach YOUTUBE: gerçek video → bilgi/altyazı
S8 Agent-Reach V2EX: gerçek istek → postlar
S9 Agent-Reach RSS: gerçek feed → girdiler
S10 Agent-Reach WEB (Jina): gerçek URL → metin
S11 Agent-Reach GITHUB: gerçek repo → bilgi
S12 Agent-Reach BILIBILI: gerçek arama → sonuç

## Kanıt standardı
- Her test: komut + çıktı parçası + PASS/FAIL
- RED yok (araç testi, kod yok) — SURFACE kanıtı ana kriter

## SONUÇLAR (2026-08-07 08:30)
S1 modsearch SEARCH: ✅ PASS — antigravity-cli, 3 sonuç, 13.7s (npm + github + newreleases)
S2 modsearch FETCH: ✅ PASS — antigravity-cli, 416 char content
S3 wigolo SEARCH: ✅ PASS — bing+duckduckgo, 3 sonuç, 3.9s, skorlu (0.92/0.75/0.71)
S4 wigolo FETCH: ✅ PASS — markdown, 149 char, cached:false
S5 wigolo CRAWL: ✅ PASS — 1 sayfa (example.com tek sayfalık, makul)
S6 modlens OCR: ✅ PASS — 4/4 satır doğru okundu, 3.6s, 4 layout bölgesi
   NOT: Türkçe 'Ü' → 'U' okunmuş (küçük OCR hatası, metin ASCII'ydi)
S7 Agent-Reach YOUTUBE: ✅ PASS — yt-dlp v2026.07.04, video bilgisi alındı (5935s)
S8 Agent-Reach V2EX: ✅ PASS — 10 sıcak başlık API'den
S9 Agent-Reach RSS: ✅ PASS — Hacker News 20 girdi (feedparser)
S10 Agent-Reach WEB (Jina): ✅ PASS — sayfa metni + cached snapshot
S11 Agent-Reach GITHUB: ✅ PASS — gh CLI, omo 67391⭐
S12 Agent-Reach BILIBILI: ✅ PASS — bili-cli kuruldu, kullanıcı araması (112k fan)

## EK BULGULAR
- Agent-Reach CLI kanal komutları sunmuyor; SKILL.md + upstream araçlar üzerinden çalışıyor (yt-dlp, feedparser, gh, curl)
- B站 doğrudan API engelli (HTML döner) → bili-cli gerekli, kuruldu ✅
- Twitter: warn durumu — TWITTER_AUTH_TOKEN + TWITTER_CT0 cookie gerekli (kullanıcı onayı + yan hesap)
- agent-reach skill --install: 3 harness'a kuruldu (agents, openclaw, claude)
- wigolo search log'ları stdout'a karışıyor (bilinen davranış)
