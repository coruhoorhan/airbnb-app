#!/usr/bin/env python3
"""
Magda-Agent PR Code Auditor Bridge.
Delegates to standardized module: magda_agent.guardian.pr_auditor
"""

from magda_agent.guardian.pr_auditor import main, review_pr, auto_close_superseded_prs

if __name__ == "__main__":
    main()
