from openai import OpenAI
import anthropic
from together import Together
from utils import call_api, shuffle_dict_and_convert_to_string
import argparse
import json
import os
from lit_review_tools import format_papers_for_printing
from utils import cache_output
import random 
import retry
import sys

@retry.retry(tries=3, delay=2)
def idea_generation(method, existing_ideas, paper_bank, grounding_k, examples, ideas_n, topic_description, openai_client, model, seed, temperature, top_p, max_tokens, RAG=True):
    ## retrieve top papers (with some randomization)
    top_papers = paper_bank[ : int(grounding_k * 2)]
    random.shuffle(top_papers)
    grounding_papers = top_papers[ : grounding_k]

    prompt = "You are an expert researcher in astrophysics and astronomy. Now I want you to help me brainstorm some new research project ideas on the topic of: " + topic_description + ".\n\n"
    if RAG:
        prompt += "Here are some relevant papers on this topic just for your background knowledge:\n" + format_papers_for_printing(grounding_papers, include_score=False, include_id=False) + "\n"
    prompt += "You should generate {} different ideas on this topic. Try to be creative and diverse in the idea generation, and do not repeat any similar ideas. ".format(str(ideas_n))
    if RAG:
        prompt += "The above papers are only for inspiration and you should not cite them and just make some incremental modifications. Instead, you should make sure your ideas are novel and distinct from the prior literature. "
    prompt += "You should aim for projects that can potentially win best paper awards at top astronomy and astrophysics journals and conferences like ApJ, MNRAS, and AAS.\n"
    prompt += "Each idea should be described as: (1) Problem: State the problem statement, which should be closely related to the topic description and something that current astronomical methods struggle to address well. (2) Existing Methods: Mention some existing astronomical datasets, observational techniques, or analysis methods if there are any. (3) Motivation: Explain the inspiration of the proposed method and why it would work well for addressing this astrophysical problem. (4) Proposed Method: Propose your new method and describe it in detail. The proposed method should be maximally different from all existing work and baselines, and be more advanced and effective than the baselines. You should be as creative as possible in proposing new methods, we love unhinged ideas that sound crazy but are grounded in physical principles. This should be the most detailed section of the proposal. (5) Experiment Plan: Specify the experiment steps, which may include observations, simulations, data analysis techniques, validation methods, and evaluation metrics.\n"
    prompt += "You can follow these examples to get a sense of how the ideas should be formatted (but don't borrow the ideas themselves):\n" + examples + "\n"
    prompt += "You should make sure to come up with your own novel and different ideas for the specified problem: " + topic_description + ". You should try to tackle important problems that are well recognized in the field of astrophysics and considered challenging for current methods. For example, think of novel solutions for problems with existing observational data and analysis techniques. In rare cases, you can propose to tackle a new problem, but you will have to justify why it is important and how to set up proper evaluation.\n"
    if "claude" in model:
        prompt += "You should make each idea standalone and not dependent on the other ideas.\n"
    if method == "observational":
        prompt += "Focus on novel observational astronomy ideas for now. The proposed method section should specify how to set up the observations, what instruments to use, and how to analyze the data. Try to leverage existing astronomical facilities when possible.\n"
    elif method == "theoretical":
        prompt += "Focus on novel theoretical astrophysics ideas for now. The proposed method section should specify what physical models to develop, what simulations to run, and how to connect theory with observational constraints.\n"
    elif method == "data_analysis":
        prompt += "Focus on novel astronomical data analysis ideas for now. The proposed method section should specify how to process and analyze existing astronomical datasets using advanced computational techniques like machine learning, statistics, or computer vision.\n"
    else:
        prompt += "Focus on proposing novel methods in astrophysics research, which can include observational astronomy, theoretical modeling, computational simulations, or data analysis techniques. The proposed method section should specify all the details involved, such as what instruments or datasets to use, what physical models to develop, and how to evaluate the results.\n"
    if existing_ideas:
        prompt += "You should avoid repeating the following existing ideas and try to be different and diverse: " + existing_ideas + "\n"
    prompt += "Please write down your {} ideas (each idea should be described as one paragraph. Output the ideas in json format as a dictionary, where you should generate a short idea name (e.g., \"Multi-Wavelength Quasar Variability\", or \"Galactic Dark Matter Substructure\") as the key and the actual idea description as the value (following the above format). Do not repeat idea names or contents.".format(str(ideas_n))

    prompt_messages = [{"role": "user", "content": prompt}]
    response, cost = call_api(openai_client, model, prompt_messages, temperature=temperature, top_p=top_p, max_tokens=max_tokens, seed=seed, json_output=True)
    return prompt, response, cost

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', type=str, default='claude-3-opus-20240229', help='api engine; https://openai.com/api/')
    parser.add_argument('--paper_cache', type=str, default=None, required=True, help='cache file name for the retrieved papers')
    parser.add_argument('--idea_cache', type=str, default=None, required=True, help='where to store the generated ideas')
    parser.add_argument('--RAG', type=str, default="True", required=True, help='whether to do RAG for idea generation')
    parser.add_argument('--method', type=str, default='general', help='either observational, theoretical, data_analysis, or general')
    parser.add_argument('--grounding_k', type=int, default=10, help='how many papers to use for grounding')
    parser.add_argument('--append_existing_ideas', type=str, default="True", help='whether to append existing ideas to the idea cache')
    parser.add_argument('--max_tokens', type=int, default=30000, help='max tokens in the output')
    parser.add_argument('--temperature', type=float, default=1.0, help='temperature in sampling')
    parser.add_argument('--top_p', type=float, default=1.0, help='top p in sampling')
    parser.add_argument('--ideas_n', type=int, default=5, help="how many ideas to generate")
    parser.add_argument('--seed', type=int, default=2024, help="seed for generation")
    parser.add_argument('--debug', action='store_true', help="enable debug mode")
    args = parser.parse_args()

    with open("../keys.json", "r") as f:
        keys = json.load(f)
    random.seed(args.seed)

    ANTH_KEY = keys["anthropic_key"]
    OAI_KEY = keys["api_key"]
    ORG_ID = keys["organization_id"]
    
    if "claude" in args.engine:
        client = anthropic.Anthropic(
            api_key=ANTH_KEY,
        )
    elif "o1" in args.engine or "gpt" in args.engine:
        client = OpenAI(
            organization=ORG_ID,
            api_key=OAI_KEY
        )
    else:
        ## we will use Together API for all other models
        client = Together()
    
    with open(args.paper_cache, "r") as f:
        lit_review = json.load(f)
    
    topic_description = lit_review["topic_description"]
    paper_bank = lit_review["paper_bank"]

    ## cache dir and file
    if args.RAG == "True":
        print ("RAG is enabled for idea generation")
    else:
        print ("RAG is disabled for idea generation")
    ideas_file = args.idea_cache
    
    # extract existing ideas
    existing_ideas = None
    if os.path.exists(ideas_file) and args.append_existing_ideas == "True":
        with open(ideas_file, "r") as f:
            ideas_cache = json.load(f)
        if "ideas" in ideas_cache:
            existing_ideas = [key for idea in ideas_cache["ideas"] for key in idea.keys()]
            existing_ideas = list(set(existing_ideas))
            existing_ideas = "; ".join(existing_ideas)
            print ("Appending previous ideas.")
    else:
        print ("Not appending previous ideas.")
    
    # Use our new astro examples instead of the original ones
    with open("prompts/astro_idea_examples_method.json", "r") as f:
        method_idea_examples = json.load(f)
        method_idea_examples = shuffle_dict_and_convert_to_string(method_idea_examples)
    
    print ("topic: ", topic_description)
    print ("existing ideas: ", existing_ideas)
    print ("\n")
    print ("generating {} ideas...".format(str(args.ideas_n)))
    
    if not args.debug:
        try:
            prompt, response, cost = idea_generation(args.method, existing_ideas, paper_bank, args.grounding_k, method_idea_examples, args.ideas_n, topic_description, client, args.engine, args.seed, args.temperature, args.top_p, args.max_tokens, args.RAG)
        except:
            print ("Error in idea generation...")
            sys.exit(1)
    else:
        prompt, response, cost = idea_generation(args.method, existing_ideas, paper_bank, args.grounding_k, method_idea_examples, args.ideas_n, topic_description, client, args.engine, args.seed, args.temperature, args.top_p, args.max_tokens, args.RAG)
    
    print ("idea generation cost: ", cost)
    # print ("prompt: ", prompt)
    # print ("response: ", response)
    # print ("---------------------------------------\n")

    response = json.loads(response.strip())
    ideas = {"topic_description": topic_description, "ideas": [response]}
    
    ## if the idea_cache already exists, directly add to the current list
    if os.path.exists(ideas_file):
        with open(ideas_file, "r") as f:
            ideas_cache = json.load(f)
        ideas_cache["ideas"].append(response)
        ideas = ideas_cache
    
    print ("#ideas generated so far: ", sum(len(d) for d in ideas["ideas"]))

    ## save the cache
    cache_dir = os.path.dirname(ideas_file)
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
    cache_output(ideas, ideas_file) 