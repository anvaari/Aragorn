"""One-off maintenance jobs. Run from the REPO ROOT: `python app/cli.py <command>`.

Same sys.path trick as `fastapi run app/main.py`: the script's directory (app/)
lands on sys.path, so the absolute imports rooted at app/ work and .env is read
from the current (root) directory.
"""
import typer

app = typer.Typer(help="Aragorn maintenance jobs", no_args_is_help=True,
                  add_completion=False, pretty_exceptions_show_locals=False)


@app.command("backfill-summaries")
def backfill_summaries(batch_size: int = typer.Option(
        50, "--batch-size", help="Artists per refresh pass.")):
    """Regenerate LLM summaries for EVERY artist whose event set changed."""
    from services.artist_service import refresh_artist_summaries

    total_updated = 0
    while True:
        result = refresh_artist_summaries(batch_size=batch_size)
        total_updated += result["updated"]
        typer.echo(f"stale={result['stale']} updated={result['updated']} "
                   f"(total updated={total_updated})")
        if result["stale"] == 0:
            break
    typer.echo(f"Done: {total_updated} summaries refreshed.")


@app.command("normalize-artists")
def normalize_artists(
    limit: int = typer.Option(100, "--limit", help="Max artists to process."),
    apply: bool = typer.Option(
        False, "--apply",
        help="Write names directly WITHOUT the Telegram review step."),
):
    """Propose Persian->English artist names for admin review in Telegram.

    Default flow: create pending proposals and DM the admin (bot_admin_chat_id)
    with a review entry-point. --apply skips the review (manual run = consent).
    """
    from services.normalization_service import (apply_normalizations_directly,
                                                notify_admin_proposals,
                                                propose_normalizations)

    if apply:
        result = apply_normalizations_directly(limit=limit)
        typer.echo(f"Applied {result['applied']} of {result['candidates']} "
                   f"candidates ({result['skipped']} junk skipped).")
        return
    result = propose_normalizations(limit=limit)
    typer.echo(f"Created {result['proposed']} proposals from {result['candidates']} "
               f"candidates ({result['skipped']} junk skipped).")
    if result["proposed"] and notify_admin_proposals(result["proposed"]):
        typer.echo("Admin notified in Telegram — review there to apply.")


@app.command("proposals")
def proposals(
    status: str = typer.Option("pending", "--status",
                               help="pending | approved | rejected | all"),
    limit: int = typer.Option(20, "--limit", help="Rows to list."),
):
    """List artist name proposals."""
    from db import crud_proposals

    status = None if status == "all" else status
    rows = crud_proposals.list_proposals(status=status, limit=limit)
    if not rows:
        typer.echo("No proposals found.")
        return
    for row in rows:
        typer.echo(f"#{row['id']} [{row['status']}] artist={row['artist_id']} "
                   f"{row['current_name']} -> {row['proposed_name']}")


if __name__ == "__main__":
    app()
