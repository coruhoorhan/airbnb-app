#!/usr/bin/env python3
import json
import sqlite3
import os
import time
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airbnb-app")

print("=" * 80)
print("MADDE 1 İSPATI: PROSEDÜREL & GÖREV BELLEĞİ (/opt/airbnb-app/airbnb_tasks.json)")
print("=" * 80)
with open("/opt/airbnb-app/airbnb_tasks.json", "r", encoding="utf-8") as f:
    manifest = json.load(f)

print(f"• Toplam Görev Sayısı: {len(manifest.get('tasks', []))}")
print(f"• Son Güncelleme: {datetime.fromtimestamp(manifest.get('updated_at', time.time()), timezone.utc).isoformat()}")
print("• Kaydedilen Görevlerden Örnekler:")
for t in manifest.get("tasks", [])[:4]:
    print(f"  - ID: [{t['id']}] | Alan: {t['area']} | Durum: {t['status']}")
    print(f"    Başlık: {t['title']}")
    print(f"    İzinli Dosyalar: {t.get('allowed_paths', [])}")
    print(f"    Kabul Kriterleri: {t.get('acceptance', [])}")

print("\n" + "=" * 80)
print("MADDE 2 İSPATI: ANLAMSAL SEMANTİK AST BİLGİ GRAFI (Codebase Knowledge Graph)")
print("=" * 80)
from magda_airbnb_codebase_indexer import AirbnbCodebaseIndexer
indexer = AirbnbCodebaseIndexer("/opt/airbnb-app")
graph = indexer.build_full_codebase_knowledge_graph()

s = graph["summary"]
print(f"• İndekslenen Toplam Varlık Sayısı: {s['total_api_routes']} Rota + {s['total_db_functions']} DB Fonksiyonu + {s['total_react_components']} React Bileşeni")
print("• Semantik İlişki Örnekleri (Route -> DB Fonksiyonları -> React Bileşenleri):")
for r in graph["api_routes"][:3]:
    print(f"  - API Endpoint: {r['method']} {r['path']} (server.js) | RateLimited: {r['has_rate_limiting']}")
for f in graph["database_functions"][:3]:
    params_str = ", ".join(f["parameters"])
    print(f"  - DB Fonksiyonu: {f['name']}({params_str}) (src/lib/db.js)")
for c in graph["react_components"][:3]:
    print(f"  - React Bileşeni: <{c['component_name']} /> ({c['file']}, {c['lines_of_code']} satır)")

print("\n" + "=" * 80)
print("MADDE 3 İSPATI: EPİSODİK BELLEK & GUARDIAN TABLOSU (/opt/airbnb-app/data/airbnb.db)")
print("=" * 80)
conn = sqlite3.connect("/opt/airbnb-app/data/airbnb.db")
conn.row_factory = sqlite3.Row
issues = conn.execute("SELECT id, type, severity, title, status, autoHealed, createdAt FROM guardian_issues ORDER BY id DESC LIMIT 5").fetchall()
print(f"• guardian_issues Tablosundaki Kayıt Sayısı: {len(issues)}")
for iss in issues:
    print(f"  - Issue #{iss['id']} [{iss['status'].upper()}] (Severity: {iss['severity']}): {iss['title']}")
    print(f"    Otomatik Onarıldı mı (AutoHealed): {bool(iss['autoHealed'])} | Tarih: {iss['createdAt']}")
conn.close()
print("=" * 80)
