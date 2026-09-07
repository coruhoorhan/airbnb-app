#!/usr/bin/env python3
"""
Magda-Agent 7/24 Universal Fullstack Guardian Daemon.
Generic entry point for ANY project (Airbnb, E-Belediye, CRM, E-Commerce).
"""

import os
import sys

# Import from universal guardian engine
from magda_agent.guardian.guardian_runner import MagdaGuardianEngine
from magda_airbnb_daemon import MagdaAutonomousWatchdog, main

if __name__ == "__main__":
    main()
