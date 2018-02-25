#!/usr/bin/env python3
import json
import sys

import jabbercat.emoji


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--emoji-java",
        action="append",
        default=[],
        help="Path to an emoji-java-like database to merge"
    )
    parser.add_argument(
        "--gemoji",
        action="append",
        default=[],
        help="Path to an gemoji-like database to merge"
    )
    parser.add_argument(
        "outfile",
        nargs="?",
        default=None,
        help="Output file (defaults to stdout)"
    )

    args = parser.parse_args()

    db = jabbercat.emoji.EmojiDatabase()

    for src in args.gemoji:
        with open(src, "r") as f:
            db.merge_gemoji(json.load(f))

    for src in args.emoji_java:
        with open(src, "r") as f:
            db.merge_emoji_java(json.load(f))

    if args.outfile is not None:
        args.outfile = open(args.outfile, "w")
    else:
        args.outfile = sys.stdout

    with args.outfile:
        json.dump(db.save(), args.outfile)
