import sys
import json
from pathlib import Path
import fire

try:
    from .classes import LogseqPage, LogseqBlock
except:
    from classes import LogseqPage, LogseqBlock

__VERSION__: str = "2.6"

def parse_file(
    file_path: str = None,
    verbose: bool = False,
    as_json: bool = False,
    ):
    """
    Parameters:
    -----------

    file_path: path to .md file

    verbose: bool, default to False

    as_json: default to False.
        If True will output a json string meant to be piped to jq.
    """
    if file_path is not None:
        assert Path(file_path).exists(), f"{file_path} not found"

        content = Path(file_path).read_text()
    else:
        content = sys.stdin.read()

    parsed = LogseqPage(
            content=content,
            verbose=verbose,
            )

    if as_json:
        return json.dumps(
            parsed.as_json(),
            indent=4,
            ensure_ascii=False
        )
    else:
        return parsed

def cli() -> None:
    fire.Fire(parse_file)

if __name__ == "__main__":
    fire.Fire(parse_file)
