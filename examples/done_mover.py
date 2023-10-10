import urllib.request
import time
import difflib
from pathlib import Path
import fire

# import the library from the current repo instead of pypi
import sys
saved_path = sys.path
sys.path.insert(0, "../src")
sys.path.insert(0, "../src/LogseqMarkdownParser")
import LogseqMarkdownParser
sys.path = saved_path

def check_internet_connection():
    try:
        urllib.request.urlopen('http://www.google.com', timeout=1)
        return True
    except urllib.request.URLError:
        return False


def main(
        TODO_path,
        DONE_path,
        verbose=False,
        needs_internet=True,
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
    if needs_internet and not check_internet_connection:
        time.sleep(60)
        while not check_internet_connection():
            print("Waiting for internet connection...")
            time.sleep(60)
        time.sleep(120)  # wait at least 2minutes for any sync to finish

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

    n_moved = 0
    for i, block in enumerate(todos.blocks):
        if block is None:
            continue  # already added
        if block.TODO_state == "DONE":
            parent_indent = block.indentation_level
            dones.append(block)
            todos.blocks[i] = None
            n_moved += 1
            for ii in range(i+1, len(todos.blocks)):
                child = todos.blocks[ii]
                if child.indentation_level <= parent_indent:
                    # not a child, stop adding those blocks
                    break
                else:
                    # is a child, also add those blocks
                    dones.append(todos.blocks[ii])
                    todos.blocks[ii] = None
                    n_moved += 1
        else:
            assert "- DONE " not in str(block), f"{block}"

    todos.blocks = [b for b in todos.blocks if b is not None]
    assert not [b for b in dones if b is None], "dones contained None"
    dones = LogseqMarkdownParser.classes.MdText(
            content="\n".join([str(b) for b in dones]),
            verbose=verbose)

    # export in a temporary file to check the output
    temp_file = Path("./cache")
    todos.export_to(temp_file, overwrite=True)
    temp_todos = temp_file.read_text().replace("\t", " " * 4)
    dones.export_to(temp_file, overwrite=True)
    temp_dones = temp_file.read_text().replace("\t", " " * 4)
    temp_file.unlink()

    # manually check that each line that is removed from todo
    # ends up in the done file
    diff_todo = [d for d in difflib.ndiff(
            orig_todos.split("\n"),
            temp_todos.split("\n"),
            )]
    diff_done = [d for d in difflib.ndiff(
            orig_dones.split("\n"),
            temp_dones.split("\n"),
            )]

    assert (diff_todo and diff_done) or (not diff_todo and not diff_done), (
        "something went wrong")

    missings = []
    for d in diff_todo:
        if d.startswith("+"):
            if "-" + d[1:] not in diff_done:
                missings.append(d)
        elif d.startswith("-"):
            if "+" + d[1:] not in diff_done:
                missings.append(d)
    if missings:
        print("Missing lines:")
        for m in missings:
            print(m)

    n_todo = len(todos.blocks)
    n_done = len(dones.blocks)
    print(f"Moved {n_moved} blocks.")
    print(f"Number of blocks in TODO: {n_todo}")
    print(f"Number of blocks in DONE: {n_done}")
    todos.export_to(TODO_path, overwrite=True)
    dones.export_to(DONE_path, overwrite=True)

if __name__ == "__main__":
    fire.Fire(main)
