import fire
import LogseqMarkdownParser
import re
from pathlib import Path

def main(
    input: str,
    output: str,
    regex_pattern: str = "- #+ to sort",
    order: str = "after",
    sep: str = "- ---",
    verbose_parsing: bool = False,
    ) -> None:
    """
    Move blocks from one file to another.

    Params:
    - input: Path to the input file.
    - output: Path to the output file.
    - regex_pattern: Regular expression to match the target header.
    - order: Determines the order of the new blocks relative to the target header ('before' or 'after').
    - sep: Separator string to use between old and new blocks.
    - verbose_parsing: If True, print additional parsing information.

    Usage example:

    `python move_blocks.py --input my_file.md --output my_other_file.md --regex_pattern "- #+ my target header" --order "after"` --sep "- ---"
        This will:
        * Take all the logseq blocks from the file "my_file.md"
        * Move those blocks to the file "my_other_file.md"
        * The location of the new blocks will be as children of the line "## my target header"
        * Order being "after", those new blocks will appear after any children of the target header, otherwise they will appear first.
        * The new blocks will be separated from the old one by a block with content '- ---'

    """
    assert order in ["before", "after"], "order must be either before or after"
    # parsing files
    try:
        parsed_input = LogseqMarkdownParser.parse_file(
            input,
            verbose=verbose_parsing,
        )
        assert parsed_input.blocks, "no blocks found in input"
    except Exception as err:
        raise Exception(f"Failed parsing {input}: '{err}'")
    try:
        parsed_output = LogseqMarkdownParser.parse_file(
            output,
            verbose=verbose_parsing,
        )
        assert parsed_output.blocks, "no bocks found in output"
    except Exception as err:
        raise Exception(f"Failed parsing {output}: '{err}'")

    # checking pattern line exists
    pattern = re.compile(regex_pattern)
    assert sum(
        bool(pattern.match(b.content))
        for b in parsed_output.blocks
    ) == 1, f"found no or multiple line for pattern '{regex_pattern}'"

    # find index of the pattern line
    good_location = None
    level = None
    skip_sep = True  # don't add separator if no other children blocks (only works if order=='after')
    for ib, ob in enumerate(parsed_output.blocks):
        if pattern.match(ob.content):
            assert good_location is None and level is None
            good_location = ib + 1
            level = ob.indentation_level
            if order == "before":
                break
            elif order == "after":
                continue
            else:
                raise ValueError(order)
        elif good_location and ob.indentation_level <= level:
            assert order == "after"
            skip_sep = False
            good_location = ib
            break
    assert good_location is not None and level is not None

    if order == "before":
        # add separator block before adding the new blocks
        sep_block = LogseqMarkdownParser.LogseqBlock(content=sep, verbose=verbose_parsing)
        sep_block.indentation_level = level + 4
        parsed_output.blocks.insert(good_location, sep_block)

    # moving the blocks
    while parsed_input.blocks:
        parsed_output.blocks.insert(good_location, parsed_input.blocks.pop(-1))

        # don't forget to indent the new blocks
        parsed_output.blocks[good_location].indentation_level += level + 4

    if order == "after" and not skip_sep:
        # add separator block after adding the new blocks
        sep_block = LogseqMarkdownParser.LogseqBlock(content=sep, verbose=verbose_parsing)
        sep_block.indentation_level = level + 4
        parsed_output.blocks.insert(good_location, sep_block)

    assert parsed_output.content, "something went wrong"

    # exporting to temporary files
    parsed_input.export_to(input + ".temp", overwrite=True, allow_empty=True)
    assert Path(input + ".temp")
    parsed_output.export_to(output + ".temp", overwrite=True)
    assert Path(output + ".temp")

    # moving temporary files as permanent
    Path(input).unlink(missing_ok=False)
    Path(input + ".temp").rename(input)
    Path(output).unlink(missing_ok=False)
    Path(output + ".temp").rename(output)


if __name__ == "__main__":
    fire.Fire(main)
