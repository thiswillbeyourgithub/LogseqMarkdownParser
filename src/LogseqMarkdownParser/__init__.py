import sys
from pathlib import Path, PosixPath
import fire
from typing import Optional, Union, List

from .classes import LogseqPage, LogseqBlock

__VERSION__ = LogseqPage.__VERSION__


def parse_file(
    file_path: Union[str, PosixPath] = None,
    verbose: bool = False,
    out_format: Optional[str] = None,
) -> Union[List[dict], str, LogseqPage]:
    """
    Parameters:
    -----------

    file_path: path to .md file

    verbose: bool, default to False

    out_format: default to None
        Either 'json' or 'toml'. For example can be piped directly to jq
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

    if out_format:
        return parsed.export(format=out_format)
    else:
        return parsed


def cli() -> None:
    fire.Fire(parse_file)


if __name__ == "__main__":
    fire.Fire(parse_file)
