import fire
import sys
saved_path = sys.path
sys.path.insert(0, "../src")
sys.path.insert(0, "../src/LogseqMarkdownParser")
import LogseqMarkdownParser
sys.path = saved_path

def parse_file(
    path: str,
    ):
    """
    Parse a markdown file using LogseqMarkdownParser.

    Args:
        path (str): The path to the markdown file to be parsed.

    Returns:
        None
    """
    parsed = LogseqMarkdownParser.parse_file(
        path,
        verbose=True)
    import code ; code.interact(local=locals())

if __name__ == "__main__":
    fire.Fire(parse_file)
