from selenium import webdriver
from selenium.webdriver.common.by import By

browser = webdriver.Chrome()

try:
    browser.get("https://sea-lion-app-q6nwz.ondigitalocean.app/sample1")

    # Test addition
    browser.find_element(By.XPATH, "//button[text()='1']").click()
    browser.find_element(By.XPATH, "//button[text()='+']").click()
    browser.find_element(By.XPATH, "//button[text()='2']").click()
    browser.find_element(By.XPATH, "//button[text()='=']").click()

    display = browser.find_element(By.XPATH, "//*[@id='display']")
    assert display.get_attribute("value") == "3", "Addition test failed"

    # Test subtraction
    browser.find_element(By.XPATH, "//button[text()='C']").click()
    browser.find_element(By.XPATH, "//button[text()='5']").click()
    browser.find_element(By.XPATH, "//button[text()='-']").click()
    browser.find_element(By.XPATH, "//button[text()='3']").click()
    browser.find_element(By.XPATH, "//button[text()='=']").click()

    assert display.get_attribute("value") == "2", "Subtraction test failed"

    # Test alert dismissal (divide by zero)
    browser.find_element(By.XPATH, "//button[text()='C']").click()
    browser.find_element(By.XPATH, "//button[text()='8']").click()
    browser.find_element(By.XPATH, "//button[text()='/']").click()
    browser.find_element(By.XPATH, "//button[text()='0']").click()
    browser.find_element(By.XPATH, "//button[text()='=']").click()

    alert = browser.switch_to.alert
    assert alert.text == "Cannot divide by zero!", "Alert text mismatch"
    alert.dismiss()

    # Test other operations and cases

finally:
    browser.quit()
