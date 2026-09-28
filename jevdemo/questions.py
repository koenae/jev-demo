"""Question criteria shared by demo 1 and demo 2 (kept apart so they can be shown as-is)."""

from typesafe_sdk import NoulCriteria

TEAMS = {
    "billing": "Invoices, charges, refunds, subscriptions.",
    "technical": "Bugs, errors, integrations, outages, account access.",
    "sales": "Plans, pricing, upgrades, discounts.",
    "other": "No action needed or not a support request.",
}

URGENCY_LEVELS = [
    "No time pressure; can wait a week.",      # score 0
    "Should be handled within a few days.",    # score 1
    "Blocking the customer; needs a same-day response.",  # score 2
]

REFUND = NoulCriteria(
    true="The customer explicitly wants a charge reversed, refunded or credited.",
    false="The customer only reports a problem or asks a question.",
)
