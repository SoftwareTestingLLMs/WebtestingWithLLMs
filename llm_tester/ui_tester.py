import os.path
import time
import openai
from pathlib import Path
import urllib.parse
import json
import re
import string
from enum import Enum
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
from bs4 import BeautifulSoup
from datetime import datetime
from types import SimpleNamespace

def filter_html(html_string):
    soup = BeautifulSoup(html_string, "html.parser")

    # Remove all script and style elements
    for script in soup(["script", "style", "meta", "link", "noscript"]):
        script.decompose()

    # Convert HTML object back to a string without additional newlines
    text = str(soup)

    return text

def custom_logger(msg, log_messages):
    print(msg)
    log_messages.append(f"{datetime.now()}:{msg}")
    return log_messages

def is_clickable(element, driver):
    return element.is_displayed() and element.is_enabled()

def extract_coverage(driver):
    coverage_json = driver.execute_script("return JSON.stringify(window.__coverage__)")
    try:
        os.makedirs(".nyc_output")
    except FileExistsError:
        pass
    with open(".nyc_output/out.json", "w") as file:
        file.write(coverage_json)
    coverage_report = os.popen("npx nyc report --reporter=text-summary --cwd=.. -t WebtestingWithLLMs/.nyc_output").read()
    coverage_search_result = re.search(r"Branches\s+: \d+(?:\.\d+)?% \( (\d+)\/(\d+) \)", coverage_report)
    branches_hit = int(coverage_search_result.group(1))
    branches_total = int(coverage_search_result.group(2))
    percentage = branches_hit / branches_total
    return SimpleNamespace(covered=branches_hit, blocks=branches_total, percentage=percentage)

class ArgDescriptor:
    def __init__(self, name, description, randomizeValue):
        self.name = name
        self.description = description
        self.randomizeValue = randomizeValue

class ActionType:
    def __init__(self, name, description, action, **kwargs):
        self.name = name
        self.action = action
        self.description = description
        self.args = kwargs["args"] if "args" in kwargs else []
        self.silent_exceptions = kwargs["silent_exceptions"] if "silent_exceptions" in kwargs else []
        self.adjective = kwargs["adjective"] if "adjective" in kwargs else name + "able"

def random_string():
    return ''.join(random.choices(string.ascii_letters + string.digits + ' @.', k = random.randint(3, 9)))

class ActionTypes(Enum):
    CLICK = ActionType('click', 'clicks on a html element', lambda action, driver, args: action.element.click(), silent_exceptions=[ElementClickInterceptedException])
    HOVER = ActionType('hover', 'moves the mouse over an html element', lambda action, driver, args: ActionChains(driver).move_to_element(action.element).perform())
    SEND_KEYS = ActionType('send_keys', 'sends keystrokes to an html element', lambda action, driver, args: action.element.send_keys(args[0]), args=[ArgDescriptor('keys', 'the keys to be sent to the input element', random_string)], adjective='writable')
    CLEAR = ActionType('clear', 'resets the contents of an html element', lambda action, driver, args: action.element.clear())

class Action:

    def __init__(self, element, action_type):
        self.element = element
        self.type = action_type
        self.id = element.get_attribute("id")
        self.attributes = None
        if element is None or element.get_attribute("id") == "":
            raise Exception("No id in element " + element.get_attribute('outerHTML'))
    
    def execute(self, driver):
        self.type.action(self, driver, self.attributes)
    
    def action_id(self):
        return self.id + self.type.name
    
    def __str__(self):
        return "action: " + self.type.name + ('(' + ' '.join(self.attributes) + ')' if not self.attributes is None else '') + " element: " + self.element.get_attribute('outerHTML')

    def should_fail_silently(self, on_exception):
        return any(map(lambda e: isinstance(on_exception, e), self.type.silent_exceptions))
    
    def with_random_args(self):
        if len(self.type.args) != 0:
            self.attributes = list(map(lambda arg: arg.randomizeValue(), self.type.args))
        return self

def extract_actions(driver):
    actions = []
    hidden_by = dict()
    def is_on_top(e):
        id = e.get_attribute("id")
        topmost = get_element_on_top(e, driver)
        if topmost != id:
            hidden_by[id] = topmost
            return False
        return True
    clickables = driver.find_elements(By.XPATH, "//button") + driver.find_elements(By.XPATH, "//a") + driver.find_elements(By.CSS_SELECTOR, ".on-click")
    clickable_dict = dict()
    for element in clickables:
        id = element.get_attribute("id")
        if id not in clickable_dict and is_clickable(element, driver):
            clickable_dict[id] = element
    clickables = list(clickable_dict.values())
    actions += map(lambda b: Action(b, ActionTypes.CLICK.value), filter(is_on_top, clickables))

    mouse_overs = driver.find_elements(By.CSS_SELECTOR, ".mouse-over")
    actions += map(lambda e: Action(e, ActionTypes.HOVER.value), filter(is_on_top, mouse_overs))

    text_fields = list(filter(is_on_top, driver.find_elements(By.XPATH, "//input[@type='text']")))
    actions += map(lambda e: Action(e, ActionTypes.SEND_KEYS.value), text_fields)
    actions += map(lambda e: Action(e, ActionTypes.CLEAR.value), filter(lambda t: t.get_attribute("value") != "", text_fields))

    return actions, hidden_by

def get_element_on_top(element, driver):
    # Scolls to the element and returns the id of the topmost element at the middle of the element.
    # If the supplied element is a parent of the topmost element, returns the id of the supplied element.
    # If the element is not displayed, returns an empty string.

    if not element.is_displayed():
        return ""
    id = element.get_attribute("id")
    script = (
        f"var doc = document.getElementById(\"{id}\");"
        f"doc.scrollIntoView();"
        f"return doc.getBoundingClientRect();"
    )
    rect = driver.execute_script(script)
    element = driver.find_element(By.ID, id)
    middle_point_y = rect["y"] + rect["height"] / 2
    middle_point_x = rect["x"] + rect["width"] / 2
    ret = driver.execute_script(
        f"var topmost = document.elementFromPoint({middle_point_x}, {middle_point_y});"
        f"var topmostId = topmost?.id || \"\";"
        f"while (topmost != null) {{"
        f"    if (topmost.id == \"{id}\") return topmost.id;"
        f"    topmost = topmost.parentElement;"
        f"}}"
        f"return topmostId;"
    )
    return ret

def flatten(l):
    return [item for sublist in l for item in sublist]

def run_ui_test(url, delay, interactions, load_wait_time, test_type, output_dir, llm_instructions):
    # Check if the given URL is a local file path
    if os.path.isfile(url):
        # If it is a local file, convert the file path to a proper URL
        url = Path(url).as_uri()
    elif not urllib.parse.urlsplit(url).scheme:
        # If it's a relative file path, convert it to an absolute path first, then to a proper URL
        url = Path(os.path.abspath(url)).as_uri()

    log_messages = []

    config = {
        "url": url,
        "delay": delay,
        "interactions": interactions,
        "load_wait_time": load_wait_time,
        "test_type": test_type,
        "output_dir": output_dir,
    }

    llm_instructions = "The goal is to test as many different features as possible to find potential bugs, so make sure to include edge cases." if llm_instructions is None else llm_instructions

    # Time-stamp to uniquely identify this run
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create a unique subfolder for each test run
    output_dir = os.path.join(output_dir, timestamp)

    # Create results directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Add configuration to log
    log_messages = custom_logger(
        f"Configuration: {json.dumps(config, indent=2)}", log_messages
    )

    log_messages = custom_logger(f"Starting the test on URL: {url}", log_messages)

    # OpenAI key loading would be required here
    if test_type != "monkey":
        with open("openai_key.json", "r") as file:
            openai.api_key = json.load(file)["key"]

    # Open the web browser and navigate to the app's URL
    browser = webdriver.Chrome()
    browser.get(url)
    time.sleep(delay)

    # Wait for the elements to load
    WebDriverWait(browser, load_wait_time).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    log_messages = custom_logger("Web page loaded successfully.", log_messages)

    interactions_by_goal = dict()
    current_goal = None

    # Start testing
    past_actions = []

    past_messages = []
    for i in range(interactions):
        # Refresh the list of buttons before each interaction
        action_dict = dict()
        actions, hidden_by = extract_actions(browser)
        for action in actions:
            action_dict[action.action_id()] = action

        # Get the filtered HTML source code of the page
        filtered_html = filter_html(browser.page_source)

        # Save click arguments
        with open(os.path.join(output_dir, "page_" + str(i) + ".html"), "w") as file:
            file.write(filtered_html)

        action_string = None
        success = False
        previous_misdemeanor = False
        previous_id = None
        previous_type = None
        misdemeanor_count = 0
        while not success:
            if test_type == "monkey":
                # Choose a random button
                action = random.choice(list(action_dict.values())).with_random_args()
            elif test_type in ["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo-preview"]:

                # Break if the model is not doing as told
                if misdemeanor_count > 5:
                    raise Exception("Tried to use implossible actions too many times. Previous action was " + str(previous_type) + " with id " + str(previous_id) + ".")

                # Remove past html from the input to the model
                for past_message in past_messages:
                    if past_message["role"] == "function":
                        past_message["content"] = "omitted"

                # Append the filtered HTML to the past messages, 
                if len(past_messages) > 0:
                    past_messages.append({"role": "function", "name": "emulate_interaction", "content": filtered_html})
                
                # Only keep the last 10 messages, this means 5 interactions
                past_messages = past_messages[-10:]
                                          
                # Create the prompt for the GPT model with task description
                prompt_system = (
                    f"Given a web application, you are tasked with assisting in testing its functionality. "
                    f"The emulate_interaction function takes an interaction as input and emulates it on the web application. "
                    f"The return value of the function is the new, filtered HTML source code of the web application. "
                    f"The source code of previous interactions will be omitted from the input to the assistant. "
                    f"You may define high-level testing goals using the new_testing_goal argument."
                )
                few_shot_examples = [[
                    {
                        "role": "assistant",
                        "function_call": {
                            "name": "emulate_interaction",
                            "arguments": json.dumps({
                                "page_description": "The start page of a web site with multiple calculators for different purposes. There are buttons to navigate to the differet calculators and a button to switch the language of the web site. The current language is English.",
                                "new_testing_goal": "Test the calculator for calculating the area of a circle in multiple languages.",
                                "interaction": {
                                    "interaction_type": "click",
                                    "element_id": "btn-area-circle",
                                },
                                "explanation": "Clicking the 'Circle Area' button to navigate to the calculator for calculating the area of a circle.",
                            }),
                        },
                    },
                    {
                        "role": "function",
                        "name": "emulate_interaction",
                        "content": "omitted"
                    },
                    {
                        "role": "assistant",
                        "function_call": {
                            "name": "emulate_interaction",
                            "arguments": json.dumps({
                                "page_description": "A page with a calculator for calculating the area of a circle. There is an empty text field to enter the radius of the circle and a button labeled 'Calculate'. The current language is English.",
                                "interaction": {
                                    "interaction_type": "send_keys",
                                    "element_id": "radius",
                                    "keys": "5",
                                },
                                "explanation": "Entering the radius of the circle into the text field.",
                            }),
                        },
                    },
                ], [
                    {
                        "role": "assistant",
                        "function_call": {
                            "name": "emulate_interaction",
                            "arguments": json.dumps({
                                "page_description": "An article on a news website. The main part of the article is hidden by a login paywall. The navigation bar has links to different news categories.",
                                "new_testing_goal": "Subscribe to the comment section of the article.",
                                "interaction": {
                                    "interaction_type": "send_keys",
                                    "element_id": "user-id",
                                    "keys": "john.doe@fictional.tld",
                                },
                                "explanation": "Entering the email address into the login field, because the user is not logged in.",
                            }),
                        },
                    }
                ]]
                prompt = (
                    f"Here is the filtered HTML source code of the web application: '{filtered_html if len(past_messages) == 0 else 'omitted'}'. "
                ) + "" if llm_instructions is None else " " + llm_instructions
                messages = [
                    { "role": "system", "content": prompt_system },
                    { "role": "system", "content": f"Here are some examples how the 'emulate_interaction' function should be used." },
                    *flatten(map(lambda example: [{ "role": "user", "content": "Please test my website: omitted"}, *example], few_shot_examples)),
                    { "role": "user", "content": prompt },
                    *past_messages,
                ]

                # Create the schema for the function call
                actions_by_type = dict()
                for action in action_dict.values():
                    if action.type.name not in actions_by_type:
                        actions_by_type[action.type.name] = []
                    actions_by_type[action.type.name].append(action)
                
                # For each action type, create a json schema as output for the GPT model
                interactions = []
                for action_type_name in actions_by_type:
                    action_type = actions_by_type[action_type_name][0].type
                    properties = dict()
                    properties["interaction_type"] = {"const": action_type.name, "type": "string", "description": "The type of interaction to emulate"}
                    properties["element_id"] = {"enum": [action.id for action in actions_by_type[action_type_name]], "type": "string", "description": "The id of the element to interact with"}

                    for arg in action_type.args:
                        properties[arg.name] = {"type": "string", "description": arg.description}

                    interactions.append({
                        "type": "object",
                        "properties": properties,
                        "required": list(properties.keys()),
                        "description": action_type.description,
                    })
                
                schema = {
                    "type": "object",
                    "properties": {
                        "page_description": {
                            "type": "string",
                            "description": "A short textual description of the state of the web application",
                        },
                        "new_testing_goal": {
                            "type": "string",
                            "description": "Assigns a new high level goal that needs to be followed in order to complete the users instructions. This goal should take multiple user interactions to complete. The assistant shall try to complete this goal in the next couple of interactions and then assign a new one.",
                        },
                        "interaction": {
                            "anyOf": interactions,
                            "description": "The interaction to emulate",
                        },
                        "explanation": {
                            "type": "string",
                            "description": "A short explanation of why the interaction was chosen",
                        },
                    },
                    "required": ["page_description", "new_testing_goal", "interaction", "explanation"] if current_goal is None else ["page_description", "interaction", "explanation"],
                }

                functions = [
                    {
                        "name": "emulate_interaction",
                        "description": "Emulates a user interaction with the web application",
                        "parameters": schema,
                    },
                ]

                # Add a message telling the model to only click on clickable elements, etc.
                theModelIsStupidMessage = ""
                for interaction in interactions:
                    type_name = interaction["properties"]["interaction_type"]["const"]
                    action_type = ActionTypes[type_name.upper()].value
                    adjective = action_type.adjective
                    theModelIsStupidMessage += f"Only use the {type_name} action with {adjective} elements. The {adjective} elements have the following ids: {', '.join(interaction['properties']['element_id']['enum'])}. "

                if previous_misdemeanor:
                    if type(previous_id) is str:
                        theModelIsStupidMessage += f"You cannot use the {json.dumps(previous_type)} action with the element id {json.dumps(previous_id)} because it is not applicable. "
                    else:
                        theModelIsStupidMessage += f"You cannot use the {json.dumps(previous_type)} action with the element id {json.dumps(previous_id)} because ids must be strings. "
                
                if not current_goal is None:
                    messages.append({"role": "system", "content": f"The user provided the following end goal: {llm_instructions}."})
                    messages.append({"role": "system", "content": f"Pursue your self-assigned sub goal or assign a new one: {current_goal}."})
                    messages.append({"role": "system", "content": f"Previously executed interactions by goal: {json.dumps(interactions_by_goal)}."})
                    # if all goals have been explored to some extent, remind the model to try to find new goals
                    if all(map(lambda goal: interactions_by_goal.get(goal, 0) > 5, interactions_by_goal)):
                        theModelIsStupidMessage += f"Remember that you can assign completely new high-level goals using the new_testing_goal argument. "
                    messages.append({"role": "system", "content": f"Start by describing the website supplied by the function call. Give a short general description first then summarize the main elements on the website. Do not use HTML in your description. Either stick to your current goal '{current_goal}' or formulate a new high level goal that should be executed. Take the necessary actions to complete it."})
                else:
                    messages.append({"role": "system", "content": f"Start by describing the website supplied by the user. Give a short general description first then summarize the main elements on the website. Do not use HTML in your description. Then formulate a high level goal that should be executed and take the necessary actions to complete it."})

                messages.append({"role": "system", "content": theModelIsStupidMessage})

                # Ask the GPT model for the next action
                response = openai.ChatCompletion.create(
                    model=test_type,
                    messages=messages,
                    functions=functions,
                    function_call={"name": "emulate_interaction"},
                )

                # Log the api call and the response to an output file
                with open(os.path.join(output_dir, "api_call_" + str(i + 1) + ".json"), "w") as file:
                    json.dump({ "response": response, "messages": messages, "functions": functions }, file, indent=2)

                response_message = response["choices"][0]["message"]
                

                # Check if GPT wanted to call a function
                if response_message.get("function_call"):
                    function_args = json.loads(
                        response_message["function_call"]["arguments"]
                    )
                    interaction = function_args.get("interaction")
                    action_type = interaction.get("interaction_type")
                    action_element_id = interaction.get("element_id")
                    if not type(action_element_id) is str:
                        previous_misdemeanor = True
                        previous_id = action_element_id
                        previous_type = action_type
                        misdemeanor_count += 1
                        log_messages = custom_logger(
                            f"Action {i+1}: {test_type.capitalize()} tester executiong: '{response_message}' | The model tried to use a non-string element id. | Trying again.", log_messages
                        )
                        continue
                    # find an action that matches the id and type
                    selected_action = action_dict.get(action_element_id + action_type)
                    if action_element_id in hidden_by:
                        log_messages = custom_logger(
                            f"Action {i+1}: {test_type.capitalize()} tester executiong: '{response_message}' | The model tried to use an element that is hidden by {hidden_by[action_element_id]}. | Trying again.", log_messages
                        )
                        hiding_element_id = hidden_by[action_element_id]
                        past_messages.append(response_message)
                        if hiding_element_id == "":
                            past_messages.append({"role": "system", "content": "Error: This element is hidden by another element and can not be interacted with."})
                        else:
                            past_messages.append({"role": "system", "content": f"Error: This element is hidden by the element with the id {hiding_element_id} and can not be interacted with."})
                        continue
                    if selected_action is None:
                        previous_misdemeanor = True
                        previous_id = action_element_id
                        previous_type = action_type
                        misdemeanor_count += 1
                        log_messages = custom_logger(
                            f"Action {i+1}: {test_type.capitalize()} tester executiong: '{response_message}' | The model tried to use an impossible action, even after being told not to. | Trying again.", log_messages
                        )
                        continue
                    new_goal = function_args.get("new_testing_goal")
                    if new_goal is not None:
                        current_goal = new_goal
                        log_messages = custom_logger(
                            f"Action {i+1}: {test_type.capitalize()} | Setting new goal: {current_goal}.", log_messages
                        )
                    interactions_by_goal[current_goal] = interactions_by_goal.get(current_goal, 0) + 1
                    misdemeanor_count = 0
                    selected_action.attributes = [interaction.get(arg_descriptor.name) for arg_descriptor in selected_action.type.args]
                    action = selected_action
                    previous_misdemeanor = False
                    past_messages.append(response_message)
                else:
                    raise Exception(
                        f"The model did not make a function call in the response: {response_message}"
                    )
                

            else:
                raise ValueError(f"Invalid test type: {test_type}")

            try:
                action_string = str(action)
                action.execute(browser)
                success = True
            except Exception as e:
                if action.should_fail_silently(e):
                    log_messages = custom_logger(
                        f"Action {i+1}: {test_type.capitalize()} tester executiong: '{action_string}' | Failed with exception: {str(e)} | Removed from pool of available actions. | Trying again.", log_messages
                    )
                    del action_dict[action.action_id()]
                else:
                    raise e

        # Check for alert and accept it if present
        try:
            alert = browser.switch_to.alert
            log_messages = custom_logger(
                f"Alert found with message: {alert.text}. Accepting it.", log_messages
            )
            alert.accept()
        except Exception as e:
            pass  # no alert, so pass

        # Get coverage percentage
        try:
            coverage_percentage = extract_coverage(browser).percentage
        except Exception as e:
            log_messages = custom_logger(
                f"Could not find coverage element or extract percentage: {str(e)}",
                log_messages,
            )
            coverage_percentage = None

        # Record the observation after the action
        current_observation = "todo" #display_element.get_attribute("value")

        log_messages = custom_logger(
            f"Action {i+1}: {test_type.capitalize()} tester executiong: '{action_string}' | Coverage: {100*coverage_percentage}%",
            log_messages,
        )

        # Record action
        past_actions.append(
            {
                "step": (i + 1),
                "action": action_string,
                "observation": current_observation,
                "coverage percentage": coverage_percentage,
            }
        )

        time.sleep(delay)  # Wait a bit between actions for the page to update

    # Extract and log the code coverage data after all interactions
    coverage = extract_coverage(browser)

    log_messages = custom_logger(
        f"Final coverage data: {str(coverage)}", log_messages
    )

    log_messages = custom_logger(
        f"Detailed coverage calculation explanation: Out of the total number of {coverage.blocks} blocks across all functions, "
        f"{coverage.covered} were covered (i.e., executed at least once during the test). This leads to a final "
        f"coverage percentage of {coverage.percentage * 100}%. This percentage represents the ratio of the number of "
        f"covered blocks to the total number of blocks, giving equal weight to each block.",
        log_messages,
    )

    # Close the driver
    log_messages = custom_logger("Test run completed.", log_messages)
    browser.quit()


    # Save click arguments
    with open(os.path.join(output_dir, "config.json"), "w") as file:
        json.dump(config, file, indent=4)

    # Save past actions to an output file
    with open(os.path.join(output_dir, "past_actions.json"), "w") as file:
        json.dump(past_actions, file, indent=4, default=lambda obj: obj.__dict__)

    log_messages = custom_logger(
        f"Past actions saved to: {os.path.join(output_dir, 'past_actions.json')}",
        log_messages,
    )

    # Save log messages to a log file
    with open(os.path.join(output_dir, "output.log"), "w") as log_file:
        for message in log_messages:
            log_file.write(f"{message}\n")

    log_messages = custom_logger(
        f"Logs saved to: {os.path.join(output_dir, 'output.log')}", log_messages
    )

    return log_messages, past_actions
