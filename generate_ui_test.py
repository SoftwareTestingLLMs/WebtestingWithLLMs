import click
import os
from selenium import webdriver
import openai
import json
from urllib.parse import urlparse


def generate_directory_path(url, base_dir):
    # Extract the directory name from the URL
    url_parts = urlparse(url)
    directory = url_parts.netloc + url_parts.path

    # Construct the full directory path
    return os.path.join(base_dir, directory.lstrip("/"))


@click.command()
@click.option(
    "--url",
    default="https://sea-lion-app-q6nwz.ondigitalocean.app/sample1",
    help="The URL of the web application to test.",
)
@click.option(
    "--base_dir",
    default="ui_tests",
    help="The base directory where the ui tests should be saved.",
)
def main(url, base_dir):
    # Get OpenAI API key from file
    with open("openai_key.json", "r") as file:
        openai.api_key = json.load(file)["key"]

    # Open the web browser and navigate to the app's URL
    browser = webdriver.Chrome()
    browser.get(url)

    task = (
        f"Your task is to test a web application in detail using python and selenium with the URL {url}. Try to test as many features as possible."
        f'Use "browser = webdriver.Chrome() to open the web browser. Use only xpath commands '
        f'like "browser.find_element(By.XPATH, \'//button[text()="Click me!"]\')" to find elements. If there is '
        f"an alert, the script should switch to the alert and dismiss it before proceeding with the next step. "
        f"Use assertions to test the correct behavior of the application. Only print the code without further "
        f"explanations. This is the web application: {browser.page_source}"
    )

    click.echo(task)

    completion = openai.ChatCompletion.create(
        model="gpt-4", messages=[{"role": "user", "content": task}]
    )

    click.echo(completion)
    response = completion["choices"][0]["message"]["content"]
    

    # Generate the directory path
    directory_path = generate_directory_path(url, base_dir)

    # Save the generated test to file
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)

    with open(os.path.join(directory_path, "test.py"), "w") as file:
        file.write(response)

    # Close the web browser
    browser.quit()


if __name__ == "__main__":
    main()
