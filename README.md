# LogseqMarkdownParser
a simple python script to load a markdown file and easily access the properties of each block etc. You can also parse it as json, handy when using [jq](https://github.com/jqlang/jq). toml output is also supported. You can use it as a cli tol or as a python library.

# Notes to reader
* **Why make this?** I wanted a script that reads a Logseq page, extracts every "DONE" tasks and append it to another file. So I made this little parser. The resulting script can be found in `examples/done_mover.py`. If you need anything just create an issue.
* **How stable is it?** Probably okay, I use it for specific things so things might go south in edge cases. Please open an issue if you found a bug.
* Note that the github version might be more up to date than the PyPI version
* **Does it take into account the logbook (i.e. what's added to the block when clicking on 'DOING')?** I didn't think about that initially. I think it should be parsed as normal block content and not as a property.
* **What's the deal with properties?** page.page_properties is a python dict, you can edit it freely as it's only appended to the top of the page when exporting. But page.blocks[0].properties is an ImmutableDict because the properties are stored inside the text content using Logseq format. To edit a block property, use the `del_property` and `set_property` method.

## Features
* Implements classes `LogseqPage` and `LogseqBlock`
* read pages, page properties, block and block properties as a regular python dictionary
* easily save to a path as a Logseq-ready markdown file with `page.export_to`
* Static typing with [beartype](https://beartype.readthedocs.io/) if you have it installed (otherwise no typechecking).
* parse for the cli as json: `LogseqMarkdownParser some_file.md --out_format='json' |jq`
* parse for the cli as toml: `LogseqMarkdownParser some_file.md --out_format='toml' > output.toml`
* supports stdin: `cat some_file.md | LogseqMarkdownParser --out_format='json' | jq`
* shell completion: `eval "$(LogseqMarkdownParser -- --completion)"` or `eval "$(cat completion.zsh)"`

## How to
* Install with `python -m pip install LogseqMarkdownParser`
### Usage
``` python
import LogseqMarkdownParser

# loading:
# load file
page = LogseqMarkdownParser.parse_file(file_content, verbose=True)
# load a string
page = LogseqMarkdownParser.parse_text(content=my_string, verbose=True)
# load a string as page manually
page = LogseqMarkdownParser.LogseqPage(content=my_string, verbose=True)

# get page properties
page.page_properties

# access the blocks as a list
page.blocks

# get a block's properties
page.blocks[0].properties
# You can't edit them directly though, only page_properties can be directly edited at this time, see note below

# edit block properties
page.blocks[0].set_property(key, value)
page.blocks[0].del_property(key)

# inspect a page or block as a dict
page.dict()  # this include the page properties, each block and their properties
page.blocks[0].dict()

# Save as Logseq ready md file
page.export_to("some/path.md")

# format as another format
print(page.format('json'))  # also toml
```
