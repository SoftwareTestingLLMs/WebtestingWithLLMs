import click
from llm_tester.ui_tester import run_ui_test


@click.command()
@click.option(
    "--url",
    default="https://sea-lion-app-q6nwz.ondigitalocean.app/calculator",
    help="The URL of the web application to test.",
)
@click.option(
    "--delay",
    default=0.5,
    help="The time delay (in seconds) between actions on the web application.",
)
@click.option(
    "--interactions",
    default=30,
    help="The number of interactions to perform on the web application.",
)
@click.option(
    "--load-wait-time",
    default=10,
    help="The maximum time to wait (in seconds) for the page to load.",
)
@click.option(
    "--test-type",
    type=click.Choice(["monkey", "gpt-4", "gpt-3.5-turbo", "gpt-4-turbo-preview"], case_sensitive=False),
    default="monkey",
    help="The type of testing to perform.",
)
@click.option(
    "--output-dir",
    default="results",
    help="The directory where the output files will be stored.",
)
@click.option(
    "-y", "--yes",
    is_flag=True,
    default=False,
    help="Automatically answer yes to all prompts.",
)
def main(url, delay, interactions, load_wait_time, test_type, output_dir, yes):
    if test_type == "gpt-4" and not yes:
        while True:
            print("GPT-4 is discouraged, since it is expensive. Would you like to use the cheaper GPT-4 turbo preview instead? (Y/n)")
            answer = input().lower()
            if answer == "y" or answer == "":
                test_type = "gpt-4-turbo-preview"
                break
            elif answer == "n":
                break
    run_ui_test(url, delay, interactions, load_wait_time, test_type, output_dir)


if __name__ == "__main__":
    main()
