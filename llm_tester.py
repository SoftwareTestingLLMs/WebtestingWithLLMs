import click
import time
import openai
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import string


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
@click.option(
    "--test-type",
    type=click.Choice(["monkey", "gpt4"], case_sensitive=False),
    default="monkey",
    help="The type of testing to perform.",
)
def main(url, delay, interactions, load_wait_time, test_type):
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

    # Find all buttons and input fields
    buttons = browser.find_elements(By.XPATH, "//button")
    inputs = browser.find_elements(By.XPATH, "//input")

    # Create a list for clickable elements
    clickable_elements = buttons + [
        input for input in inputs if not input.get_attribute("readonly")
    ]

    # Start testing
    for i in range(interactions):
        if test_type == "monkey":
            element = random.choice(clickable_elements)
            if element.tag_name == "button":
                element.click()
            elif element.tag_name == "input":
                random_text = "".join(
                    random.choices(string.ascii_letters + string.digits, k=5)
                )
                element.send_keys(random_text)
        else:
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