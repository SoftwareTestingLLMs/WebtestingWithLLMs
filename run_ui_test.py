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
    type=click.Choice(["monkey", "gpt-4", "gpt-3.5-turbo"], case_sensitive=False),
    default="monkey",
    help="The type of testing to perform.",
)
@click.option(
    "--output-dir",
    default="results",
    help="The directory where the output files will be stored.",
)
def main(url, delay, interactions, load_wait_time, test_type, output_dir):
    run_ui_test(url, delay, interactions, load_wait_time, test_type, output_dir)


if __name__ == "__main__":
    main()
