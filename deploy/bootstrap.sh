#!/bin/sh
# One-shot Compose bootstrap: migrate, generate + load sample sources, create actors, approve the trial profile.
set -eu
python scripts/generate_data.py
python experiments/support/generate_cases.py > /dev/null
S="$SAMPLE_SOURCE_URL"
python scripts/load_sources.py --group "cloud=$S#cloud" --group "ref=$S#ref" --group "ai=$S#ai"
python scripts/bootstrap.py
python scripts/trial_profile_approve.py config/trial-profiles/sandbox-trials-v1.json --actor lead
