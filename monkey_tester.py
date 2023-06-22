import click
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import string
import time
from pathlib import Path
import os.path
import urllib.parse


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
    # Check if the given URL is a local file path
    if os.path.isfile(url):
        # If it is a local file, convert the file path to a proper URL
        url = Path(url).as_uri()
    elif not urllib.parse.urlsplit(url).scheme:
        # If it's a relative file path, convert it to an absolute path first, then to a proper URL
        url = Path(os.path.abspath(url)).as_uri()

    print(f"Starting the test on URL: {url}")

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

    # Create two lists: one for clickable elements and one for readonly inputs
    clickable_elements = buttons + [
        input for input in inputs if not input.get_attribute("readonly")
    ]
    readonly_inputs = [input for input in inputs if input.get_attribute("readonly")]

    print(
        f"Found {len(clickable_elements)} clickable elements and {len(readonly_inputs)} readonly inputs."
    )

    # Start monkey testing
    for i in range(
        interactions
    ):  # Let's interact with elements as per interactions count
        element = random.choice(clickable_elements)  # Choose a random clickable element

        if element.tag_name == "button":
            print(
                f"Action {i+1}: Clicking button with outerHTML: '{element.get_attribute('outerHTML')}'."
            )
            element.click()  # If it's a button, click it
        elif element.tag_name == "input":
            # If it's an editable input field, enter some random text
            random_text = "".join(
                random.choices(string.ascii_letters + string.digits, k=5)
            )
            print(
                f"Action {i+1}: Entering text into input field with outerHTML: '{element.get_attribute('outerHTML')}', text: '{random_text}'."
            )
            element.send_keys(random_text)

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
