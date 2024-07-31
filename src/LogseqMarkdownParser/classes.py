import sys
import textwrap
from typing import Union, Any
from pathlib import Path, PosixPath
import uuid
import re
import json
import rtoml as toml

__VERSION__: str = "2.15"

# only use beartype if its installed
try:
    from beartype import beartype
except Exception as err:
    pass

# if used in a tqdm loop, it's annoying to have the prints appear
# if tqdm is found, use it instead
try:
    from tqdm import tqdm
    def print(x):
        tqdm.write(str(x))
except Exception as err:
    pass

class ImmutableDict(dict):
    "Dict that can't be modified, used for block properties to tell you to use set_property instead"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__frozen = True
    def __setitem__(self, key, value):
        if self.__frozen:
            raise TypeError("Cannot modify ImmutableDict after initialization")
        super().__setitem__(key, value)
    def __delitem__(self, key):
        if self.__frozen:
            raise TypeError("Cannot modify ImmutableDict after initialization")
        super().__delitem__(key)
    def clear(self):
        raise TypeError("Cannot modify ImmutableDict after initialization")
    def pop(self, key, default=None):
        raise TypeError("Cannot modify ImmutableDict after initialization")
    def popitem(self):
        raise TypeError("Cannot modify ImmutableDict after initialization")
    def setdefault(self, key, default=None):
        raise TypeError("Cannot modify ImmutableDict after initialization")
    def update(self, *args, **kwargs):
        raise TypeError("Cannot modify ImmutableDict after initialization")



class LogseqPage:
    """simple class that stores the markdown blocks in the self.blocks attribute.

    Attributes:
        - blocks
            list of LogseqBlock objects
        - page_properties
            can be edited like a normal dict, as opposed to the block properties
        - __VERSION__
            version of the LogseqMarkdownParser

    Methods:
        - format
        - export_to
        - set_property
        - del_property

    """
    __VERSION__ = __VERSION__
    PAGE_PROP_REGEX = re.compile(r"(\w[\w_-]*\w:: .+)")

    def __init__(
        self,
        content: str,
        check_parsing: bool = False,
        verbose: bool = False,
    ) -> None:
        self.verbose = verbose
        assert isinstance(content, str), (
            f"content must be of type string, not '{type(content)}'")

        content = content.strip()

        # detect each block (read each line then merge with the latest block)
        lines = content.split("\n")

        # convert any leading * to -
        lines = [
            li.replace("* ", "- ", 1) if li.lstrip().startswith("* ") else li
            for li in lines
        ]

        assert lines[0].lstrip().startswith("-") or lines[0].lstrip().startswith("#") or ":: " in lines[0] or (len(lines) == 1 and not lines[0].strip()
                                                                          ), f"First line of document must start with '[ \t]*- ' or '[ \t]*#' or contain a page property or the document must be empty"
        lines = [l for l in lines if l.strip()]  # remove empty lines
        pageprop = ""  # as string first
        first_block_reached = False
        for i, line in enumerate(lines):
            if not line.strip():
                lines[i] = None
            elif not line.lstrip().startswith("- "):  # it's a property or content
                if not first_block_reached:  # page property
                    pageprop += lines[i] + "\n"
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

        if blocks:
            assert first_block_reached

        self.page_properties = {}  # the property of the whole page have to be stored separately
        prop = re.findall(self.PAGE_PROP_REGEX, pageprop)
        for found in prop:
            assert found == found.lstrip(), f"Incorrect page property? {found}"
            try:
                key, value = found.split(":: ")
                self.page_properties[key.strip()] = value.strip()
            except ValueError as err:
                # probably failed because it was not a property but a long line that contained ::
                raise Exception(f"Failed to parse page property: {found}")

        if self.verbose:
            print(f"Number of blocks in text: {len(blocks)}")

        # parse each block
        self.blocks = []
        for index, block_str in enumerate(blocks):
            assert isinstance(
                block_str, str), f"block is not string: '{block_str}'"
            block = LogseqBlock(
                content=block_str,
                verbose=self.verbose,
            )
            assert block.content == block_str.replace(u"\xa0", u" "), (
                "block content modifying unexpectedly")

            if self.verbose:
                print("\n\n---------------------------------\n")
                print(block)
                print("\n")
                print(f"* indentation level: {block.indentation_level}")
                print(f"* TODO state: {block.TODO_state}")
                print(f"* properties: {block.properties}")
                print(f"* UUID: {block.UUID}")

            self.blocks.append(block)

        if not check_parsing:
            return
        reformed = self.content
        content = "\n".join([l for l in content.split("\n") if l.strip()])
        if reformed.replace(u"\xa0", u" ") != content.replace(u"\xa0", u" "):
            print("\n\nError: file content differed after parsing:")
            print(f"Length: '{len(reformed)}' vs '{len(content)}'")
            print("Nb lines: '" + str(len(reformed.split('\n'))) +
                  " vs '" + str(len(content.split('\n'))) + "'")
            spco = content.split("\n")
            spref = reformed.split("\n")
            nref = len(spref)

            print(f"Different lines between original and parsed:")
            for i in range(len(spco)):
                if len(spco) == len(spref):
                    if spco[i] == spref[i]:
                        continue
                    else:
                        print(f"Different line:")
                        print(f"reference: '{spco[i]}'")
                        print(f"reformed:  '{spref[i]}'")
                        print("\n------------------------\n")
                else:
                    print(f"reference: '{spco[i]}'")
                    if i < nref and spco[i] != spref[i]:
                        print(f"reformed:  '{spref[i]}'")
                    print("\n------------------------\n")
            raise Exception("file content differed after parsing")

    @property
    def content(self) -> str:
        """return the concatenated list of each block of the page. It cannot
        be edited: you have to edit the block's content instead.

        The page properties are present at the top just like in logseq.
        Note that the leading spaces are not replaced by tabs, so logseq might
        overwrite them badly so use self.export_to instead if you want to save
        the file to Logseq"""
        temp = "\n".join(
            [f"{k}:: {v}" for k, v in self.page_properties.items()])
        if self.blocks:
            if temp:
                temp += "\n"
            latest_UUID = self.blocks[-1].UUID

            for block in self.blocks:
                assert str(block).lstrip().startswith("-")
                bil = block.indentation_level
                if not bil % 4 == 0:
                    newbil = (1 + bil // 4) * 4
                    if self.verbose:
                        print(
                            "block has an indentation level not "
                            f"divisible by 4: '{bil % 4}' in block {block}. "
                            f"setting indentation to {newbil}")
                    block.indentation_level = newbil
                temp += str(block)
                if block.UUID != latest_UUID:
                    temp += "\n"
        temp = textwrap.dedent(temp)
        temp = temp.strip()
        return temp

    @content.setter
    def content(self, new: str) -> None:
        raise Exception(
            "Cannot edit page content directly. "
            "You have to edit the blocks individually.")

    def set_property(self, key: str, value: Any) -> None:
        """
        The key must be a string and the value will be cast as string.
        You can edit self.page_properties as a regular dict instead of using this method.
        """
        try:
            value = str(value)
        except Exception as err:
            raise Exception(
                f"Failed to parse as string: '{value}' (err:{err})")
        self.page_properties[key] = value

    def del_property(self, key: str) -> None:
        """
        The key must be a string and the value will be cast as string.
        You can edit self.page_properties as a regular dict instead of using this method.
        """
        assert key in self.page_properties, (
            f"No {key} found in page_properties key so can't delete it")
        del self.page_properties[key]

    def export_to(
        self,
        file_path: Union[str, PosixPath],
        overwrite: bool = False,
        allow_empty: bool = False,
    ) -> None:
        """
        export the blocks to file_path
        Note that the leading spaces are replaced by tabs, so Logeq will not
        overwrite them (and sometimes badly!).
        """
        if not overwrite:
            if Path(file_path).exists():
                raise Exception(
                    "file_path already exists, use the overwrite argument")

        cont = self.content

        cont = cont.replace("    ", "\t")

        if not cont:
            assert allow_empty, "Can't save an empty file if allow_empty is False"

        with open(file_path, "w") as f:
            f.write(cont)

    def __str__(self) -> str:
        return "\n".join([str(b) for b in self.blocks])

    def __repr__(self) -> str:
        return f"LogseqPage({self.__str__()})"

    def format(self, format: str) -> Union[list[dict], str]:
        """returns the whole logseq page formatted.
        Expected formats are "list_of_dict", "json", "toml".
        'json' for example can be piped directly to jq in a shell.
        In all cases, the format will be a python list of dict, that is then
        parsed depending on the keyword. Note that the first item of the list
        will always be the page_properties.
        """
        cont = [block.export(format="dict") for block in self.blocks]
        if format == "list_of_dict":
            return cont
        elif format == "json":
            return json.dumps(cont, ensure_ascii=False, indent=2)
        elif format == "toml":
            return toml.dumps(cont, pretty=True)
        else:
            raise ValueError(format)


class LogseqBlock:
    BLOCK_PROP_REGEX = re.compile(r"[ \t]+(\w[\w_-]*\w:: .+)")
    INDENT_REGEX = re.compile(r"^[ \t]*")
    __VERSION__ = __VERSION__

    def __init__(
            self,
            content: str,
            verbose: bool = False,
    ) -> None:
        """
        Class with the following new attributes:
            - indentation_level: in number of spaces, with tab=4
            - TODO_state: wether the block is in a TODO/DOING/NOW/LATER/DONE etc.
                              None otherwise.
            - UUID: a random UUID. It is not the same as the one used within
                  Logseq but can be used to keep track of parents.
                  If an 'id' property is already present in the block,
                  it will be used instead, this is the case if the UUID was
                  set by Logseq.
            - properties: an ImmutableDict containing the block properties.

        And the following methods:
            - set_property
            - del_property

        Note:
            - For modifying the content, properties, indentation_level or
              TODO_state: changing the value will affect the
              other values. I.e modifying the content to manually edit
              the indentation will have the same effect as modifying
              the indentation_level.
            - the other attributes can not (yet?) be altered
            - if the UUID attribute is changed, it will be inscribed in
              the block as an id property, just like Logseq does. By default the
              UUID is random() and not inscribed in the content. Just like
              in Logseq.
            - verbose argument is currently unused
        """
        assert content.lstrip().startswith("-"), (
            f"stripped block content must start with '- '. Not the case here: '{content}'")
        self.verbose = verbose
        content = content.replace(u'\xa0', u' ')  # replace by regular space
        self._blockvalues = {
            'content': content,
        }
        if "id" in self.properties:
            self._blockvalues["UUID"] = self.properties["id"]
        else:
            self._blockvalues["UUID"] = str(uuid.uuid4())
        self._changed = False  # set to True if any value was manually changed

    def __str__(self) -> str:
        """overloading of the original str to make it access the content
        attribute"""
        return self._blockvalues["content"]

    def __repr__(self) -> str:
        return f"LogseqBlock({self.__str__()})"

    @property
    def content(self) -> str:
        "content of the block. This includes the block properties."
        cont = self._blockvalues["content"]
        return cont

    @content.setter
    def content(self, new: str) -> None:
        old = self._blockvalues["content"]
        assert isinstance(new, str), "new content must be a string"
        assert new.lstrip().startswith(
            "-") or ":: " in new, "stripped new content must start with '-' or be a property"
        new = new.replace(u'\xa0', u' ')
        if new != old:
            self._changed = True
            self._blockvalues["content"] = new

    @property
    def indentation_level(self) -> int:
        return self._get_indentation()

    @indentation_level.setter
    def indentation_level(self, new: int) -> None:
        # note: we don't compare the new to the old value
        # because this way we make sure that leading spaces are replaced
        # by tabs
        assert new % 4 == 0, f"new indentation level must be divisible by 4, not {new}"
        unindented = textwrap.dedent(self.content)
        reindented = textwrap.indent(unindented, "\t" * (new // 4))
        self.content = reindented
        self._changed = True
        assert new == self.indentation_level, (
            "block intentation level apparently failed to be set")

    @property
    def TODO_state(self) -> Union[None, str]:
        return self._get_TODO_state()

    @TODO_state.setter
    def TODO_state(self, new: str) -> None:
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
                    1,
                )
            else:
                self.content = self.content.replace(
                    f"- {old} ",
                    f"- {new} ",
                    1)
            self._changed = True

    @property
    def properties(self) -> ImmutableDict:
        "Shows the block properties, but to modify them, you have to use the 'set_property' method"
        return self._get_properties()

    @properties.setter
    def property_failedsetter(self, *args, **kwargs) -> None:
        raise Exception(
            "To modify the properties you must use self.set_property(key, value)")

    def _get_properties(self) -> ImmutableDict:
        prop = re.findall(self.BLOCK_PROP_REGEX, self.content)
        properties = {}
        for found in prop:
            assert found == found.lstrip(
            ), f"REGEX match an incorrect property: {found}"

            try:
                key, value = found.split(":: ")
                properties[key.strip()] = value.strip()
            except ValueError as err:
                # probably failed because it was not a property but a long line that contained ::
                raise Exception(f"Failed to parse property: {found}")

        cont = self.content
        for k, v in properties.items():
            assert f"{k}:: " in cont, f"Missing key '{k}' in content"
            assert f"{k}:: {v}" in cont, f"Missing key/value {key}/{value} in content"

        n_id = len(re.findall(r"[ \t]+id:: [\w-]+", cont))
        assert n_id in [0, 1], f"Found {n_id} mention of id:: property"
        properties = ImmutableDict(properties)

        return properties

    # METHODS:

    def del_property(
        self,
        key: str,
        ) -> None:
        """
        Delete a property of the block.
        Note that this will also directly alter the block content.
        """
        assert isinstance(key, str), f"key must be a string, not {type(key)}"
        assert key in self.properties, "key not found in properties"
        count =  self.content.count(f"  {key}:: ")
        assert count == 1, (
            f"Key {key} found {count} times in {self.content}")
        temp = []
        for line in self.content.split("\n"):
            if not re.search(rf"[ \t]+{key}:: ", line):
                temp.append(line)
        new_content = "\n".join(temp)
        assert new_content.count(f"{key}::") == 0, (
            f"invalid number of key {key} in {new_content}")
        self.content = new_content
        self._changed = True

        assert key not in self.properties, (
            "key apparently failed to be deleted")

    def set_property(
            self,
            key: str,
            value: Any,
        ) -> None:
        """
        Set a property to the block.
        The key must be a string and the value will be cast as string.
        Note that this will also directly alter the block content.
        """
        assert isinstance(key, str), f"key must be a string, not {type(key)}"
        try:
            value = str(value)
        except Exception as err:
            raise Exception(
                f"Failed to parse as string: '{value}' (err:{err})")

        assert value, f"Cannot add empty string property for key {key}"
        assert len(value.splitlines()
                    ) == 1, "cannot add property containing newlines"

        old_content = self.content
        if key in self.properties:  # edit prop
            old_val = self.properties[key]
            assert self.content.count(f"  {key}:: {old_val}") == 1, (
                "unable to find key/val pair: {key}/{old_val}")
            self.content = self.content.replace(
                f"  {key}:: {old_val}",
                f"  {key}:: {value}",
            )
        else:  # add prop
            new = "\n" + "\t" * (self.indentation_level // 4)
            new += f"  {key}:: {value}"
            self.content += new
            assert old_content in self.content

        self._changed = True
        assert self.content.count(f"  {key}:: {value}") == 1, (
            "unable to find key/val pair after it was set: {key}/{value}")

        assert key in self.properties, (
            "key apparently failed to be added")
        assert value == self.properties[key], (
            "key apparently failed to be set to the right value")

    def format(self, format: str) -> Union[dict, str]:
        """format the block. Formats are 'dict', 'json', 'toml'"""
        assert format in ["dict", "json", "toml"], "supportted format are dict, json, toml"
        d = {
            "block_properties": self.properties,
            "block_content": self.content,
            "block_indentation_level": self.indentation_level,
            "block_TODO_state": self.TODO_state,
            "block_UUID": self.UUID,
        }
        if format == "dict":
            return d
        elif format == "json":
            return json.dumps(d, ensure_ascii=False, indent=2)
        elif format == "toml":
            return toml.dumps(d, pretty=True)
        else:
            raise ValueError(format)

    def _get_TODO_state(self) -> Union[None, str]:
        TODO_state = None
        for keyword in ["TODO", "DOING", "NOW", "LATER", "DONE"]:
            if re.search(f"- {keyword} .*", self.content.lstrip()):
                assert not TODO_state, (
                    "block content fits multiple TODO states: "
                    f"'{self.content}'")
                TODO_state = keyword
        return TODO_state

    def _get_indentation(self) -> int:
        """count the leading spaces of a block to know the indentation level"""
        n = len(
            re.search(
                self.INDENT_REGEX,
                self.content.replace("\t", " " * 4)
            ).group(0)
        )
        return n

    @property
    def UUID(self) -> str:
        block_properties = self.properties
        if "id" in block_properties:  # retrieving value set as property
            self._blockvalues["UUID"] = block_properties["id"]
        return self._blockvalues["UUID"]

    @UUID.setter
    def UUID(self, new: str) -> None:
        assert isinstance(new, str), "new id must be a string"
        assert new.count("-") == 4, "new id must contain 4 -"
        assert new.replace(
            "-", "").isalnum(), "new id does not look like a UUID4"
        self.set_property(key="id", value=new)
        self._changed = True


if "beartype" in sys.modules:
    LogseqBlock = beartype(LogseqBlock)
    LogseqPage = beartype(LogseqPage)
