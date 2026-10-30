#!/usr/bin/env python3
"""Jewellers Digest pricing, in one place.

Every rupee figure the product shows comes from here: the landing page, the
docs, and the AI note's own cost reasoning. Prices quoted in three files
drift, and a page advertising one number while Razorpay charges another is
the kind of mistake that ends in refunds.

RAZORPAY DOES NOT READ THIS FILE. The amount actually charged lives in the
Razorpay plan, which is immutable once created - you cannot edit a plan's
amount, you create a new plan and point RAZORPAY_PLAN_ID at it. So these
constants are the SHOP WINDOW and the plan is the till. They have to be kept
equal by hand, and PLAN_AMOUNT_PAISE exists so a mismatch can be asserted
rather than discovered by a customer.
"""

# What the product costs after the launch offer ends. This is a real,
# intended price, not a decorative number to strike through - if it were
# never going to be charged, quoting it as the regular price would be a
# false reference price and, in India, squarely what the CCPA's guidelines
# on misleading advertisements are about.
REGULAR_INR = 499

# The launch price. Locked for whoever subscribes during the offer: a
# subscription keeps billing its own plan's amount for as long as it lives,
# so early subscribers stay at this figure unless they are migrated.
OFFER_INR = 99

# Paise, as integers. Money never goes in a float.
REGULAR_PAISE = REGULAR_INR * 100
OFFER_PAISE = OFFER_INR * 100

# What the live Razorpay plan must be set to. Assert against this rather
# than trusting that the dashboard matches the website.
PLAN_AMOUNT_PAISE = OFFER_PAISE

DISCOUNT_PCT = round((1 - OFFER_INR / REGULAR_INR) * 100)


def rupees(n):
    """Indian digit grouping: 1,00,000 rather than 100,000."""
    s = f"{int(n):,}"
    if int(n) < 1000:
        return s
    head, tail = divmod(int(n), 1000)
    out = f"{tail:03d}"
    while head > 99:
        head, pair = divmod(head, 100)
        out = f"{pair:02d},{out}"
    return f"{head},{out}"

# Free till Dhanteras: the daily market outlook (not the workbook) is free to
# anyone who signs in with their email, to the end of this day (IST). The JD
# worker enforces it (FREE_UNTIL there); the pages only advertise it, and stop
# on their own after this date. The regular price above applies afterwards.
FREE_UNTIL = "2026-11-06"
FREE_LABEL = "Dhanteras, 6 Nov"


def free_open(today=None):
    from datetime import datetime, timedelta, timezone
    today = today or datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()
    return today <= FREE_UNTIL
