import re
from pathlib import Path
import fire

try:
    from . import classes
except:
    import classes

def parse_file(
        file_path,
        verbose=False,
        ):
    """
    Parameters:
    -----------
    file_path
    verbose
    """
    assert Path(file_path).exists(), f"{file_path} not found"

    content = Path(file_path).read_text()
    parsed_text = classes.MdText(
            content=content,
            verbose=verbose,
            )
    return parsed_text

def cli():
    return fire.Fire(parse_file)

if __name__ == "__main__":
    done = fire.Fire(parse_file)

    # for testing only
    #done.save_as("./output_text.md", overwrite=False)
