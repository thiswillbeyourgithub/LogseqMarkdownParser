import textwrap
from typing import Union, Any, Callable
import uuid6
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

@typechecker
class LogseqBlock:
    BLOCK_PROP_REGEX = re.compile(r"[ \t]+(\w[\w_-]*\w:: .+)")
    INDENT_REGEX = re.compile(r"^[ \t]*")

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
                  set by Logseq. Otherwise, a UUI6 (so sortable by time) will
                  be used.
            - properties: an ImmutableDict containing the block properties.

        Methods:
            - dict
            - format
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
            self._blockvalues["UUID"] = str(uuid6.uuid6())
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
        unindented = textwrap.dedent(self.content).strip()
        reindented = textwrap.indent(unindented, "\t" * (new // 4))
        self.content = reindented
        self._changed = True
        assert new == self.indentation_level, (
            "block indentation level apparently failed to be set")

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
            except ValueError:
                # probably failed because it was not a property but a long line that contained ::
                raise Exception(f"Failed to parse property: {found}")

        cont = self.content
        for k, v in properties.items():
            assert f"{k}:: " in cont, f"Missing key '{k}' in content"
            assert f"{k}:: {v}" in cont, f"Missing key/value {key}/{value} in content"

        n_id = len(re.findall(r"[ \t]+id:: [\w-]+", cont))
        assert n_id in [0, 1], f"Found {n_id} mention of id:: property"
        properties = ImmutableDict(properties.copy())

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
        count =  self.content.count(f"{key}:: ")
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
            assert self.content.count(f"{key}:: {old_val}") == 1, (
                "unable to find key/val pair: {key}/{old_val}")
            lines = self.content.splitlines(keepends=True)[::-1]
            for ili, li in enumerate(lines):
                if f"{key}:: {old_val}" in li:
                    li[ili] = li.replace(old_val, value)
                    break
            self.content = "".join(lines[::-1])
        else:  # add prop
            new = "\n" + "\t" * (self.indentation_level // 4)
            new += f"  {key}:: {value}"
            self.content += new
            assert old_content in self.content

        self._changed = True
        assert self.content.count(f"{key}:: {value}") == 1, (
            "unable to find key/val pair after it was set: {key}/{value}")

        assert key in self.properties, (
            "key apparently failed to be added")
        assert value == self.properties[key], (
            "key apparently failed to be set to the right value")

    def format(self, format: str) -> Union[dict, str]:
        """format the block. Formats are 'dict', 'json', 'toml'"""
        assert format in ["dict", "json", "toml"], "supportted format are dict, json, toml"
        d = {
            "block_properties": dict(self.properties).copy(),
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

    def dict(self) -> dict:
        """returns the block as a dict. Same as self.format('dict')"""
        return self.format(format="dict")

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
            "-", "").isalnum(), "new id does not look like a UUID6"
        self.set_property(key="id", value=new)
        self._changed = True
