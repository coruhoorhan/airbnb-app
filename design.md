# 🌊 Kinetic Coastal & Modernist — Tasarım ve Arayüz Anayasası

> **Belge Adı:** `design.md`
> **Konsept:** Kinetic Coastal & Modernist (Karadeniz Kıyı & Cesur Tipografi)
> **İlham:** Awwwards Site of the Day, Studio Freight, Kıyı Modernizmi
> **Tarih:** 29 Ağustos 2026 (Restore: 1 Eylül 2026)

---

## 1. Tasarım Kadranları (Design Dials)

| Kadran | Değer | Açıklama |
|---|---|---|
| DESIGN_VARIANCE | 9 | Asimetrik Bento ızgaraları, yatay kaydırmalı galeri, 50/50 split hero |
| MOTION_INTENSITY | 8 | 3D parallax tilt, hover depth, yay fiziği `:active:scale-[0.98]`, shimmer geçişleri |
| VISUAL_DENSITY | 3 | Ferah beyaz alan, nefes alan tipografi, düşük kart yoğunluğu |

---

## 2. Renk Paleti (Color System)

| Rol | Renk | Hex | Kullanım |
|---|---|---|---|
| Arka Plan (Aydınlık) | Kıyı Işığı | `from-sky-50/40 via-white to-amber-50/30` | Hero bölgesi, sayfa zeminleri |
| Arka Plan (Koyu) | Derin Obsidyen | `#0D0F12` / `#16191E` | Footer, koyu kartlar, modal overlay |
| Birincil CTA | Kıyı Gün Batımı (Amber Wave) | `#FF5A36` | Butonlar, fiyat vurgusu, linkler |
| İkincil Vurgu | Karadeniz Zümrütü | `#0F9D78` | İndirim kuponları, onay rozetleri, başarı durumları |
| Metin (Açık) | Kömür | `#1F2937` | Başlıklar, gövde metni |
| Metin (Koyu) | Kıyı Kumu | `#F9FAFB` | Koyu zeminde metin |

---

## 3. Tipografi Kuralları (Typography)

- **Başlıklar (Hero/H1/H2):** `font-black tracking-tight` — Cesur Sans Display, geniş harf aralığı
- **Alt Başlıklar (H3/H4):** `font-bold` — Kompakt, net
- **Fiyat & Veri:** `font-mono tabular-nums` — Monospaced, koordinat formatı (41.025° N, 37.498° E)
- **Sıfır Em-Dash:** Sayfada tek bir `—` veya `–` karakteri kullanılmaz. Tüm ayraçlar `·` (middot) veya `|` (pipe) ile değiştirilir.

---

## 4. Bileşen Standartları (Component Standards)

- **Köşe Yarıçapı:** `rounded-2xl` (kartlar, butonlar) / `rounded-3xl` (hero, modal) — tekil geometri ölçeği
- **Kartlar:** 3D hover depth (`hover:-translate-y-1 hover:shadow-xl`), spotlight border efekti
- **Butonlar:** WCAG AA kontrast, `min-h-[44px]`, `rounded-2xl`, `font-bold`, tek satır etiket
- **İskeletler (Skeleton):** CLS = 0, piksel kusursuz shimmer, `min-h-[100dvh]` mobil stabilite
- **Navigasyon:** Yüzen arama kapsülü, tek tık döviz çevirici (₺ TRY, $ USD, € EUR, £ GBP)

---

## 5. Kupon & İndirim Görsel Kuralları

- **Kupon Kutusu:** Amber `#FF5A36` border, zümrüt `#0F9D78` onay rozeti, `font-mono` kod
- **İndirim Satırı:** Zümrüt yeşili metin, `-₺{tutar}` formatı, `font-bold tabular-nums`
- **Hata Mesajı:** Kırmızı-500, `text-sm`, kupon input'u altında konumlandırma

---

## 6. Yasaklı Desenler (Banned Patterns)

- ❌ Klasik 3'lü kart sıraları (3-column card grid) — asimetrik bento zorunlu
- ❌ Yapay mor neon parlamalar (AI purple glow)
- ❌ Em-dash karakterleri (`—`, `–`)
- ❌ Küçük boyutlu (< 44px) dokunma hedefleri
- ❌ CSS'te `!important` (Tailwind utility sırası yeterli)

---

## 7. Düzen Mimarisi (Layout Architecture)

- **Hero:** 50/50 asimetrik split — sol tarafta editorial başlık, sağda öne çıkan görsel
- **Kategori Çubuğu:** Yatay kaydırmalı pill'ler, aktif kategori `ring-2 ring-amber-500`
- **İlan Izgarası:** Asimetrik bento (1 büyük + 2 dikey veya 2+1 pattern)
- **Detay Sayfası:** 5'li asimetrik fotoğraf kolajı, sticky booking widget
- **Footer:** Koyu obsidyen zemin, tek sütunlu marka + sosyal bağlantılar