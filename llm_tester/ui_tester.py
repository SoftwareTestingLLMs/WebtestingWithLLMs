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

def format_past_actions(past_actions):
    if not past_actions:
        return "No actions available. "

    formatted_actions = "\n"
    for action in past_actions:
        formatted_actions += f"Step {action['step']}: Action: {action['action']} | Observation: {action['observation']} | Coverage Percentage: {action['coverage percentage']}%\n"
    return formatted_actions

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
    def __init__(self, name, description, action, silentExceptions = [], args = []):
        self.name = name
        self.action = action
        self.description = description
        self.args = args
        self.silent_exceptions = silentExceptions

def random_string():
    return ''.join(random.choices(string.ascii_letters + string.digits + ' @.', k = random.randint(3, 9)))

class ActionTypes(Enum):
    CLICK = ActionType('click', 'clicks on a html element', lambda action, driver, args: action.element.click(), [ElementClickInterceptedException])
    HOVER = ActionType('hover', 'moves the mouse over an html element', lambda action, driver, args: ActionChains(driver).move_to_element(action.element).perform())
    SEND_KEYS = ActionType('send_keys', 'sends keystrokes to an html element', lambda action, driver, args: action.element.send_keys(args[0]), [], [ArgDescriptor('keys', 'the keys to be sent to the input element', random_string)])
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

    clickables = driver.find_elements(By.XPATH, "//button") + driver.find_elements(By.XPATH, "//a") + driver.find_elements(By.CSS_SELECTOR, ".on-click")
    clickable_dict = dict()
    for element in clickables:
        id = element.get_attribute("id")
        if id not in clickable_dict and is_clickable(element, driver):
            clickable_dict[id] = element
    clickables = list(clickable_dict.values())
    actions += map(lambda b: Action(b, ActionTypes.CLICK.value), clickables)

    mouse_overs = driver.find_elements(By.CSS_SELECTOR, ".mouse-over")
    actions += map(lambda e: Action(e, ActionTypes.HOVER.value), mouse_overs)

    text_fields = driver.find_elements(By.XPATH, "//input[@type='text']")
    actions += map(lambda e: Action(e, ActionTypes.SEND_KEYS.value), text_fields)
    actions += map(lambda e: Action(e, ActionTypes.CLEAR.value), filter(lambda t: t.get_attribute("value") != "", text_fields))

    return actions

def run_ui_test(url, delay, interactions, load_wait_time, test_type, output_dir):
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

    # Start testing
    past_actions = []
    for i in range(interactions):
        # Refresh the list of buttons before each interaction
        action_dict = dict()
        for action in extract_actions(browser):
            action_dict[action.action_id()] = action

        # Get the filtered HTML source code of the page
        filtered_html = filter_html(browser.page_source)

        # Save click arguments
        with open(os.path.join(output_dir, "page_" + str(i) + ".html"), "w") as file:
            file.write(filtered_html)

        success = False
        while not success:
            element = None
            if test_type == "monkey":
                # Choose a random button
                action = random.choice(list(action_dict.values())).with_random_args()
            elif test_type in ["gpt-4", "gpt-3.5-turbo"]:
                # Create list of clickable elements using IDs
                clickable_elements_data = "in the function" #[button.get_attribute("id") for button in buttons]

                # Create the prompt for the GPT model with task description
                prompt_system = (
                    f"Given a web application, you are tasked with testing its functionality."
                )
                prompt = (
                    f"Here is the filtered HTML source code of the web application: '{filtered_html}'. "
                    f"Please output the id of the element to interact with. "
                    f"Remember, the goal is to test as many different features as possible to find potential bugs, so make sure to include edge cases."
                )
                messages = [
                    { "role": "system", "content": prompt_system },
                    { "role": "user", "content": prompt },
                ]

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
                    properties["interaction_type"] = {"const": action_type.name}
                    properties["element_id"] = {"enum": [action.id for action in actions_by_type[action_type_name]]}

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
                        "interaction": {
                            "anyOf": interactions,
                            "description": "The interaction to emulate",
                        },
                    },
                    "required": ["interaction"],
                }


                # Define the function for GPT
                functions = [
                    {
                        "name": "emulate_interaction",
                        "description": "Emulates a user interaction with the web application",
                        "parameters": schema,
                    }
                ]

                # Print the function for debugging
                print(json.dumps(functions, indent=2))

                # Ask the GPT model for the next action
                response = openai.ChatCompletion.create(
                    model=test_type,
                    messages=messages,
                    functions=functions,
                    function_call={"name": "emulate_interaction"},
                )

                print(json.dumps(response, indent=2))

                response_message = response["choices"][0]["message"]

                # Check if GPT wanted to call a function
                if response_message.get("function_call"):
                    function_args = json.loads(
                        response_message["function_call"]["arguments"]
                    )
                    interaction = function_args.get("interaction")
                    action_type = interaction.get("interaction_type")
                    action_element_id = interaction.get("element_id")
                    print("action type " + str(action_type) + " element id " + str(action_element_id))
                    # find an action that matches the id and type
                    selected_action = action_dict.get(action_element_id + action_type)
                    if selected_action is None:
                        raise Exception(f"No action found with id: {action_id}")
                    selected_action.attributes = [interaction.get(arg_descriptor.name) for arg_descriptor in selected_action.type.args]
                    action = selected_action
                else:
                    raise Exception(
                        f"The model did not make a function call in the response: {response_message}"
                    )

            else:
                raise ValueError(f"Invalid test type: {test_type}")

            print("executing " + str(action))
            try:
                action.execute(browser)
                success = True
            except Exception as e:
                if action.should_fail_silently(e):
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
            print("coverage " + str(coverage_percentage))
        except Exception as e:
            log_messages = custom_logger(
                f"Could not find coverage element or extract percentage: {str(e)}",
                log_messages,
            )
            coverage_percentage = None

        # Record the observation after the action
        current_observation = "todo" #display_element.get_attribute("value")

        log_messages = custom_logger(
            f"Action {i+1}: {test_type.capitalize()} tester executiong: '{str(action)}' | Current observation: {current_observation} | Coverage: {coverage_percentage}%",
            log_messages,
        )

        # Record action
        past_actions.append(
            {
                "step": (i + 1),
                "action": str(action),
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
        f"coverage percentage of {coverage.percentage}%. This percentage represents the ratio of the number of "
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
