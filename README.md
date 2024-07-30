# fuzztainerAI
This is information about fuzztainerAI, my project for the SEFCOM high school internship of 2024

## What is FuzztainerAI
FuzztainerAI aims to leverage openai to generate commands/binary arguments for afl++ to increase the fuzzing capabilities of automatically harnessed docker containers.

## The Process
### STEP 1: Adding context (The Roots of the Tree)
Providing context is the most vital part of making the openai produce good results. No matter how good the prompt may be, wihout a good quanity and quality context, it might as well be a blank prompt. Without a good solid base of expansive and tough roots, a tree will never be able to grow. We added context with these three ways:

**1. <program> --help**
We created a tool which opeai could call which will return the output of the program's help page. We tried adding trying more options than just --help (for example: --tutorial, --info, --init, etc..) and at one point had about 50 of these commands, but found that all the extra commands didnt provide enough value to be justfied. It didnt produce much 90% of the time, and the times it did, it sometimes provided too much information that wasnt exactly relevant and ended up confusing openai more than it helped.

**2. Web Scraper**
We created a script using Playwright ([https://playwright.dev/](url)) to scrape the image page on https://hub.docker.com/ and pass the any overview information to the openai. This works better for more popular docker container which actually have documentation, while more obscure images woudnt commonoly have information. When it does work, it provides valuable juicy information significantly imporving the results.

**3. Test Commands**
This is a more last-minute experimental addition that we still need to test to justify it. If the previous two steps did not provide enough information, then openai can call another tool passing it 1-5 experimental test commands to analyze it's results and see what works and what doesnt work. Based on this information it can learn more about the type and method of input, various flags and how they work, and which ports are availbale. I hope that based off this information, it can then craft the real command that is more likely to work on the first try. 

### STEP 2: Crafting the prompt (the Trunk Tree)
Crafting and tweaking the prompt was a continuous process of trial and error and these are the most important lessons about prompt engineering that I learned: 
**1. Dont trust Openai at all:**
One rookie mistake I made at the beginning was treating openai like a human mentor. My prompts were too general and up to interpetation and while a knowledgeable human mentor might fill in the blanks, openai obviously could not do that.

ORIGINAL PROMPT: "*Use the information you just recieved to improve the prompts*" --> dont trust openai to know exactly what to look at in the information and how to improve the prompt
IMPROVED PROMPT: "*Using the information about the stdout and stderr of the prompts, change parts of the command to improve it based on the following characteristics: ...*"  --> Says exactly what infomration to look at (stdout, stderr) and which characteristics specifically to improve.

In other words: BE AS SPECIFIC AND COMMANDING AS POSSIBLE, dont trust openai to fill in the blanks like a human naturally would.

**2. More is not always merrier**
I feel into the common trap of adding as much information into the prompt as possible. If something didnt work as I wanted it to, I would just reword the instruction and add it at the end again (for example, i was having problems with the openai. Sometimes adding more information was actually deterimental to the openai results making it confused

**3. Seperate into small prompts**
I had better sucess when i split my prompt into four little sections instead of one big block. The one big block prompt was fine when the prompt was relatively small, but as I added more complexity, the openai started become more confused and hallucinate more often.


## STEP 3: Ensuring the command actually work (The Branches of the tree)
This is the biggest problem that we still are not 100% done creating. The biggest problems with LLM's is their hallucinations




### The Results
After preliminary results, we noticed two things that we need to change: We need to create more thourough testing to make sure the generated commands will actually work as intended. Our preliminary results did prove that fuzztainerAI does actually work sucessfully sometimes, but it is failing because of hallucination more times than not, so we need to fix that moving forward.

