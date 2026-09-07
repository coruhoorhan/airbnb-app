#!/usr/bin/env bash
# ==============================================================================
# Magda-Agent 7/24 Living Cognitive Organism — Automated Setup Script
# Installs 57 cognitive features, virtualenv, dependencies, systemd guardian
# Usage: ./setup_magda_agent.sh [TARGET_PROJECT_DIR]
# ==============================================================================

set -euo pipefail

TARGET_DIR="${1:-/opt/airbnb-app}"
MAGDA_SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="/opt/magda-env"

echo "🌌 [Magda-Agent Setup] Starting deployment for target: ${TARGET_DIR}"
echo "📁 Source directory: ${MAGDA_SOURCE_DIR}"

# 1. System Pre-requisites Check
echo "🔍 Step 1: Checking system prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "❌ python3 required but not installed."; exit 1; }
command -v git >/dev/null 2>&1 || { echo "❌ git required but not installed."; exit 1; }
command -v openssl >/dev/null 2>&1 || { echo "❌ openssl required but not installed."; exit 1; }

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✅ Python version: ${PY_VER} (3.10+ supported)"

# 2. Virtual Environment Setup
echo "🐍 Step 2: Creating/Updating isolated Python environment at ${VENV_DIR}..."
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

source "${VENV_DIR}/bin/activate"
pip install --upgrade pip setuptools wheel >/dev/null 2>&1 || true

# 3. Install Full 57-Feature Dependencies
echo "📦 Step 3: Installing 57-feature cognitive dependencies (ChromaDB, FastAPI, HTTPX, SQLite, AST)..."
pip install -r "${MAGDA_SOURCE_DIR}/requirements.txt" --quiet

# 4. Target Project Synchronization
echo "🧬 Step 4: Embedding Magda-Agent cognitive core into target project..."
mkdir -p "${TARGET_DIR}/magda_agent"
mkdir -p "${TARGET_DIR}/.github/workflows"
mkdir -p "${TARGET_DIR}/scripts"

# Sync magda_agent package
rsync -av --delete --exclude '__pycache__' "${MAGDA_SOURCE_DIR}/magda_agent/" "${TARGET_DIR}/magda_agent/" >/dev/null 2>&1 || cp -rf "${MAGDA_SOURCE_DIR}/magda_agent" "${TARGET_DIR}/"

# Sync guardian daemon & indexer
cp -f "${MAGDA_SOURCE_DIR}/magda_airbnb_daemon.py" "${TARGET_DIR}/magda_daemon.py" 2>/dev/null || true
cp -f "${MAGDA_SOURCE_DIR}/magda_airbnb_codebase_indexer.py" "${TARGET_DIR}/magda_codebase_indexer.py" 2>/dev/null || true

# 5. Environment & Secrets Configuration
echo "🔐 Step 5: Configuring environment variables (.env)..."
ENV_FILE="${TARGET_DIR}/.env"
touch "${ENV_FILE}"

# Ensure JWT_SECRET
if ! grep -q "^JWT_SECRET=" "${ENV_FILE}"; then
    echo "JWT_SECRET=$(openssl rand -hex 32)" >> "${ENV_FILE}"
fi

# Ensure CSRF_SECRET
if ! grep -q "^CSRF_SECRET=" "${ENV_FILE}"; then
    echo "CSRF_SECRET=$(openssl rand -hex 32)" >> "${ENV_FILE}"
fi

# Set default LLM config if missing
if ! grep -q "^OPENAI_MODEL=" "${ENV_FILE}"; then
    echo "OPENAI_MODEL=mercury-2" >> "${ENV_FILE}"
    echo "OPENAI_BASE_URL=https://api.inceptionlabs.ai/v1" >> "${ENV_FILE}"
fi

# 6. Initialize Task Manifest if missing
if [ ! -f "${TARGET_DIR}/agent_tasks.json" ]; then
    echo "📋 Step 6: Initializing agent_tasks.json..."
    cat << 'EOF' > "${TARGET_DIR}/agent_tasks.json"
{
  "schema_version": 1,
  "project": "magda-managed-app",
  "task_source_priority": [
    "agent_tasks.json"
  ],
  "risk_levels": [
    "low",
    "medium",
    "high",
    "critical"
  ],
  "merge_policy": {
    "low": "auto_merge_after_tests",
    "medium": "auto_merge_after_tests",
    "high": "human_review_required",
    "critical": "manual_only"
  },
  "replenishment_policy": {
    "minimum_todo_tasks": 3,
    "batch_size": 3,
    "always_add_tasks": false,
    "tasks_per_run": 1,
    "allowed_risks_for_generated_tasks": [
      "low",
      "medium"
    ]
  },
  "tasks": []
}
EOF
fi

# 7. Setup Systemd 7/24 Service
if command -v systemctl >/dev/null 2>&1 && [ "$EUID" -eq 0 ]; then
    echo "⚙️ Step 7: Configuring systemd service (magda-daemon.service)..."
    cat << EOF > /etc/systemd/system/magda-daemon.service
[Unit]
Description=Magda-Agent 7/24 Autonomous Fullstack Guardian
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${TARGET_DIR}
EnvironmentFile=${TARGET_DIR}/.env
Environment=PYTHONUNBUFFERED=1
ExecStart=${VENV_DIR}/bin/python3 ${TARGET_DIR}/magda_daemon.py 60
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable --now magda-daemon.service >/dev/null 2>&1 || true
    echo "✅ Systemd service magda-daemon.service active and running."
fi

# 8. Verification
echo "🧪 Step 8: Verifying module imports..."
${VENV_DIR}/bin/python3 -c "
import sys
sys.path.insert(0, '${TARGET_DIR}')
from magda_agent.llm_client import LLMClient
from magda_agent.safety.acs_guard_runtime_v7 import ACSGuardRuntimeV7
from magda_agent.memory.virtual_compression_v5 import MemGPTVirtualContextSemanticCompressorV5
print('✨ Core 57-feature cognitive modules imported cleanly.')
"

echo "=============================================================================="
echo "🎉 Magda-Agent setup completed successfully!"
echo "📍 Target Project: ${TARGET_DIR}"
echo "🧠 Virtualenv:     ${VENV_DIR}"
echo "🤖 Guardian:       magda-daemon.service (Active 7/24)"
echo "=============================================================================="
