#!/bin/bash

# Example usage for astrophysics research idea generation
# Run this script from the ai_researcher directory

python3 src/astro_grounded_idea_gen.py \
 --engine "claude-3-5-sonnet-20240620" \
 --paper_cache "../cache_results_test/lit_review/exoplanet_atmospheres.json" \
 --idea_cache "../cache_results_test/seed_ideas/exoplanet_atmospheres.json" \
 --grounding_k 10 \
 --method "general" \
 --ideas_n 5 \
 --seed 2024 \
 --RAG "True" 