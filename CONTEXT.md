# Airbnb App — Villa Kiralama Platformu

> Karadeniz kıyısı temalı villa kiralama keşif platformu.
> React + Vite + Express + SQLite + iyzico ödeme.

## Proje Yapısı

```
/opt/airbnb-app/
├── src/              # React frontend (Vite)
│   ├── components/   # UI bileşenleri
│   ├── pages/        # Sayfa bileşenleri
│   ├── lib/          # Utility / API fonksiyonları
│   ├── App.jsx       # Ana uygulama (Router + state)
│   └── main.jsx      # Vite giriş noktası
├── tests/            # Vitest testleri
│   ├── messageEngine.test.js
│   ├── reservationEngine.test.js
│   └── ...
├── server.js         # Express backend (API + SQLite)
├── data/             # SQLite veritabanı dosyaları
├── docs/             # Dokümantasyon (PRD, research, agents)
├── .archcore/        # Archcore context
├── .scaffolding/     # Agent-stack scaffolding
└── .harness/         # Harness-automation policy
```

## Glossary

| Terim | Anlamı |
|---|---|
| Listing | Villa/kiralık ilanı |
| Listing ID | Benzersiz ilan kodu (örn. `list_01`) |
| Currency | Döviz birimi (TRY, USD, EUR, GBP) |
| Dark Mode | Koyu tema (localStorage `veys-dark-mode`) |
| Recently Viewed | Son bakılanlar (localStorage `veys-recently-viewed`, max 6) |
| Sort Order | Sıralama düzeni (Önerilen, Fiyat ↑↓, Puan ↓) |
| iyzico | Ödeme entegrasyonu (Express backend) |
| Kupon | İndirim kodu sistemi |
| Last Minute | Son dakika indirimi (yüzde bazlı) |

## Teknolojiler

- **Frontend:** React 19, React Router, Tailwind CSS v4
- **Backend:** Express, better-sqlite3, iyzico
- **Build:** Vite
- **Test:** Vitest
- **State:** React hooks (useState, useEffect, useMemo)
- **Persistence:** localStorage (preferences, recently viewed)
- **Scripting:** run.sh (agent-stack orchestration)
- **Skills:** Matt Pocock engineering skills (setup-matt-pocock-skills, implement-spec, tdd, code-review, domain-modeling, handoff, grill-with-docs, to-spec, ask-matt)
- **Gate system:** GATES.md (G1-G8, unlazy-style acceptance ledger)