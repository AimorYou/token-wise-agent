# Feature + Bug: CLI does not support batch mode

## Description

The CLI tool currently processes one input file at a time.  We want to add a
**batch mode** where the CLI accepts a directory and processes every supported
file in it.

## Expected behavior

`cli.py` should accept a `--batch` flag.  When enabled, the `input` argument
is treated as a **directory** and every file with a supported extension
(`.txt`, `.csv`) inside it should be processed.

Results should be returned as a dict mapping each filename to its processed
output, e.g.:

```python
{
    "a.txt": "PROCESSED: contents of a",
    "b.csv": "PROCESSED: contents of b",
}
```

## Notes

- `processor.py` already has a `process_file(path)` function that works for
  single files.
- `file_utils.py` contains `list_supported_files(directory)` which should
  return only files with supported extensions — but it currently has a bug
  that causes it to return **all** files regardless of extension.
- The CLI parsing in `cli.py` needs a new `--batch` flag and corresponding
  logic.

## Tests currently failing in

`tests/test_cli_batch.py`
