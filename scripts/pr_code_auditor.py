#!/usr/bin/env python3
"""
Magda-Agent PR Code Auditor Bridge.
Delegates to standardized module: magda_agent.guardian.pr_auditor
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from magda_agent.guardian.pr_auditor import main, review_pr, auto_close_superseded_prs

if __name__ == "__main__":
    main()
