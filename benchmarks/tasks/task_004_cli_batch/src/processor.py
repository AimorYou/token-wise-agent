"""File processor — transforms the content of a single file."""


def process_file(path: str) -> str:
    """Read *path* and return its processed content.

    For this task the "processing" is trivial: uppercase the content and
    prepend a tag.  In a real application this could be any transformation.

    Returns
    -------
    str
        Processed text.
    """
    with open(path, "r") as fh:
        content = fh.read().strip()
    return f"PROCESSED: {content}"
