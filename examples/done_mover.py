import LogseqMarkdownParser
from pathlib import Path
import fire


def main(
        TODO_path,
        DONE_path,
        *args,
        **kwargs,
        ):
    """
    simple script that outputs the TODO blocks found in a logseq page
    into another page.

    TODO_path:
        path to the file that must contain only TODOs
    DONE_path:
        path to the file that must contain only DONEs
    """
    assert not args and not kwargs, "extra arguments detected"

    assert Path(TODO_path).exists, "TODO_path does not exist"
    todos = LogseqMarkdownParser.parse_file(TODO_path)
    n_todo = len(Path(TODO_path).read_text().split("\n"))

    if Path(DONE_path).exists():
        dones = LogseqMarkdownParser.parse_file(DONE_path)
        n_done = len(Path(DONE_path).read_text().split("\n"))
    else:
        dones = LogseqMarkdownParser.classes.ParsedText("").parse_text()
        n_done = 0

    latest_indent = 0
    adding_mode = False
    for i, block in enumerate(todos.parsed_blocks):
        if not adding_mode:
            if block.block_TODO_state == "DONE":
                dones.parsed_blocks.append(block)
                todos.parsed_blocks[i] = None

                adding_mode = True
                latest_indent = block.block_indentation_level
        else:
            if block.block_indentation_level > latest_indent:
                dones.parsed_blocks.append(block)
                todos.parsed_blocks[i] = None
            else:
                latest_indent = block.block_indentation_level
                adding_mode = False

    todos.parsed_blocks = [b for b in todos.parsed_blocks if b is not None]

    todos.save_as(TODO_path, overwrite=True)
    dones.save_as(DONE_path, overwrite=True)

    n_todo2 = len(Path(TODO_path).read_text().split("\n"))
    n_done2 = len(Path(DONE_path).read_text().split("\n"))
    diff = n_todo + n_done - n_todo2 - n_done2
    if diff not in [0, -1]:
        raise Exception(
                "Number of lines of output documents is not the "
                f"sum of number of lines of input documents. Diff={diff}")


if __name__ == "__main__":
    fire.Fire(main)
