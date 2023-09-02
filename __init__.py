import re
from pathlib import Path
import fire

from classes import ParsedText, ParsedBlock

def parse_file(
        file_path,
        verbose=False,
        ):
    """
    Usage:
    # load file
    parsed_text = parse_file(file_path)

    # get information about a block
    print(parsed_text.parsed_blocks[0])
    print(parsed_text.parsed_blocks[0].block_properties)

    # save to path
    parsed_text.save_as(other_file_path)

    Parameters:
    -----------
    file_path
    verbose
    """
    assert Path(file_path).exists(), f"{file_path} not found"

    content = Path(file_path).read_text()
    parsed_text = ParsedText(content).parse_text(
            content=content,
            verbose=verbose,
            )
    return parsed_text

if __name__ == "__main__":
    done = fire.Fire(parse_file)

    # for testing only
    #done.save_as("./output_text.md", overwrite=False)
