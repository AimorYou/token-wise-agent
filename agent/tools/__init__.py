# Import all custom tools here so they self-register via register_tool().
# Each module calls register_tool() at the bottom upon import.
from agent.tools import bash        # noqa: F401
from agent.tools import grep        # noqa: F401
from agent.tools import smart_read  # noqa: F401
from agent.tools import submit      # noqa: F401
