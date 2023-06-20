import click
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import random
import string
import time


@click.command()
@click.option(
    "--url",
    default="https://sea-lion-app-q6nwz.ondigitalocean.app/sample1",
    help="The URL of the web application to test.",
)
def main(url):
    # Open the web browser and navigate to the app's URL
    browser = webdriver.Chrome()
    browser.get(url)

    # Wait for the elements to load
    WebDriverWait(browser, 10).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )

    # Find all buttons and input fields
    buttons = browser.find_elements(By.XPATH, "//button")
    inputs = browser.find_elements(By.XPATH, "//input")

    # Create a list of all interactable elements
    elements = buttons + inputs

    # Start monkey testing
    for _ in range(100):  # Let's interact with elements 100 times
        element = random.choice(elements)  # Choose a random element

        if element.tag_name == "button":
            element.click()  # If it's a button, click it
        elif element.tag_name == "input":
            # If it's an input field, enter some random text
            element.send_keys(
                "".join(random.choices(string.ascii_letters + string.digits, k=5))
            )

        time.sleep(1)  # Wait a bit between actions for the page to update

    # Close the driver
    browser.quit()


if __name__ == "__main__":
    main()
