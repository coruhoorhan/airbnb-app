import asyncio
import json
import logging
import os
import re
import sys
import time

sys.path.insert(0, "/opt/airbnb-app")

from magda_airbnb_codebase_indexer import AirbnbCodebaseIndexer
from magda_agent.llm_client import LLMClient
from magda_airbnb_daemon import AirbnbTasksManifestManager

indexer = AirbnbCodebaseIndexer("/opt/airbnb-app")
code_map = indexer.build_full_codebase_knowledge_graph()

llm = LLMClient(
    api_key="sk_bd34705e2b5f716f243d90fa5701c807",
    base_url="https://api.inceptionlabs.ai/v1",
    model="mercury-2",
    default_max_tokens=2500
)

async def run_discovery():
    prompt = f"""Sen Magda-Agent Bilişsel Mimarı ve Ürün Yöneticisisin.
Aşağıda /opt/airbnb-app projesinin canlı AST kod tabanı haritası yer alıyor:
- API Rotaları: {len(code_map['api_routes'])} adet (server.js)
- DB Fonksiyonları: {len(code_map['database_functions'])} adet (src/lib/db.js)
- React Bileşenleri: {len(code_map['react_components'])} adet (src/components/)
- Tespit Edilen Kod Açıkları: {len(code_map['code_smells_and_issues'])} adet

Bu Airbnb projesini pazardaki en gelişmiş, modern ve güvenli platform haline getirmek için 5 adet SOMUT, EKSİKSİZ ve GELİŞTİRİLEBİLİR YENİ ÖZELLİK GÖREVİ (Feature Tasks) üret.

Format JSON olmalıdır:
{{
  "tasks": [
    {{
      "id": "feat-01-dynamic-pricing",
      "area": "backend",
      "risk": "medium",
      "title": "Ev Sahipleri İçin Yapay Zekâ Dinamik Fiyatlandırma Motoru",
      "description": "Doluluk oranı, mevsimsellik ve talep yoğunluğuna göre optimal gecelik fiyat hesaplayan akıllı motor.",
      "allowed_paths": ["server.js", "src/lib/pricingEngine.js", "airbnb_tasks.json"],
      "acceptance": ["Fiyat öneri API'si doğru oranları döner.", "Birim testleri geçer."]
    }}
  ]
}}
Sadece JSON ver."""

    raw_json = await llm.generate(prompt)
    m = re.search(r"\{.*\}", raw_json, re.DOTALL)
    if m:
        parsed = json.loads(m.group(0))
        manifest_mgr = AirbnbTasksManifestManager("/opt/airbnb-app/airbnb_tasks.json")
        added_count = 0
        for t in parsed.get("tasks", []):
            if manifest_mgr.add_task(
                task_id=t["id"],
                title=t["title"],
                description=t["description"],
                area=t.get("area", "backend"),
                risk=t.get("risk", "medium"),
                allowed_paths=t.get("allowed_paths", ["server.js", "airbnb_tasks.json"]),
                acceptance=t.get("acceptance", ["Tests pass."])
            ):
                added_count += 1
        print(json.dumps({
            "status": "features_discovered",
            "new_tasks_added": added_count,
            "tasks": parsed.get("tasks", [])
        }, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"error": "Failed to parse JSON", "raw": raw_json[:300]}))

asyncio.run(run_discovery())
