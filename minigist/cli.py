import click

@click.group()
def cli():
    """
    A tool that monitors your Miniflux feeds for articles without summaries,
    generates concise summaries using AI, and updates the entries automatically.
    """
    pass

@cli.command()
def run():
    """Run the update procedure."""
    click.echo("Running update...")

if __name__ == "__main__":
    cli()
