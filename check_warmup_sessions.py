#!/usr/bin/env python3
"""Check which sessions are currently in warmup"""

import sys
sys.path.insert(0, '.')

from database import get_accounts_for_warmup

accounts = get_accounts_for_warmup()

print("\n" + "="*100)
print("✅ SESSIONS IN WARMUP")
print("="*100 + "\n")

print(f"Total sessions: {len(accounts)}\n")

session_ids = [acc.get('session_id') for acc in accounts]
print("Session IDs:")
print(", ".join(session_ids))
print()

# Group by stage
from collections import Counter
stages = Counter(acc.get('warmup_stage', 0) for acc in accounts)

print("By warmup stage:")
for stage in sorted(stages.keys()):
    count = stages[stage]
    print(f"  Stage {stage:2}: {count} sessions")

print("\n" + "="*100 + "\n")

