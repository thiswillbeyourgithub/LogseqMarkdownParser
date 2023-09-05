# LogseqMarkdownParser
a simple python script to load a markdown file and easily access the properties of each block etc.

# Notes to reader
* **Why make this?** I wanted a script that reads a logseq page, extracts every "DONE" tasks and append it to another file. So I made this little parser. The resulting script can be found in `examples/done_mover.py`. If you need anything just create an issue.
* **How stable is it?** Probably not very, I use it for specific things so things might go south. Please open an issue if you found a bug.
* note that the github version might be more up to date than the PyPI version

## Features
* access block properties as a dictionary
* easily save to a path

## Usage
* Install with `python -m pip install LogseqMarkdownParser`
* load file with `parsed = LogseqMarkdownParser.parse_file(file_content, verbose=True)`
* get the first block with `parsed.blocks[0]`
* get its properties with `parsed.blocks[0].get_properties()`
* add a property to a block with `parsed.blocks[0].set_property(key, value)`
* save to path with `parsed.export_to("some/path.md")`

