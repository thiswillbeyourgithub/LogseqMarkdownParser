import textwrap
from typing import Union, Any, Callable
from pathlib import Path, PosixPath
import re
import json
import rtoml as toml

# only use beartype if its installed
try:
    from beartype import beartype as typechecker
except Exception:
    def typechecker(func: Callable) -> Callable:
        return func

# if used in a tqdm loop, it's annoying to have the prints appear
# if tqdm is found, use it instead
try:
    from tqdm import tqdm
    def print(x):
        tqdm.write(str(x))
except Exception:
    pass

from .blocks import LogseqBlock


@typechecker
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
        - dict
        - format
        - export_to
        - set_property
        - del_property

    """
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
                                                                          ), (
                    "First line of document must start with '[ \t]*- ' or '[ \t]*#' or contain a page property or the document must be empty"
        )
        lines = [li for li in lines if li.strip()]  # remove empty lines
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
            except ValueError:
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
        content = "\n".join([li for li in content.split("\n") if li.strip()])
        if reformed.replace(u"\xa0", u" ") != content.replace(u"\xa0", u" "):
            print("\n\nError: file content differed after parsing:")
            print(f"Length: '{len(reformed)}' vs '{len(content)}'")
            print("Nb lines: '" + str(len(reformed.split('\n'))) +
                  " vs '" + str(len(content.split('\n'))) + "'")
            spco = content.split("\n")
            spref = reformed.split("\n")
            nref = len(spref)

            print("Different lines between original and parsed:")
            for i in range(len(spco)):
                if len(spco) == len(spref):
                    if spco[i] == spref[i]:
                        continue
                    else:
                        print("Different line:")
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
        return self.content

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
        page_prop = self.page_properties
        cont = [page_prop] + [block.dict() for block in self.blocks]

        if format == "list_of_dict":
            return cont
        elif format == "json":
            return json.dumps(cont, ensure_ascii=False, indent=2)
        elif format == "toml":
            return toml.dumps(cont, pretty=True)
        else:
            raise ValueError(format)

    def dict(self) -> dict:
        """returns the page, with its page properties and blocks as a single dict"""
        d = {
            "page_properties": self.page_properties,
            "page_content": self.content,
            "blocks": [b.dict() for b in self.blocks],
        }
        return d
