"""Command-line interface for the file processor."""

import argparse
from typing import Dict

from .processor import process_file
from .file_utils import list_supported_files


def build_parser() -> argparse.ArgumentParser:
    """Create and return the argument parser."""
    parser = argparse.ArgumentParser(description="Process text files.")
    parser.add_argument("input", help="Path to input file or directory")
    # TODO: add --batch flag for directory processing
    return parser


def run(args: argparse.Namespace) -> str | Dict[str, str]:
    """Execute processing based on parsed CLI arguments.

    Returns
    -------
    str or dict
        Single processed string in normal mode, or a dict of
        ``{filename: processed}`` pairs in batch mode.
    """
    # TODO: handle batch mode
    return process_file(args.input)


def main(argv: list[str] | None = None) -> str | Dict[str, str]:
    """Entry point: parse args and run."""
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)
