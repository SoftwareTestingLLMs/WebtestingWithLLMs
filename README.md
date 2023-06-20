# WebtestingWithLLMs

# ChromeDriver Installation Guide

This guide provides steps to install ChromeDriver, which is a necessary component for running automated tests with Selenium WebDriver on the Google Chrome browser.

## Prerequisites
Ensure that you have the Google Chrome browser installed on your system. You can check your Google Chrome version by typing `google-chrome --version` in the terminal or navigating to `chrome://version` in the Chrome browser.

## Installation

### Windows

1. Visit the [ChromeDriver download page](https://sites.google.com/a/chromium.org/chromedriver/downloads).
2. Download the version that matches your installed Google Chrome version.
3. Unzip the downloaded file to retrieve `chromedriver.exe`.
4. Place `chromedriver.exe` in a directory of your choice and add that directory to your system's PATH environment variable.

### MacOS
1. If you have Homebrew installed, simply run: `brew install chromedriver`.
2. Check if the correct version of ChromeDriver is installed by running `chromedriver --version` in the terminal.

### Ubuntu (and other Debian-based systems)
1. Use the following command to install ChromeDriver: `sudo apt-get install chromium-chromedriver`.
2. Depending on your system's configuration, you may need to add the directory `/usr/lib/chromium-browser/` to the PATH environment variable: `export PATH=$PATH:/usr/lib/chromium-browser/`.
3. Verify the installation by running `chromedriver --version` in the terminal.

Remember to always match your ChromeDriver version with your Google Chrome browser version to avoid compatibility issues. Keep both your browser and ChromeDriver updated to the latest versions for the best results.

For more details, refer to the [official ChromeDriver documentation](https://sites.google.com/a/chromium.org/chromedriver/home).
