import json
from pathlib import Path
import fire

try:
    from . import classes
except:
    import classes

LogseqPage = classes.LogseqPage
LogseqBlock = classes.LogseqBlock

__VERSION__="2.5"

def parse_file(
    file_path: str,
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
    assert Path(file_path).exists(), f"{file_path} not found"

    content = Path(file_path).read_text()
    parsed_text = classes.LogseqPage(
            content=content,
            verbose=verbose,
            )
    if as_json:
        return json.dumps(parsed_text.as_json(), indent=4, ensure_ascii=False)
    else:
        return parsed_text

def cli() -> None:
    fire.Fire(parse_file)

if __name__ == "__main__":
    fire.Fire(parse_file)
