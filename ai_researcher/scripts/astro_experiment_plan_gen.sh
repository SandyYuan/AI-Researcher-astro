#!/bin/bash

# Example usage for astrophysics research project plan generation
# Run this script from the ai_researcher directory

python3 src/astro_experiment_plan_gen.py \
 --engine "claude-3-5-sonnet-20240620" \
 --idea_cache_dir "../cache_results_test/ideas_dedup/" \
 --cache_name "exoplanet_atmospheres" \
 --experiment_plan_cache_dir "../cache_results_test/project_proposals/" \
 --idea_name "all" \
 --seed 2024 \
 --method "observational" 