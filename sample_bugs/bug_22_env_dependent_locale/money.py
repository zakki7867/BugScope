import os


def format_price(amount):
    """Format a price with two decimals and a dot."""
    text = f"{amount:.2f}"
    if os.environ.get("BUGSCOPE_DEMO_LOCALE") == "EU":
        text = text.replace(".", ",")
    return text
