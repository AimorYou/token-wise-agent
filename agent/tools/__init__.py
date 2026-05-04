# Import all custom tools here so they self-register via register_tool().
# Each module calls register_tool() at the bottom upon import.
from agent.tools import (
    bash,  # noqa: F401
    bash_session,  # noqa: F401
    glob,  # noqa: F401
    grep,  # noqa: F401
    smart_editor,  # noqa: F401
    smart_reader,  # noqa: F401
    submit,  # noqa: F401
)
