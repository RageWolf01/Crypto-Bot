"""Allow ``python -m crypto_advisor``."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
