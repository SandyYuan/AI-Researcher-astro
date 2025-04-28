from openai import OpenAI
import anthropic
from utils import call_api
import argparse
import json
import os
from utils import cache_output, format_plan_json
import retry
from tqdm import tqdm
import random 
random.seed(2024)

@retry.retry(tries=3, delay=2)
def plan_generation_method(method, idea, demo_examples, topic_description, openai_client, model, seed):
    ## formulate an idea from a paragraph into a full experiment plan based on our template

    prompt = "You are an expert researcher in astrophysics and astronomy. Your job is to expand a brief project idea into a full research proposal with detailed experiment plans so that your students can follow the steps and execute the full project. I will provide you with an idea on the topic of: " + topic_description + ".\n\n"
    prompt += "The idea is:\n" + format_plan_json(idea) + "\n"
    prompt += "Now you should come up with the full research plan covering:\n"
    prompt += "1. Title: A concise statement of the main research question to be used as the paper title.\n"
    prompt += "2. Problem Statement: Clearly define the astrophysical problem your research intends to address. Explain clearly why this problem is interesting and important in the context of modern astronomy.\n"
    prompt += "3. Motivation: Explain why existing methods (both classic ones and recent ones) are not good enough to solve the problem, and explain the inspiration behind the new proposed method. You should also motivate why the proposed method would work better than existing approaches on the problem.\n"
    prompt += "4. Proposed Method: Explain how the proposed method works, describing all the steps in detail. Make sure every step is clearly described and feasible to implement using available astronomical facilities, datasets, or computational resources.\n"
    prompt += "5. Step-by-Step Experiment Plan: Break down every single step of the research, making sure every step is executable. Cover all essential details such as the observations needed, instruments to use, datasets to analyze, simulations to run, and metrics to evaluate success. For observational plans, specify telescope requirements, exposure times, and data reduction steps. For theoretical work, describe model development and validation approaches. For data analysis, provide specific techniques and tools to use.\n"
    prompt += "6. Test Case Examples: Give two concrete examples. The first example should show how the baseline method fails on a specific astronomical scenario or dataset. If there are multiple baselines, give examples for all of them. The second example should show how the proposed method succeeds on the same case. For each test case, include the input and the expected output. You should also provide an explanation for why the outputs from the proposed method are better. If the proposed method has multiple steps, break them down into intermediate steps.\n"
    prompt += "7. Fallback Plan: Propose some alternative plans for what the students should do if the proposed method didn't manage to satisfy the success criteria. For example, you can suggest additional analysis to help debug why the proposed method didn't work, which could inform alternative new methods, or how to turn the project into an analysis paper by offering interesting results even if the main hypothesis isn't confirmed. Write a coherent paragraph rather than a list of bullet points.\n"
    prompt += "The research plan should not include any background introduction (you can skip the literature review, paper writing tips, and ethical discussion). Just give instructions on the research and experiments.\n"
    
    if method == "observational":
        prompt += "When designing the research plan, focus on observational astronomy. Prefer using existing telescopes and instruments rather than proposing to build new ones. Consider the practical aspects of telescope proposal requirements, expected signal-to-noise ratios, and data reduction techniques. Be realistic about the observing time allocations that would be feasible for a student project.\n"
    elif method == "theoretical":
        prompt += "When designing the research plan, focus on theoretical astrophysics. Develop analytical models or numerical simulations that can be implemented with reasonable computational resources. Make sure to include validation steps that connect the theoretical work to existing observational constraints.\n"
    elif method == "data_analysis":
        prompt += "When designing the research plan, focus on astronomical data analysis. Utilize existing public datasets from astronomical surveys or archives. Consider computational requirements and specify appropriate statistical or machine learning methods. Ensure that data preprocessing steps are clearly described.\n"
    else:
        prompt += "When designing the research plan, consider a comprehensive approach that might combine observations, theory, and data analysis as appropriate for the problem. Be realistic about the resources required and make sure the plan is feasible for a student project.\n"
    
    prompt += "Be consistent in your methodology and experiment design. For example, if you propose to use a specific telescope or instrument, make sure it's appropriate for the wavelength and sensitivity requirements of your project.\n"
    prompt += "Below are a few examples of how the full research plans should look like:\n"
    prompt += demo_examples + "\n\n"
    prompt += "Now please write down your research plan in JSON format (keys should be the section names, just like the above examples). Make sure to be as detailed as possible so that a student can directly follow the plan to implement the project."
    
    prompt_messages = [{"role": "user", "content": prompt}]
    response, cost = call_api(openai_client, model, prompt_messages, temperature=0., max_tokens=4096, seed=seed, json_output=True)
    return prompt, response, cost

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', type=str, default='gpt-4-1106-preview', help='api engine; https://openai.com/api/')
    parser.add_argument('--idea_cache_dir', type=str, default=None, required=True, help='dir that stores all the raw ideas')
    parser.add_argument('--experiment_plan_cache_dir', type=str, default=None, required=True, help='dir to store all the generated experiment plans')
    parser.add_argument('--cache_name', type=str, default=None, required=True, help='the specific cache (topic)')
    parser.add_argument('--idea_name', type=str, default=None, required=True, help='the specific idea to be formulated into an experiment plan')
    parser.add_argument('--method', type=str, default='general', help='either observational, theoretical, data_analysis, or general')
    parser.add_argument('--grounding_k', type=int, default=10, help='how many papers to use for grounding')
    parser.add_argument('--seed', type=int, default=2024, help="seed for generation")
    args = parser.parse_args()

    with open("../keys.json", "r") as f:
        keys = json.load(f)

    ANTH_KEY = keys["anthropic_key"]
    OAI_KEY = keys["api_key"]
    ORG_ID = keys["organization_id"]
    S2_KEY = keys["s2_key"]
    
    if "claude" in args.engine:
        client = anthropic.Anthropic(
            api_key=ANTH_KEY,
        )
    else:
        client = OpenAI(
            organization=ORG_ID,
            api_key=OAI_KEY
        )

    ## We would ideally have astro-specific examples, but for initial implementation
    ## we'll use the existing examples
    with open("prompts/experiment_plan_examples_prompting.txt", "r") as f:
        demo_examples = f.read().strip()
    
    with open(args.idea_cache_dir + args.cache_name + ".json") as f:
        idea_file = json.load(f)
    topic_description = idea_file["topic_description"]
    all_ideas = idea_file["ideas"]

    if args.idea_name == "all":
        idea_names = list(all_ideas.keys())
    else:
        idea_names = [args.idea_name]
    
    if not os.path.exists(args.experiment_plan_cache_dir + args.cache_name + "/"):
        os.makedirs(args.experiment_plan_cache_dir + args.cache_name + "/")
        
    all_costs = 0
    for idea_name in tqdm(idea_names):
        cache_file = os.path.join(args.experiment_plan_cache_dir + args.cache_name + "/" + '_'.join(idea_name.lower().split()) + ".json")
        
        try:            
            idea_file = {}
            idea_file["topic_description"] = topic_description
            idea_file["idea_name"] = idea_name
            idea_file["raw_idea"] = all_ideas[idea_name]

            print ("working on: ", idea_name)
            idea = all_ideas[idea_name]
            
            prompt, response, cost = plan_generation_method(args.method, idea, demo_examples, topic_description, client, args.engine, args.seed)
            # print (response)
            print ("cost: ", cost)

            all_costs += cost
            experiment_plan = json.loads(response.strip())
            idea_file["full_experiment_plan"] = experiment_plan

            cache_output(idea_file, cache_file)

        except: 
            print ("error in generating experiment plan for idea: ", idea_name)
    
    print ("Total cost: ", all_costs) 