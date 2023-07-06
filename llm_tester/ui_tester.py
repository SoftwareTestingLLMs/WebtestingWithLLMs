import os.path
import time
import openai
from pathlib import Path
import urllib.parse
import json
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
from bs4 import BeautifulSoup
from datetime import datetime
import logging
import shutil


def filter_html(html_string):
    soup = BeautifulSoup(html_string, "html.parser")

    # Remove all script and style elements
    for script in soup(["script", "style"]):
        script.decompose()

    # Remove the div with id 'coverage'
    coverage_div = soup.find(id="coverage")
    if coverage_div:
        coverage_div.decompose()

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


def run_ui_test(url, delay, interactions, load_wait_time, test_type, output_dir):
    # Check if the given URL is a local file path
    if os.path.isfile(url):
        # If it is a local file, convert the file path to a proper URL
        url = Path(url).as_uri()
    elif not urllib.parse.urlsplit(url).scheme:
        # If it's a relative file path, convert it to an absolute path first, then to a proper URL
        url = Path(os.path.abspath(url)).as_uri()

    # Set up logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")

    # Set up file and console handlers for logging
    log_path = "temp_output.log"  # Creating a temporary log file
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info(f"Starting the test on URL: {url}")

    # OpenAI key loading would be required here
    with open("openai_key.json", "r") as file:
        openai.api_key = json.load(file)["key"]

    # Open the web browser and navigate to the app's URL
    browser = webdriver.Chrome()
    browser.get(url)

    # Wait for the elements to load
    WebDriverWait(browser, load_wait_time).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )
    logger.info("Web page loaded successfully.")

    # Get the filtered HTML source code of the page
    filtered_html = filter_html(browser.page_source)

    # Start testing
    past_actions = []
    for i in range(interactions):
        # Refresh the list of buttons before each interaction
        buttons = browser.find_elements(By.XPATH, "//button")
        display_element = browser.find_element(By.ID, "display")

        element = None
        if test_type == "monkey":
            # Choose a random button
            element = random.choice(buttons)
        elif test_type in ["gpt-4", "gpt-3.5-turbo"]:
            # Create list of clickable elements using IDs
            clickable_elements_data = [button.get_attribute("id") for button in buttons]

            # Create the prompt for the GPT model with task description
            prompt = (
                f"Given a web application, you are tasked with testing its functionality. "
                f"Here is the filtered HTML source code of the web application: '{filtered_html}'. "
                f"Here are the available interactable GUI elements: {clickable_elements_data}. "
                f"Here are the ordered past actions that you have done for this test (first element was the first action of the test and the last element was the previous action): {format_past_actions(past_actions)}"
                f"Please output the id of the element to click on next and provide a brief explanation or reasoning for your choice. "
                f"Remember, the goal is to test as many different features as possible to find potential bugs and make sure to include edge cases."
            )

            # Define the function for GPT
            functions = [
                {
                    "name": "select_element",
                    "description": "Selects an element given its ID and provides an explanation for the choice",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "The id of the element to select",
                            },
                            "explanation": {
                                "type": "string",
                                "description": "The reasoning behind the selection of this element",
                            },
                        },
                        "required": ["id", "explanation"],
                    },
                }
            ]

            # Ask the GPT model for the next action
            response = openai.ChatCompletion.create(
                model=test_type,
                messages=[{"role": "user", "content": prompt}],
                functions=functions,
                function_call={"name": "select_element"},
            )

            response_message = response["choices"][0]["message"]

            # Check if GPT wanted to call a function
            if response_message.get("function_call"):
                function_args = json.loads(
                    response_message["function_call"]["arguments"]
                )
                action_id = function_args.get("id")
                logger.info(function_args.get("explanation"))

                for button in buttons:
                    if button.get_attribute("id") == action_id:
                        element = button
                        break
                if not element:
                    raise Exception(f"No button found with id: {action_id}")
            else:
                raise Exception(
                    f"The model did not make a function call in the response: {response_message}"
                )

        else:
            raise ValueError(f"Invalid test type: {test_type}")

        element.click()

        # Check for alert and accept it if present
        try:
            alert = browser.switch_to.alert
            logger.info(f"Alert found with message: {alert.text}. Accepting it.")
            alert.accept()
        except Exception as e:
            pass  # no alert, so pass

        # Get coverage percentage
        try:
            coverage_element = browser.find_element(By.ID, "percentage")
            coverage_text = coverage_element.text
            coverage_percentage = re.search(r"(\d+.\d+)%", coverage_text).group(1)
        except Exception as e:
            logger.info(
                f"Could not find coverage element or extract percentage: {str(e)}"
            )
            coverage_percentage = None

        # Record the observation after the action
        current_observation = display_element.get_attribute("value")
        current_action = element.get_attribute("id")

        logger.info(
            f"Action {i+1}: {test_type.capitalize()} tester clicking button with id: '{current_action}' | Current observation: {current_observation} | Coverage: {coverage_percentage}%"
        )

        # Record action
        past_actions.append(
            {
                "step": (i + 1),
                "action": current_action,
                "observation": current_observation,
                "coverage percentage": coverage_percentage,
            }
        )

        time.sleep(delay)  # Wait a bit between actions for the page to update

    # Extract and log the code coverage data after all interactions
    coverage_json_string = browser.execute_script("return JSON.stringify(coverage)")
    coverage_data = json.loads(coverage_json_string)
    covered_blocks = sum(
        1
        for function in coverage_data.values()
        for block, times in function.items()
        if times > 0
    )
    total_blocks = sum(len(function) for function in coverage_data.values())
    coverage_percentage = (
        round((covered_blocks / total_blocks) * 100, 2) if total_blocks > 0 else 0
    )

    logger.info(f"Final coverage data: {json.dumps(coverage_data, indent=2)}")

    logger.info(
        f"Detailed coverage calculation explanation: Out of the total number of {total_blocks} blocks across all functions, "
        f"{covered_blocks} were covered (i.e., executed at least once during the test). This leads to a final "
        f"coverage percentage of {coverage_percentage}%. This percentage represents the ratio of the number of "
        f"covered blocks to the total number of blocks, giving equal weight to each block."
    )

    # Close the driver
    logger.info("Test run completed.")
    browser.quit()

    # Save click arguments
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

    with open(os.path.join(output_dir, "config.json"), "w") as file:
        json.dump(config, file, indent=4)

    # Save past actions to an output file
    with open(os.path.join(output_dir, "past_actions.json"), "w") as file:
        json.dump(past_actions, file, indent=4)

    logger.info(
        f"Past actions saved to: {os.path.join(output_dir, 'past_actions.json')}"
    )

    # Move the temp log file to the final output directory
    final_log_path = os.path.join(output_dir, "output.log")
    shutil.move(log_path, final_log_path)
    logger.info(f"Logs saved to: {final_log_path}")
