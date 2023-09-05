import textwrap
from pathlib import Path
import uuid
import re


class MdText:
    "simple class that stores the markdown blocks in the self.blocks attribute"
    def __init__(
            self,
            content,
            verbose=False,
            ):
        self.verbose = verbose
        assert isinstance(content, str), (
            f"content must be of type string, not '{type(content)}'")

        # detect each block (read each line then merge with the latest block)
        lines = content.split("\n")
        self.page_property = ""  # the property of the whole page have to be stored separatly
        first_block_reached = False
        for i, line in enumerate(lines):
            if not re.match(r"\s*- *", line):  # it's a property or content
                if not first_block_reached:  # page property
                    self.page_property += lines[i] + "\n"
                    lines[i] = None
                else:  # block content
                    ii = 0
                    while True:
                        ii += 1
                        if lines[i-ii] is not None:
                            lines[i-ii] += "\n" + line
                            lines[i] = None
                            break
                        if i-ii <= 0:
                            raise Exception("Endless loop")
            else:
                first_block_reached = True

        blocks = [line for line in lines if line is not None]
        self.page_property = self.page_property.strip()

        if self.verbose:
            print(f"Number of blocks in text: {len(blocks)}")

        # parse each block
        self.blocks = []
        for index, block_str in enumerate(blocks):
            assert isinstance(block_str, str), f"block is not string: '{block_str}'"
            block = MdBlock(
                    content=block_str,
                    verbose=verbose,
                    )
            assert block.content == block_str, (
                "block content modifying unexpectedly")

            if self.verbose:
                print("\n\n---------------------------------\n")
                print(block)
                print("\n")
                print(f"* indentation level: {block.indentation_level}")
                print(f"* TODO state: {block.TODO_state}")
                print(f"* properties: {block.get_properties()}")
                print(f"* UUID: {block.UUID}")

            self.blocks.append(block)

        if not "\n".join([str(b) for b in self.blocks]) == content:
            import difflib
            print(''.join(difflib.ndiff(
                content,
                "\n".join([str(b) for b in self.blocks])
                )))
            raise Exception("file content differed after parsing")
        return self

    def export_to(
            self,
            file_path,
            overwrite=False,
            ):
        """
        export the blocks to file_path
        """
        if not overwrite:
            if Path(file_path).exists():
                raise Exception(
                    "file_path already exists, use the overwrite argument")

        temp = self.page_property
        latest_UUID = self.blocks[-1].UUID

        for block in self.blocks:
            assert str(block).startswith("- ")
            temp += str(block)
            if block.UUID != latest_UUID:
                temp += "\n"
        with open(file_path, "w") as f:
            f.write(temp)

    def __str__(self):
        return "\n".join(self.blocks)

    def __repr__(self):
        return f"MdText({self.__str__()})"


class MdBlock:
    PROP_REGEX = re.compile(r"\s*(\w+):: (\w+)")
    INDENT_REGEX = re.compile(r"^\s*")

    def __init__(
            self,
            content,
            verbose=False,
            ):
        """
        Class with the following new attributes:
            indentation_level: in number of spaces, with tab=4
            TODO_state: wether the block is in a TODO/DOING/NOW/LATER/DONE etc.
                              None otherwise.
            UUID: a random UUID. It is not the same as the one used within
                  Logseq but can be used to keep track of parents.
                  If a UUID is already present in the block properties,
                  it will be used instead.

        And the following methods:
            get_properties: returns a dict
            set_property: set the value to None to delete the property

        Note:
            * For modifying the content, properties, indentation_level or
              TODO_state: changing the value will affect the
              other values. I.e modifying the content to manually edit
              the indentation will have the same effect as modifying
              the indentation_level.
            * the other attributes can not (yet?) be altered
            * if the UUID attribute is changed, it will be inscribed in
              the block as a property, just like Logseq does. By default the
              UUID is random() and not inscribed in the content. Just like
              in Logseq.
        """
        assert content.strip().startswith("-"), (
            f"stripped block content must start with '- '. Not the case here: '{content}'")
        self._blockvalues = {
                'content': content,
                "UUID": str(uuid.uuid4()),  # if accessing self.UUID the UUID
                # will always updates if a id:: property was set in the content
            }
        self._changed = False  # set to True if any value was manually changed
        self.verbose = verbose

    def __str__(self):
        """overloading of the original str to make it access the content
        attribute"""
        return self._blockvalues["content"]

    def __repr__(self):
        return f"MdBlock({self.__str__()})"

    @property
    def content(self):
        return self._blockvalues["content"]

    @content.setter
    def content(self, new):
        old = self._blockvalues["content"]
        assert isinstance(new, str), "new content must be a string"
        assert new.strip().startswith("-"), "stripped new content must start with '-'"
        if new != old:
            self._changed = True
            self._blockvalues["content"] = new

    @property
    def indentation_level(self):
        return self._get_indentation()

    @indentation_level.setter
    def indentation_level(self, new):
        old = self.indentation_level
        if old != new:
            unindented = textwrap.dedent(self.content)
            reindented = textwrap.indent(unindented, " " * new)
            self.content = reindented
            self._changed = True
            assert new == self.indentation_level, (
                "block intentation level apparently failed to be set")

    @property
    def TODO_state(self):
        return self._get_TODO_state()

    @TODO_state.setter
    def TODO_state(self, new):
        old = self._get_TODO_state()
        assert old in ["TODO", "DOING", "NOW", "LATER", "DONE", None], (
            f"Invalid old TODO value: {old}")
        if old:
            assert f"- {old} " in self.content, (
                f"Error: previous state '- {old} ' not in block content but should have been")

        assert new in ["TODO", "DOING", "NOW", "LATER", "DONE", None], (
            f"Invalid new TODO value: {new}")

        if old != new:
            if new is None:  # just delete
                self.content = self.content.replace(
                        f"- {old} ",
                        "- ",
                        count=1,
                        )
            else:
                self.content = self.content.replace(
                        f"- {old} ",
                        f"- {new} ",
                        count=1)
            self._changed = True

    # METHODS:
    def set_property(
            self,
            key,
            value=None):
        """
        set a property to the block.
        if the value is None, the property will be deleted
        Note that this will also directly alter the block content.
        """
        if value is not None:  # add or edit prop
            assert isinstance(value, str), "value must be a string"

            if key in self.properties:  # edit prop
                old_val = self.properties[key]
                assert self.content.count(f"  {key}:: {old_val}") == 1, (
                    "unable to find key/val pair: {key}/{old_val}")
                self.content = re.sub(
                        f"  {key}:: {old_val}",
                        f"  {key}:: {value}",
                        )
            else:  # add prop
                new = "\n" + " " * self.indentation_level
                new += f"  {key}:: {value}"
                self.content = new

            self._changed = True
            assert self.content.count(f"  {key}:: {value}") == 1, (
                "unable to find key/val pair after it was set: {key}/{value}")

            assert key in self.properties, (
                "key apparently failed to be added")
            assert value == self.properties[key], (
                "key apparently failed to be set to the right value")
        else:
            assert key in self.properties, "key not found in properties"
            assert self.content.count(f"  {key}:: ") == 1, (
                    f"invalid number of key {key} in {self.content}")
            temp = []
            for line in self.content.split("\n"):
                if not re.match(rf"\s+{key}:: ", line):
                    temp.append(line)
            new_content = "\n".join(temp)
            assert new_content.count(f"{key}::") == 0, (
                    f"invalid number of key {key} in {new_content}")
            self.content = new_content
            self._changed = True

            assert key not in self.properties, (
                "key apparently failed to be deleted")

    def get_properties(self):
        prop = re.search(self.PROP_REGEX, self.content)
        if not prop:
            properties = {}
        else:
            properties = {
                    k.strip(): v.strip()
                    for k, v in zip(*prop.groups())
                    }
        if self.verbose:
            print(f"Block properties: {properties}")
        return properties

    def _get_TODO_state(self):
        TODO_state = None
        for keyword in ["TODO", "DOING", "NOW", "LATER", "DONE"]:
            if re.match(f"- {keyword} ", self.content):
                assert not TODO_state, (
                    "block content fits multiple TODO states: "
                    f"'{self.content}'")
                TODO_state = keyword
        if self.verbose:
            print(f"Block TODO_state: {TODO_state}")
        return TODO_state

    def _get_indentation(self):
        """count the leading spaces of a block to know the indentation level"""
        n = len(
                re.search(
                    self.INDENT_REGEX,
                    self.content.replace("\t", " " * 4)
                    ).group(0)
                )
        if self.verbose:
            print(f"Block indentation: {n}")
        return n

    @property
    def UUID(self):
        block_properties = self.get_properties()
        if "id" in block_properties:  # retrieving value set as property
            self._blockvalues["UUID"] = block_properties["id"]
        return self._blockvalues["UUID"]

    @UUID.setter
    def UUID(self, new):
        assert isinstance(new, str), "new id must be a string"
        assert new.count("-") == 4, "new id must contain 4 -"
        assert new.replace("-", "").isalnum(), "new id does not look like a UUID4"
        self.set_property(key="id", value=new)
        self._changed = True
