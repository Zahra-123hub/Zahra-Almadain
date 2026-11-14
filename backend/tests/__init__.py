import os

# The tests run on the clock of the computer, so "today" in a test is the same day for the server (see app/timeutil.py).
os.environ.setdefault("APP_TIMEZONE", "LOCAL")
