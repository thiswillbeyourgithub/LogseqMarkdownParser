# LogseqMarkdownParser
a simple python script to load a markdown file and easily access the properties of each block etc.

# Why?
* I wanted a script that reads a logseq page, extracts every "DONE" tasks and append it to another file. So I made this little parser. The resulting script can be found in `examples/done_mover.py`. If you need anything just create an issue.

## Features
* access block properties as a dictionary
* get the parent uuid of each block as well as its position in the hierarchy (i.e. which header is above)
* get the indentation of each block
* easily save to a path

## Usage
* Install
    python -m pip install LogseqMarkdownParser
* load file
    parsed_text = LogseqMarkdownParser.parse_file(file_content).parse_text(verbose=True)
* get information about a block
    print(parsed_text.parsed_blocks[0])
    print(parsed_text.parsed_blocks[0].block_properties)
* add a property to a block (a del_logseq_property method also exists)
    parsed_text.parsed_blocks[0].add_logseq_property(key, value)
* save to path
    parsed_text.save_as(other_file_path)

