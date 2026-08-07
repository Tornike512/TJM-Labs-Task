"""Call loop for the TJM Labs sales agent.

Run via the root entry point:
    python main.py                              # known caller (default number)
    python main.py --phone "+1-555-000-9999"    # unknown caller
"""

import argparse
import sys

from . import api
from .agent import Agent

DEFAULT_CALLER_PHONE = "+1-555-123-4567"


def read_caller_line():
    """Read one caller line; echo it when input is piped so transcripts
    captured from a scripted run still show both sides of the dialogue."""
    if sys.stdin.isatty():
        return input("You: ")
    line = input().lstrip("\ufeff")
    print(f"You: {line}")
    return line


def say(lines):
    for line in lines:
        print(f"Agent: {line}")


def main():
    parser = argparse.ArgumentParser(description="TJM Labs pharmacy sales agent")
    parser.add_argument("--phone", default=DEFAULT_CALLER_PHONE,
                        help="caller ID of the pharmacy calling in")
    parser.add_argument("--api-url", default=api.DEFAULT_API_URL,
                        help="pharmacy API endpoint (override to test outages)")
    args = parser.parse_args()

    pharmacies = api.get_pharmacies(args.api_url)
    if not pharmacies:
        print("(pharmacy API unreachable - continuing without caller data)")
    caller = api.find_by_phone(pharmacies, args.phone)

    print(f"--- Incoming call from {args.phone} ---")
    agent = Agent(caller)
    say(agent.start())

    while not agent.done:
        try:
            text = read_caller_line()
        except (EOFError, KeyboardInterrupt):
            print()
            text = "bye"
        say(agent.handle(text))

    print("--- Call ended ---")


if __name__ == "__main__":
    main()
