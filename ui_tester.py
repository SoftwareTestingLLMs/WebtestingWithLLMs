import click
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


@click.command()
@click.option(
    "--url",
    default="https://sea-lion-app-q6nwz.ondigitalocean.app/sample1",
    help="The URL of the web application to test.",
)
@click.option(
    "--delay",
    default=0.5,
    help="The time delay (in seconds) between actions on the web application.",
)
@click.option(
    "--interactions",
    default=5,
    help="The number of interactions to perform on the web application.",
)
@click.option(
    "--load-wait-time",
    default=10,
    help="The maximum time to wait (in seconds) for the page to load.",
)
@click.option(
    "--test-type",
    type=click.Choice(["monkey", "gpt4"], case_sensitive=False),
    default="gpt4",
    help="The type of testing to perform.",
)
def main(url, delay, interactions, load_wait_time, test_type):
    # Check if the given URL is a local file path
    if os.path.isfile(url):
        # If it is a local file, convert the file path to a proper URL
        url = Path(url).as_uri()
    elif not urllib.parse.urlsplit(url).scheme:
        # If it's a relative file path, convert it to an absolute path first, then to a proper URL
        url = Path(os.path.abspath(url)).as_uri()

    print(f"Starting the test on URL: {url}")

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
    print("Web page loaded successfully.")

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
        else:
            # Create list of clickable elements using IDs
            clickable_elements_data = [button.get_attribute("id") for button in buttons]

            # Create the prompt for the GPT model with task description
            prompt = (
                f"Given a basic web calculator, you are tasked with testing its functionality. "
                f"The calculator only supports unary and binary operations (up to two numbers and one operation at a time). "
                f"Here is the filtered HTML source code of the page: '{filtered_html}'. "
                f"Here are the available buttons: {clickable_elements_data}. "
                f"Here are the ordered past actions that you have done for this test (first element was the first action of the test and the last element was the previous action): {past_actions}. "
                f"Please specify the id of the button to click on next, enclosed in brackets like this: [button3] (for a button with the id button3). "
                f"Please also provide a brief explanation or reasoning for your choice in each step, and remember, the goal is to test as many different features as possible to find potential bugs and make sure to include edge cases."
            )

            # Ask the GPT model for the next action
            response = openai.ChatCompletion.create(
                model="gpt-4", messages=[{"role": "user", "content": prompt}]
            )

            action_string = response["choices"][0]["message"]["content"]
            print(action_string)
            match = re.search(r"\[(.*?)\]", action_string)

            if match:
                action_id = match.group(1)
                for button in buttons:
                    if button.get_attribute("id") == action_id:
                        element = button
                        break
                if not element:
                    raise Exception(f"No button found with id: {action_id}")
            else:
                raise Exception(
                    f"Did not find a valid action index in the response from GPT-4: {action_string}"
                )

        element.click()

        # Check for alert and accept it if present
        try:
            alert = browser.switch_to.alert
            print(f"Alert found with message: {alert.text}. Accepting it.")
            alert.accept()
        except Exception as e:
            pass  # no alert, so pass

        # Record the observation after the action
        current_observation = display_element.get_attribute("value")
        current_action = element.get_attribute("id")

        print(
            f"Action {i+1}: {test_type.capitalize()} tester clicking button with id: '{current_action}'. Current observation: {current_observation}"
        )

        # Record action
        past_actions.append(
            {
                "step": (i + 1),
                "action": current_action,
                "observation": current_observation,
            }
        )

        time.sleep(delay)  # Wait a bit between actions for the page to update

    # Close the driver
    print("Closing the browser.")
    browser.quit()

    print(f"Past actions: {json.dumps(past_actions, indent=4)}")


if __name__ == "__main__":
    main()
