from openai import OpenAI
import subprocess
import json
import IPython
import time
#using this import just for testing
# from deps.archr.archr.targets import DockerImageTarget
# this is the real import:
from archr.targets import DockerImageTarget
from pathlib import Path
from fuzztainer.fuzztainer_scraper import FuzztainerScraper
import logging


class FuzztainerAI:
    def __init__(self, target, previous_binary_args):
        self.client = OpenAI()
        self.image_name = target.image_id
        self.t = target
        self.results = []
        self.previous_binary_args = previous_binary_args
        self.tool_choice = "auto"
        self.test_command_runs = []

        self.executable_path = [ ]
        print(f"old {self.t.target_args}")
        for arg in self.t.target_args:
            full_arg, err = self.t.run_command(["/busybox", "which", arg], privileged=True).communicate()
            full_arg = full_arg.decode('latin-1').strip()
            if full_arg:
                self.executable_path.append(full_arg)
            else:
                self.executable_path.append(arg)
        
        self.t = DockerImageTarget(self.image_name, pull=True, use_init=True)
        self.t.build()
        self.t.start()

        print(f"STARTING FTAI: {self.image_name} with exectable path {self.executable_path}")
        print("CALLING FUZZTAINER_SCRAPER...")
        ft_sc = FuzztainerScraper(self.image_name)
        self.scrape_info = ft_sc.scrape()

        if self.scrape_info != None:
            self.scrape_info = f'''
                -Here is some context found by web scraping information of image {self.image_name} from hub.docker.com delimited by XML tags:

                  {self.scrape_info} 

                Analyze and search this for the following information about the program within the docker container:
                -information about the network protocol or ports that the program will use
                -information about any specific flags or arguments that can be used to create your command to run the program
                -information about the method and type of input that is passed to the binary

                Dont consider any information about settings, configurations, or anything about actually running the docker container itself, you are 
                trying to make commands for the binary/program within the docker container itself, only consider information about the program/binary within the docker container.

                If there is any useful information  remember to use it later for creating the commands and setting the port and proto metadata fields.
                There might not be any useful information, that is fine. 
            '''
            print("SCRAPE INFO FOUND")
        else:
            self.scrape_info = ""
            
        self.result_format = '''
        {
            "command": <command>,
            "directories": [
                //for any directories present in the command
                //example: if you want to make the directories tmp/socket/dir1 and tmp/socket/dir2 then the this field should look like this "directories":["./tmp", "./tmp/socket", "./tmp/socket/dir1", "./tmp/socket/dir2"]
                //example if you have the directory tmp/var then you have to put ["./tmp", "./tmp/var"] you CANNOT just put ["./tmp/var"]
                "<the name and path of each directory relative to ./>"
                ],
            "files": [
                {   
                    //for any files present in the command
                    //if you want if you wanted to make a file name "file1.txt" in the directory tmp/socket/dir1 then it should be "name":"tmp/socket/dir1/file1.txt"
                    //make sure the all the directories of the path are already in the "directories" field, if not then add it
                    "name": "<full relative path + name of the file>", 
                    "content": "<Appropiate content to be writen in the file. Make this as simple as possible so the command works as intended. Dont put anything complicated, as simple as possible>"
                }, 
            //the input field is the input which will be mutated, must be exactly copy of whats present in the command
            "input": "<IMPORTANT: REQUIRED, the exact value of the one direct input which the program is recieving exactly as written in the command. This should only be the ONE item which is being used by the program most directly, dont use inputs passed through flags if there is input being passed directly into program. needs to be character-by-charcter identical to what is reflected in the command. Should never be contents within a file. Do not include any flags>",
            "input_type": "<the type of input that the binary accepts and the value of the input field is. OPTIONS = ['file', 'input_string', 'standard_in', 'network'  ] >"
            "port": "<The port of the program/binary is using. Double check that these are accurate. Dont fill this out if you are uncertain>", 
            "proto": "<the network transport layer protocol (UDP or TCP) of this binary. Keep this field blank if you are uncertain>"
        }
        '''

        main_system = f'''
                You are an AI assistant specialized in generating and refining command-line instructions for executing binaries. 
                Your tasks involve creating diverse and effective commands, ensuring they maximize code path coverage and functionality testing, and producing detailed metadata.

                You are also a creative imaginative inventive original thinker, not afraid to experiment and try new ideas to generate interesting commands.

                You also follow the users requirments meticulously and prompts carefully and to the letter exactly. 

                You also always write the output of your response in strict JSON format with the specific fields that the user instructs you to create. You dont output
                anyting other than this json which the user explicitly asks for. This is the format you will always return in delmited in xml tags:

                <return_format>
                {self.result_format}
                </return-format>
        '''

        self.list_prompt = [
            #Creates 5 base commands
            f''' 
                I want you to craft your best command on the commandline containing various arguments/flags and some method of input that executes this binary: {self.executable_path} (items after the first two might not be useful/applicable) -This program will be inside a docker container, but you are creating commands that executes this binary/program within the container itself so never create commands that are related to running docker itself. -Dont create command that are expeting a X-server/graphical output. -The command needs to be diverse and creative to test as much functionailty of the program as possible. Here are some ways to learn how the program takes input, what various flags and arguments it might take, and what network protocol and ports it uses: -Get the help page of a program and its related command(s) by running it from the commandline. Use this information to search for how it takes input, th various flags and arguments, and what possible network protocol and available listening ports it uses. Only call the help page once for the program and/or each command if applicable. {self.scrape_info} - If you still do not have enough information about the type/method of input and flags, then to sequentially create 1-5 very varied and diverse test experimental commands with various inputs and flags (the motivation of these commands is to gain as much infomation about how to run the program. The top priority is experimentation on these commands not accuracy. if you already know a lot about the program and how to run from previous steps then skip this step, the less you know the program from previous steps then the more number of commands you should test and experiment with. Analyze stdout and stderr gain more information about the type and method of input, how to use the different flags, what open listening ports/adresses exist, what works, and what doesnt work. One special thing to look for is available listening ports/adresses, find out which ports/network adresses are available and listening, if a specific port/adress is not available, then try a new one until you find a isteing port/adress. Dont put the port explicitly in the real final command, just figure it out in the testing commands. Dont use these any of the previous commands itself, instead just use the information generated by them to craft the final command. Then using all this information, continue crafting the final command. -make sure to add any files and directories in the command in the metadata of the command (if there are any errors because of missing files/directories, then add the specific files/directories) and try again. Here are the essential requirements for the command: 0. They are as different as possible (try using different flags and input types) as the following commands which has already been generated: f{self.previous_binary_args}. -Executable Without Errors: The command must run exactly as produced on the command line without any errors. 2. Comprehensive Testing: The command should explore as many diverse code paths and functionalities of the program as possible by using various flags, arguments, and input methods. 3. Single Command Only: You are not allowed to combine multiple commands. Each command should solely execute the binary with its respective input and flags. 4. Meaningful Input: The command must include some form of input based on how the program accepts input. Avoid using commands like <program> --help, <program> --version, or <program> -flag alone, as they do not provide meaningful input for testing. The actual value of the input is meaningless and should be the simples possible input to make the command work. -You shoudnt explicitly port the port with a flag in the real command. -Try to create commands that dont result in a timeout. The actual value of the input no matter what type it is does not matter, it should be as simple as possible placeholder to make the command work and make sure nothing else in the command has the same placeholder value as the input.
            ''',

            # Creates metadata
            f''' I want you to create metadata. I want you to format the command and metadata with the json format below exactly, dont add a single character before or after (dont add ```json), it must be be valid json format that is able to run json.loads(your_output). Dont return any text of any other kind. result_format: """ { self.result_format } """ For the input field: 1. The input metadata value should be only the one string/file/etc. that the program is accepting as input, dont include anything else (flags shold never be in the input field and the input field should generally not include any spaces unless its a string) Try not to have unnecesary directories in the command, only use directories if the input directly needs a direcotry or a directory would be used to further discover the codes functionality. The enviroment that the command will be running in will be empty. Make sure the input that the program is using is in the input field in the metadata. ''',

            #cycle of getting commandline outputs and tweaking command until it works
            f''' Then I want you to get the result (stdout and stderr) of the real command ran on the commandline. After you get the result from running these commands on the commandline -If the stderr contains a crash/error/fault/exception stemming from the command, change the portion of the command that is causing this error and try running the command again and continue this cycle (max of ten times) until the stderr doesnt contain a crash/error/fault/exception/extc. -If the command is giving the same error more than 3 times, then you can remove the part of the commands the error is stemming from -If the command says you should add required flags then you should add them. -If a specific flag keeps causing an error, then remove it. -If the command keps saying that the port is not available, then try to use other possible available ports. Make sure the command has an available listening port working sucessfully before you return. Once the command works without any crashes/errors/faults/exceptions stopping the program from working, then finally return the final command and the updated metadata in the same exact format: f{self.result_format} ''',

             #sanity check on metadata and input
             f''' Analyze the final command and metadata and change if needed based on these: -If the input value is empty, then search the command for the direct input to the program and put that exactly as reflected in the -The metadata follows this format exactly: {self.result_format} only, nothing other than that -The files and directories fields have every single file and directory that are mentioned in the command -the input field is not empty and has the the exact value of the direct input that is in stated in the command (if we replace this value with something else, the command will run) -dont include flags in the input value, dont include anything other than the exact input value as seen in the command -the port field and proto fields has the most accurate values filled out, blank if the port/network isnt expicitly started anywhere. -The port shouldnt explicitly be stated within the command, try not to use the --port flag. -get the stdout and stderr of the command one last time and make sure it doesnt have any crashes/error/faults/exceptions stemming from the command double check to make sure each point above is true then, RETURN THE FINAL COMMAND AND METADATA AFTER ONLY AFTER MAKING SURE EVERYTHING IS CORRECT. '''
        ]
        
        self.tools = [
        {
            "type": "function",
            "function": {
                "name": "get_help_page",
                "description": "get the help page of a program and its related command(s)/package(s) by running it from the commandline",
                "parameters" : {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "only the command/program for which you want the context for (dont add --help)"
                        }
                    },
                    "required": ["command"]
                },
            }
        },

        {
            "type": "function",
            "function": {
                "name": "run_command",
                "description": "Get the result (stdout and stderr) of one real command run on the commandline. ",
                "parameters" : {
                    "type": "object",
                    "properties": {
                        "commandsAndMetadata": {
                            "type": "string",
                            "description": f"Follow the following format exactly (only one command at a time, dont give a list of commands): {self.result_format}"
                        }
                    },
                    "required": ["commandsAndMetadata"]
                },
            }
        },

        {
            "type": "function",
            "function": {
                "name": "test_command",
                "description": "Get information of the type/method of inputs and how to use various flags of a program through running a test command",
                "parameters" : {
                    "type": "object",
                    "properties": {
                        "commandsAndMetadata": {
                            "type": "string",
                            "description": f"Follow the following format exactly (only one command at a time, dont give a list of commands): {self.result_format}"
                        }
                    },
                    "required": ["commandsAndMetadata"]
                },
            }
        },
    ]

        self.messages = []
        self.messages.append({"role": "system","content": main_system})

    def fire(self):
        for prompt in self.list_prompt:
            self.tool_choice = "auto"
            print(f"MOVING ON TO STEP {self.list_prompt.index(prompt)+1}")
            if self.list_prompt.index(prompt) > 0:
                prompt = f"Your last return command(s) were <command> {self.results[len(self.results) - 1].choices[0].message.content.strip()} <command>. " + prompt 

            self.messages.append({"role": "user", "content": prompt})
            self.openai_api_call()

        self.tool_choice = "none"

        print("\n\n END CHECK \n\n")
        
        check = self.check(self.results[len(self.results) - 1].choices[0].message.content)
        attempts = 0
        while check != True:
            if attempts > 5: break
            self.messages.append({"role": "user", "content": check})
            self.openai_api_call()
            check = self.check(self.results[len(self.results) - 1].choices[0].message.content)
            attempts += 1

        result = json.loads(self.results[len(self.results) - 1].choices[0].message.content)
        result['command'] = result['command'].replace(result['input'], '@@', 1)

        print(f"\n\n RESULT: \n {self.results[len(self.results) - 1].choices[0].message.content}")

        self.t.stop()

        return result
                

    def check(self, final_result):
        try:
            final_result = json.loads(self.results[len(self.results) - 1].choices[0].message.content.strip())
        except Exception as e:
            return f"An exception has occured with your output trying to json.loads() your output (json.loads({self.results[len(self.results) - 1].choices[0].message.content})): {str(e)}. Fix the structure of your output and return again with the correct json strcuture. Not a single character before or after (dont add '''json), Start and end with brackets. Make sure the argument can be converted to valid json: there are no unterminated strings, unterminated anything, no new line '\\n' characters, just the eact json in a single line surrounded by single quotes"
        if 'command' not in final_result:
            return f"the field 'command' not found in your output: {final_result}. Fix this and return it. This is the exact format you need to return in: {self.result_format}"
        if 'files' not in final_result:
            return f"the field 'files' not found in your output: {final_result}. Fix this and return it. This is the exact format you need to return in: {self.result_format}"
        if 'directories' not in final_result:
            return f"the field 'directories' not found in your output: {final_result}. Fix this and return it. This is the exact format you need to return in: {self.result_format}"
        if 'input' not in final_result:
            return f"the field 'input' not found in your output: {final_result}. Fix this and return it. This is the exact format you need to return in: {self.result_format}"
        if 'port' not in final_result:
            return f"the field 'port' not found in your output: {final_result}. Fix this and return it. This is the exact format you need to return in: {self.result_format}"
        if 'proto' not in final_result:
            return f"the field 'proto' not found in your output: {final_result}. Fix this and return it. This is the exact format you need to return in: {self.result_format}"
        if len(final_result['input']) == 0:
            return f"the field 'input' is a required field, you can not leave it empty. Find the exact input being passed to the program as reflected in the command and set that to the value of the 'input field' and return the fixed result. This is the exact format you need to return in: {self.result_format}"
        if final_result['input'] not in final_result['command']:
            return f"The input {final_result['input']} is not character-by-character contained within the command {final_result['command']}. Slightly alter the input value until the input value is contained within the command {final_result['command']}"

        result = self.run_command(final_result, True)['stderr'].lower()

        if 'error' in result or 'exception' in result or 'fault' in result or 'crash' in result:
            return result
        return True
        

    def openai_api_call(self):
        print(f"\n\n {len(self.messages)} - PROMPT: {self.messages[len(self.messages) - 1]} \n")

        completion = self.client.chat.completions.create(
            model="gpt-4o",
            messages=self.messages,
            tools=self.tools,
            tool_choice=self.tool_choice,
            response_format={"type":"json_object"}
        )

        self.results.append(completion)

        if completion.choices[0].message.tool_calls == None:
            print(f"{len(self.messages)} -  RETURN: " + completion.choices[0].message.content)
            return

        for tool in completion.choices[0].message.tool_calls:
            print(f"{len(self.messages)} -  TOOL CALL:  {completion.choices[0].message.tool_calls}" )
            self.messages.append({
                "role" : "assistant",
                "tool_calls": [{"id": tool.id, "function":tool.function, "type": tool.type}]
            })
            self.messages.append({   
                "tool_call_id": tool.id,
                "role": "tool",
                "type": "function",
                "name": tool.function.name,
                "content": self.execute_function(tool.function.name, tool.function.arguments)
            })
            self.openai_api_call()
        

    def execute_function(self, function_name, arguments):

        available_functions = {
            "get_help_page": self.get_help_page,
            "run_command": self.run_command,
            "test_command": self.test_command
        }
        
        function_call = available_functions[function_name]

        print(f"\n IN EXECUTE_FUNCTION ( {function_name} ) \n")

        if function_call:
            if not isinstance(arguments, dict):
                try: 
                    arguments = json.loads(arguments)
                except Exception as e:
                    return "An Error was raised when trying to json.loads(your arguments): " + str(e)
            
            if not isinstance(arguments, dict):
                return "Arguments must be a dcitionary after json.loads(), fix this issue and call again with correct json format"
            
            try:
                results = function_call(**arguments)
            except Exception as e:
                return f"Something went wrong. Try again, if this exact same error occured a lot of times {e} then just move on"
            
            return results

        return f"Function with name ${function_name} not found"
    
    def scrape(self):
        ftsc = FuzztainerScraper(self.image_name)
        return ftsc.scrape()    


    def get_help_page(self, command): 
        context = " "

        commands_flags = [
            "--help", "--version", "-h", "-?"
        ]

        for flag in commands_flags:
            if len(context) > 100000:
                return context

            try:
                process = self.t.run_command([command, flag])
                stdout, stderr = process.communicate(timeout=2)
                
                if stdout.decode('utf-8') != '' and stderr.decode('utf-8') == '':
                    if 'exec failed' not in stdout.decode('utf-8'):
                        context += (f"POSSIBLE USEFUL INFO: {str(stdout.decode('utf-8'))} \n")

            except Exception as e:
                context += (f"{command} {flag} timed out after two seconds\n")

        if len(context) == 0 or context.strip() == '':
            return "No context was found"

        context += " Only use the results of these commands as info, do not use the commands itself when craftin your command"

        return context
    

    def test_command(self, commandsAndMetadata):
        print("IN TEST COMMAND")
        if len(self.test_command_runs) >= 5:
            return f"You are not allowed to run any more test command. Please continue and craft the command using all your previous information from your previous 5 test commands: {self.test_command_runs}"
        result = self.run_command(commandsAndMetadata, end_check=True)
        self.test_command_runs.append(result)

        print(f"\n(TEST COMMAND) COMMAND: {result['command']}")
        print(f"\n(TEST COMMAND) STDERR: {result['stderr']}")
        
        output = f"This is the stdout and stderr of your commands: {result}. Use the information of the stdout and stderr as context to craft your final command, if the command worked well, then use keep in mind the parts of these commands (flags, types of inputs) that worked well in crafting the final commands. If the commands didnt work well then keep in mind what parts made it not work well and tend to not use it in the final command."
        if len(self.test_command_runs) == 5:
            output += f" You are not allowed to run any more test command, craft the command with the previous information you have gotten from the commands to craft your final command. Her are your previous 5 test commands and results: {self.test_command_runs}"
            self.tool_choice = "none"
        else:
            output += f"If you need more information, you can run {5 - len(self.test_command_runs)} more test commands"



        return output

    def run_command(self, commandsAndMetadata, end_check=False):        
        print("IN RUN COMMAND")
        if type(commandsAndMetadata) is not dict:
            try:
                data = json.loads(commandsAndMetadata)
            except Exception as e:
                return f"An exception has occured within the run_command tool trying to json.loads(commandsAndMetadata): {str(e)}. Fix the structure of your input paramter and try again. Not a single character before or after (dont add '''json), Start and end with brackets. Make sure the argument can be converted to valid json: there are no unterminated strings, unterminated anything, no new line '\\n' characters, just the eact json in a single line surrounded by single quotes"
        else:
            data = commandsAndMetadata

        if type(data) is not dict:
            return f"After sucesfully json.loads(commandsAndMetadata), the type of data is not dict. Fix this and run again. This is the data you gave me which i used json.loads for: {data} and its type is {type(data)}"

        if 'commandsAndMetadata' in data:
            data = data['commandsAndMetadata']

        if type(data) is not dict:
            return f"After sucesfully json.loads(commandsAndMetadata), the type of data is not dict. Fix this and run again. This is the data you gave me which i used json.loads for: {data} and its type is {type(data)}"

        if 'commands' in data:
            data = data['commands']

        if type(data) is not dict:
            if type(data) is list:
                return "Do not give me a list. Only give me one command to run at a time."
            return f"the data is not a valid json parsable string, it is instead type: {type(data)} after json.loads()"

        if 'directories' in data:
            for directory in data['directories']:
                self.t.run_command(["mkdir", str(directory)]).communicate()
        
        if 'files' in data:
            for file in data['files']:
                if 'name' and 'content' not in file:
                    return f"Within each file field there must be always be two fields named 'name' and 'content' even if its blank. Missing name or content field in {block}. Fix this mistake and return this and the rest of the commands. Here our the results of the commands so far: {result}"
                self.t.run_command(["touch", file['name']]).communicate()
                if 'content'in file:
                    self.t.run_command(["echo", file['content'], " > ", file['name']]).communicate()

        stdout = ""
        stderr = ""

        try:
            stdout, stderr = self.t.run_command(data['command'].split(" ")).communicate(timeout=3)
        except Exception as e:
            print("run_command timeout expired")
            stdout, stderr = (b'', b'')

        result = {
            "command": data['command'],
            "stdout": stdout.decode('utf-8'), 
            "stderr": stderr.decode('utf-8'), 
        }

        if end_check:
            return result
        
        print(f"\n(RUN COMMAND) COMMAND: {data['command']}")
        print(f"\n(RUN COMMAND) STDERR: {result['stderr']}")

        if result['stderr'] == '':
            return f"Congratulations, the command '{data['command']}' has no stderr, this means you can finally return without running any more run commands"

        output = f"This is the command, the stdout, and the stderr results of running the command: ###{str(result)}###\n"

        if 'error' in result['stderr'].lower():
            output += "The keyword 'error' was found in the stderr, this probaly signals that the command isnt working properly. Make sure to analyze the information alter change the part of the command that isnt working properly and try again. Try your best to change the command to resolve the issue.\n"
        if 'crash' in result['stderr'].lower():
            output += "The keyword 'crash' was found in the stderr, this probaly signals that the command isnt working properly. Make sure to analyze the information and alter the part of the command that isnt working properly and try again. Try your best to change the command to resolve the issue.\n"
        if 'exception' in result['stderr'].lower():
            output += "The keyword 'exception' was found in the stderr, this probaly signals that the command isnt working properly. Make sure to analyze the information and alter the part of the command that isnt working properly and try again. Try your best to change the command to resolve the issue.\n"
        if 'fault' in result['stderr'].lower():
            output += "The keyword 'fault' was found in the stderr, this probaly signals that the command isnt working properly. Make sure to analyze the information alter change the part of the command that isnt working properly and try again. Try your best to change the command to resolve the issue.\n"

        if 'files' in result['stderr'] or 'file' in result['stderr']:
            if 'missing' in result or 'exist' in result or 'not found' in result:
                output += "The keywords 'files' or 'file' and 'missing, exist, or not found' were found in the stderr, this probaly signals that file(s) are missing, if that is the case, thn make sure to add all the files required in the metadata of the command in the 'files' field. After doing this try again."

        if 'directory' in result['stderr'] or 'directories' in result['stderr']:
            if 'missing' in result or 'exist' in result or 'not found' in result:
                output += "The keywords 'directory' or 'directory' and 'missing, exist, or not found were found in the stderr, this probaly signals that a directory is missing, if that is the case, thn make sure to add all the files required in the metadata of the command in the 'files' field. After doing this try again."

        return  output
