# LogseqMarkdownParser
a simple python script to load a markdown file and easily access the properties of each block etc.

# Why?
* I wanted a script that reads a logseq page, extracts every "DONE" tasks and append it to another file. So I made this little parser. If you need anything just create an issue.

## Features
* access block properties as a dictionary
* get the parent uuid of each block as well as its position in the hierarchy (i.e. which header is above)
* get the indentation of each block
* easily save to a path

## Usage
* load file
    parsed_text = parse_file(file_path)
* get information about a block
    print(parsed_text.parsed_blocks[0])
    print(parsed_text.parsed_blocks[0].block_properties)
* save to path
    parsed_text.save_as(other_file_path)

