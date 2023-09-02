from pathlib import Path
import uuid
import re

INDENT_REGEX = re.compile(r"^\s*")

def count_indentation(content):
    """count the leading spaces to know the indentation level"""
    return len(re.search(INDENT_REGEX, content.replace("\t", "    ")).group(0))

class ParsedBlock(str):
    def parse(
            self,
            block_properties,
            block_hierarchy,
            block_uuid,
            indentation_level,
            parent_block,
            TODO_state,
            ):
        """
        Used in class ParsedText to parse each individual block.

        Subclass of string with the following new attributes:
            block_TODO_state: wether the block is in a TODO/DOING/DONE etc.
                              None otherwise.
            block_properties: dictionnary
            block_uuid: a random uuid. It is not the same as the one used within
                        logseq but is used to keep track of parents.
                        If a uuid is already present in the block properties,
                        it will be used instead.
            block_parent_uuid: uuid of the parent block along with their depth
                               as a dictionnary
            block_indentation_level: in number of spaces, with tab=4
            block_hierarchy: list of each parent header. Empty if not under any title.
        """
        self.block_properties = block_properties
        self.block_hierarchy = block_hierarchy
        self.block_uuid = block_uuid
        self.block_indentation_level = indentation_level
        self.block_parent_uuid = parent_block
        self.block_TODO_state = TODO_state
        return self



class ParsedText(str):
    def parse_text(
            self,
            content,
            verbose=False,
            ):
        assert isinstance(content, str), (
            f"content must be of type string, not '{type(content)}'")

        # detect each block
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if not i:
                continue  # skip the first line
            if not re.match(r"\s*- *", line):
                ii = 0
                while True:
                    ii += 1
                    if lines[i-ii] is not None:
                        lines[i-ii] += "\n" + line
                        lines[i] = None
                        break
                    if i-ii <= 0:
                        raise Exception("Endless loop")
        blocks = [line for line in lines if line is not None]
        if verbose:
            print(f"Number of blocks: {len(blocks)}")

        # detect headers
        headers = re.findall(r"\s*- #+ \w+\n", content)

        self.parsed_blocks = []
        cur_headers = {}  # keep track of latest headers and their depth
        latest_parents = {}
        for index, block in enumerate(blocks):
            assert isinstance(block, str), f"block is not string: '{block}'"
            if verbose:
                print(block)

            # get indentation of the block
            cur_indent = count_indentation(block)
            if verbose:
                print(f"Block indentation: {cur_indent}")

            # keep the parent with less indentated parents
            latest_parents = {k: v for k, v in latest_parents.items() if v < cur_indent}
            if verbose:
                print(f"Block parents: {latest_parents}")

            # discard headers that are not deep enough anymore
            cur_headers = {k: v for k, v in cur_headers.items() if v < cur_indent}
            if verbose:
                print(f"Block headers: {cur_headers}")

            # get properties of each block
            prop = re.search(r"\s*(\w+):: (\w+)", block)
            if not prop:
                block_properties = {}
            else:
                block_properties = {
                        k.strip(): v.strip()
                        for k, v in zip(*prop.groups())
                        }
            if verbose:
                print(f"Block properties: {block_properties}")

            if "id" in block_properties:
                block_uuid = block_properties["id"]
                if verbose:
                    print(f"Random block uuid: {block_uuid}")
            else:
                # random uuid
                block_uuid = str(uuid.uuid4())
                if verbose:
                    print(f"Reusing block uuid: {block_uuid}")

            # get the TODO state
            TODO_state = None
            for keyword in ["TODO", "DOING", "DONE"]:
                assert not TODO_state, (
                    f"block fits multiple TODO states: '{block}'")
                if re.match(f"- {keyword} ", block):
                    TODO_state = keyword
            if verbose:
                print(f"Block TODO_state: {TODO_state}")

            parsed = ParsedBlock(block).parse(
                    block_properties=block_properties,
                    block_hierarchy=cur_headers,
                    block_uuid=block_uuid,
                    indentation_level=cur_indent,
                    parent_block=latest_parents,
                    TODO_state=TODO_state,
                    )

            latest_parents[block_uuid] = cur_indent
            if block in headers:
                cur_headers[block] = cur_indent

            self.parsed_blocks.append(parsed)

            if verbose:
                print("\n---------------------------------")

        if not "\n".join(self.parsed_blocks) == content:
            import difflib
            print(''.join(difflib.ndiff(
                content,
                "\n".join(self.parsed_blocks)
                )))
            raise Exception("file content differed after parsing")
        return self

    def save_as(
            self,
            file_path,
            overwrite=False,
            ):
        """
        save to file_path
        """
        if not overwrite:
            if Path(file_path).exists():
                raise Exception(
                    "file_path already exists, use the overwrite argument")
        with open(file_path, "w") as f:
            for block in self.parsed_blocks:
                f.write(block)
                if block.block_uuid != self.parsed_blocks[-1].block_uuid:
                    f.write("\n")
