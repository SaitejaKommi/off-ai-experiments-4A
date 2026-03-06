"""Allow `python -m off_ai` execution."""
from .cli import main
import sys

sys.exit(main())
