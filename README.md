# LogseqMarkdownParser
a simple python script to load a markdown file and easily access the properties of each block etc. You can also parse it as json, handy when using [jq](https://github.com/jqlang/jq).

# Notes to reader
* **Why make this?** I wanted a script that reads a logseq page, extracts every "DONE" tasks and append it to another file. So I made this little parser. The resulting script can be found in `examples/done_mover.py`. If you need anything just create an issue.
* **How stable is it?** Probably not very, I use it for specific things so things might go south. Please open an issue if you found a bug.
* note that the github version might be more up to date than the PyPI version
* **Does it take into account the logbook (i.e. what's added to the block when clicking on 'DOING')?** I didn't think about that initially. I think it should be parsed as normal block content and not as a property.

## Features
* Implements classes `LogseqPage` and `LogseqBlock`
* access block properties as a dictionary
* easily save to a path
* parse as json: `LogseqMarkdownParser some_file.md --as_json |jq`
* supports stdin: `cat some_file.md | LogseqMarkdownParser --as_json | jq`
* shell completion: `eval "$(LogseqMarkdownParser -- --completion)"` or `eval "$(cat completion.bash)"`

## Usage
* Install with `python -m pip install LogseqMarkdownParser`
* load file with `parsed = LogseqMarkdownParser.parse_file(file_content, verbose=True)`
* get the first block with `parsed.blocks[0]`
* get its properties with `parsed.blocks[0].properties`
* add a property to a block with `parsed.blocks[0].set_property(key, value)`
* save to path with `parsed.export_to("some/path.md")`
