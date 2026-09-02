# Changelog

## [1.1.0] — 2026-09-02

### Added
- **Preference Persistence (T1):** Dark mode ve döviz seçimi (`veys-dark-mode`, `veys-currency`) localStorage'da kalıcı hale getirildi. Sayfa yenilemede korunur.
- **Listing Sort (T2):** `SortBar` bileşeni eklendi — Önerilen / Fiyat ↑ / Fiyat ↓ / Puan ↓ sıralama seçenekleri. Filtrelerle birlikte çalışır.
- **Recently Viewed (T3):** `RecentlyViewed` bileşeni eklendi — son bakılan ilanları localStorage'da tutar (max 6, en yeni önde). Explore sayfasında 2+ ilan bakıldığında görünür.

### Changed
- `src/App.jsx`: Tüm ilan detayı açma işlemleri `handleOpenListing` fonksiyonunda birleştirildi.