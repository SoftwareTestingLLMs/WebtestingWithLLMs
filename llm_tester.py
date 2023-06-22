import click
import os.path
import time
import openai
from pathlib import Path
import urllib.parse
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


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
    default=100,
    help="The number of interactions to perform on the web application.",
)
@click.option(
    "--load-wait-time",
    default=10,
    help="The maximum time to wait (in seconds) for the page to load.",
)
def main(url, delay, interactions, load_wait_time):
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

    # Start interacting with the page
    for i in range(interactions):
        # Create the prompt for the GPT model with task description
        prompt = (
            f"Your task is to test a web application using Python and Selenium. "
            f"Here is the HTML source code of the page: '{browser.page_source}'. "
            f"Please generate the next action to interact with this web page. "
            f"Try to cover as many different features and edge cases as possible."
        )

        # Ask the GPT model for the next action
        response = openai.ChatCompletion.create(
            model="gpt-4", messages=[{"role": "user", "content": prompt}]
        )

        action = response["choices"][0]["message"]["content"]
        exec(action)  # Execute the action

        # Check for alert and accept it if present
        try:
            alert = browser.switch_to.alert
            print(f"Alert found with message: {alert.text}. Accepting it.")
            alert.accept()
        except Exception as e:
            pass  # no alert, so pass

        time.sleep(delay)  # Wait a bit between actions for the page to update

    # Close the driver
    print("Closing the browser.")
    browser.quit()


if __name__ == "__main__":
    main()
