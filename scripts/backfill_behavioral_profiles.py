#!/usr/bin/env python3
"""
Backfill behavioral profiles for all accounts with personas.

One-time migration script: generates and saves behavioral_profile
for all personas that don't have one yet.

Usage:
    cd /root/heat_up && python3 scripts/backfill_behavioral_profiles.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import sqlite3
from database import (
    get_db_connection, generate_behavioral_profile, get_persona,
    init_database
)


def backfill():
    # Ensure schema is up to date
    init_database()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Only active warmup accounts that are NOT frozen/deleted/banned
        cursor.execute("""
            SELECT p.account_id, p.activity_level, p.generated_name, a.account_type
            FROM personas p
            JOIN accounts a ON p.account_id = a.id
            WHERE p.behavioral_profile IS NULL
            AND a.account_type = 'warmup'
            AND a.is_active = 1
            AND a.is_frozen = 0
            AND a.is_deleted = 0
            AND a.is_banned = 0
        """)
        rows = cursor.fetchall()

        if not rows:
            print("All active warmup personas already have behavioral profiles. Nothing to do.")
            return

        print(f"Found {len(rows)} active warmup accounts without behavioral_profile. Generating...")

        created = 0
        for row in rows:
            account_id = row["account_id"]
            persona_data = {"activity_level": row["activity_level"]}
            profile = generate_behavioral_profile(account_id, persona_data)

            cursor.execute(
                "UPDATE personas SET behavioral_profile = ? WHERE account_id = ?",
                (json.dumps(profile, ensure_ascii=False), account_id)
            )
            created += 1

        conn.commit()
        print(f"Generated {created} behavioral profiles.")

        # Show distribution of key parameters (only active warmup)
        print("\n--- Parameter Distribution (active warmup, sample 15) ---")
        cursor.execute("""
            SELECT
                p.account_id,
                json_extract(p.behavioral_profile, '$.timing.min_action_delay') as min_d,
                json_extract(p.behavioral_profile, '$.timing.max_action_delay') as max_d,
                json_extract(p.behavioral_profile, '$.engagement.react_probability') as react,
                json_extract(p.behavioral_profile, '$.reading.speed_min') as speed,
                json_extract(p.behavioral_profile, '$.conversation.min_response_delay') as resp_delay
            FROM personas p
            JOIN accounts a ON p.account_id = a.id
            WHERE p.behavioral_profile IS NOT NULL
            AND a.account_type = 'warmup'
            AND a.is_active = 1 AND a.is_frozen = 0 AND a.is_deleted = 0
            LIMIT 15
        """)
        sample = cursor.fetchall()
        print(f"{'AccID':>6} | {'MinDelay':>8} | {'MaxDelay':>8} | {'React%':>6} | {'ReadSpd':>7} | {'RespDelay':>9}")
        print("-" * 60)
        for r in sample:
            print(f"{r['account_id']:>6} | {r['min_d']:>8.2f} | {r['max_d']:>8.2f} | {r['react']:>6.3f} | {r['speed']:>7.2f} | {r['resp_delay']:>9}")

        # Summary stats
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                AVG(json_extract(p.behavioral_profile, '$.timing.min_action_delay')) as avg_min_d,
                MIN(json_extract(p.behavioral_profile, '$.timing.min_action_delay')) as lo_min_d,
                MAX(json_extract(p.behavioral_profile, '$.timing.min_action_delay')) as hi_min_d,
                AVG(json_extract(p.behavioral_profile, '$.engagement.react_probability')) as avg_react,
                MIN(json_extract(p.behavioral_profile, '$.engagement.react_probability')) as lo_react,
                MAX(json_extract(p.behavioral_profile, '$.engagement.react_probability')) as hi_react
            FROM personas p
            JOIN accounts a ON p.account_id = a.id
            WHERE p.behavioral_profile IS NOT NULL
            AND a.account_type = 'warmup'
            AND a.is_active = 1 AND a.is_frozen = 0 AND a.is_deleted = 0
        """)
        stats = cursor.fetchone()
        print(f"\n--- Summary ({stats['total']} active warmup profiles) ---")
        print(f"min_action_delay: avg={stats['avg_min_d']:.2f}, range=[{stats['lo_min_d']:.2f}, {stats['hi_min_d']:.2f}]")
        print(f"react_probability: avg={stats['avg_react']:.3f}, range=[{stats['lo_react']:.3f}, {stats['hi_react']:.3f}]")


if __name__ == "__main__":
    backfill()
