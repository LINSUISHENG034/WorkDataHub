"""
Allow running the module directly with: python -m scripts.migrations.mysql_dump_migrator
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
