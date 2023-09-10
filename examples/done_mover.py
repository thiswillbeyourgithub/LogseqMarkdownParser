import LogseqMarkdownParser
from pathlib import Path
import fire


def main(
        TODO_path,
        DONE_path,
        verbose=False,
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
    todos = LogseqMarkdownParser.parse_file(TODO_path, verbose)
    orig_todos = Path(TODO_path).read_text().replace("\t", " " * 4)

    if Path(DONE_path).exists():
        dones = LogseqMarkdownParser.parse_file(DONE_path, verbose).blocks
        orig_dones = Path(DONE_path).read_text().replace("\t", " " * 4)
    else:
        dones = []
        orig_dones = ""

    for i, block in enumerate(todos.blocks):
        if block is None:
            continue  # already added
        if block.TODO_state == "DONE":
            dones.append(block)
            todos.blocks[i] = None
            for ii in range(i+1, len(todos.blocks)):
                child = todos.blocks[ii]
                if child.indentation_level <= dones[-1].indentation_level:
                    # not a child, stop adding those blocks
                    break
                else:
                    # is a child, also add those blocks
                    dones.append(todos.blocks[ii])
                    todos.blocks[ii] = None
        else:
            assert "- DONE " not in str(block), f"{block}"

    todos.blocks = [b for b in todos.blocks if b is not None]
    assert not [b for b in dones if b is None], "dones contained Done"
    dones = LogseqMarkdownParser.classes.MdText(
            content="\n".join([str(b) for b in dones]),
            verbose=verbose)

    temp_file = Path("./cache")
    todos.export_to(temp_file, overwrite=True)
    temp_todos = temp_file.read_text().replace("\t", " " * 4)
    dones.export_to(temp_file, overwrite=True)
    temp_dones = temp_file.read_text().replace("\t", " " * 4)
    temp_file.unlink()

    diff_todos = len(orig_todos.split("\n")) - len(temp_todos.split("\n"))
    print(f"Line difference in todos: {diff_todos}")
    diff_dones = len(orig_dones.split("\n")) - len(temp_dones.split("\n"))
    print(f"Line difference in dones: {diff_dones}")
    if -diff_todos != diff_dones:
        breakpoint()
        import difflib
        print("\n".join(list(difflib.unified_diff(orig_todos.split("\n"), temp_todos.split("\n")))))
        breakpoint()
        print("\n".join(list(difflib.unified_diff(orig_dones.split("\n"), temp_dones.split("\n")))))
        raise Exception

    todos.export_to(TODO_path, overwrite=True)
    dones.export_to(DONE_path, overwrite=True)


if __name__ == "__main__":
    fire.Fire(main)
