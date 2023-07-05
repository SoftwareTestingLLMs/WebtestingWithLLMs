from setuptools import setup, find_packages

setup(
    name="llm-ui-tester",
    version="0.1",
    packages=find_packages(),
    install_requires=["selenium", "beautifulsoup4", "openai", "click"],
)
