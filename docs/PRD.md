# PRD — Airbnb-app (Villa Kiralama Platformu)

## Amaç
Karadeniz kıyısı temalı bir villa kiralama platformu: keşif (explore), ilan detayı, döviz/dil tercihleri,
fiyat sıralama, son bakılanlar. React + Vite + Express + SQLite + iyzico ödeme entegrasyonu.

## Kapsam
- Explore grid: ilan listeleme, filtreler, sıralama (Önerilen / Fiyat ↑ / Fiyat ↓ / Puan ↓)
- İlan detayı: fotoğraf galerisi, fiyat, puan, son dakika indirimi (last-minute)
- Tercih kalıcılığı: dark mode + döviz (localStorage)
- Son bakılanlar (Recently Viewed): max 6, en yeni önde
- Backend: Express + SQLite (ilan verisi, rezervasyon, iyzico ödeme)

## Kabul Kriterleri
- Tasarım anayasası `design.md`'ye uyulur (no em-dash, amber/zümrüt palet, `min-h-[44px]`, WCAG AA)
- Tüm görevler `complexity: small` → `implement-direct` yolunda ilerler
- Her görev sonrası `npm test` (9 engine testi) + `npm run build` yeşil
