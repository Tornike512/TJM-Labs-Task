"""Mock action tools. In production these would hit an email service / CRM;
here they just print a clearly visible marker line."""


def send_follow_up_email(pharmacy, topic):
    """Queue a follow-up email to the pharmacy about `topic`."""
    print(f"[TOOL CALLED] Email queued to {pharmacy} re: {topic}")


def schedule_callback(pharmacy, time):
    """Book a specialist callback with the pharmacy at `time`."""
    print(f"[TOOL CALLED] Callback scheduled with {pharmacy} for {time}")
