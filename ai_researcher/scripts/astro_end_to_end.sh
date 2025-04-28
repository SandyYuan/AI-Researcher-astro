#!/bin/bash

# End-to-end pipeline for astrophysics research idea generation
# Run this script from the ai_researcher directory

# Literature review
python3 src/lit_review.py \
 --engine "claude-3-5-sonnet-20240620" \
 --mode "topic" \
 --topic_description "novel methods for detecting and characterizing exoplanet atmospheres using next-generation telescopes and advanced data analysis techniques" \
 --cache_name "../cache_results_test/lit_review/exoplanet_atmospheres.json" \
 --max_paper_bank_size 50 \
 --print_all

# Grounded idea generation
topic_names=("exoplanet_atmospheres")
ideas_n=5 ## batch size
methods=("general" "observational" "theoretical" "data_analysis")
rag_values=("True" "False")

for seed in {1..2}; do
    # Iterate over each topic name 
    for topic in "${topic_names[@]}"; do
        # Iterate over each method 
        for method in "${methods[@]}"; do
            # Iterate over RAG values True and False
            for rag in "${rag_values[@]}"; do
                echo "Running astro_grounded_idea_gen.py on: $topic with seed $seed, method $method, and RAG=$rag"
                python3 src/astro_grounded_idea_gen.py \
                 --engine "claude-3-5-sonnet-20240620" \
                 --paper_cache "../cache_results_test/lit_review/$topic.json" \
                 --idea_cache "../cache_results_test/seed_ideas/$topic.json" \
                 --grounding_k 10 \
                 --method "$method" \
                 --ideas_n $ideas_n \
                 --seed $seed \
                 --RAG $rag 
            done
        done
    done
done

# Idea deduplication
cache_dir="../cache_results_test/seed_ideas/"
cache_names=("exoplanet_atmospheres")

for cache_name in "${cache_names[@]}"; do
    echo "Running analyze_ideas_semantic_similarity.py with cache_name: $cache_name"
    python3 src/analyze_ideas_semantic_similarity.py \
    --cache_dir "$cache_dir" \
    --cache_name "$cache_name" \
    --save_similarity_matrix 
done

for cache_name in "${cache_names[@]}"; do
    echo "Running dedup_ideas.py with cache_name: $cache_name"
    python3 src/dedup_ideas.py \
    --cache_dir "$cache_dir" \
    --cache_name "$cache_name" \
    --dedup_cache_dir "../cache_results_test/ideas_dedup" \
    --similarity_threshold 0.8 
done

# Project proposal generation
idea_cache_dir="../cache_results_test/ideas_dedup/"
project_proposal_cache_dir="../cache_results_test/project_proposals/"
cache_names=("exoplanet_atmospheres")
seed=2024

for cache_name in "${cache_names[@]}"; do
    for method in "${methods[@]}"; do
        echo "Running astro_experiment_plan_gen.py with cache_name: $cache_name and method: $method"
        python3 src/astro_experiment_plan_gen.py \
        --engine "claude-3-5-sonnet-20240620" \
        --idea_cache_dir "$idea_cache_dir" \
        --cache_name "$cache_name" \
        --experiment_plan_cache_dir "$project_proposal_cache_dir" \
        --idea_name "all" \
        --seed $seed \
        --method "$method"
    done
done

# Project proposal ranking
experiment_plan_cache_dir="../cache_results_test/project_proposals/"
ranking_score_dir="../cache_results_test/ranking/"
cache_names=("exoplanet_atmospheres")
seed=2024

for cache_name in "${cache_names[@]}"; do
    echo "Running tournament_ranking.py with cache_name: $cache_name"
    python3 src/tournament_ranking.py \
    --engine claude-3-5-sonnet-20240620 \
    --experiment_plan_cache_dir "$experiment_plan_cache_dir" \
    --cache_name "$cache_name" \
    --ranking_score_dir "$ranking_score_dir" \
    --max_round 5 
done 