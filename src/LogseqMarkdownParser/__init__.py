import json
from pathlib import Path
import fire

try:
    from . import classes
except:
    import classes

def parse_file(
        file_path,
        verbose=False,
        as_json=False,
        ):
    """
    Parameters:
    -----------
    file_path: path to .md file
    verbose: default to False
    as_json: default to False. If True will output a json string meant to be piped to jq.
    """
    assert Path(file_path).exists(), f"{file_path} not found"

    content = Path(file_path).read_text()
    parsed_text = classes.MdText(
            content=content,
            verbose=verbose,
            )
    if as_json:
        return json.dumps(parsed_text.as_json(), indent=4, ensure_ascii=False)
    else:
        return parsed_text

def cli():
    return fire.Fire(parse_file)

if __name__ == "__main__":
    done = fire.Fire(parse_file)
