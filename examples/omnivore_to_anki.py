"""
WORK IN PROGRESS

Simple script to turn highlights from Omnivore to anki cards using logseq-anki-sync


Here's my Omnivore highlight template:
'''
TODO > {{{text}}}

omnivore_highlightposition:: {{{positionPercent}}}
omnivore_highlightindex:: {{{positionAnchorIndex}}}
omnivore-type:: highlight
omnivore_highlighturl:: {{{highlightUrl}}}
omnivore_highlightdatehighlighted:: {{{rawDateHighlighted}}}
omnivore_highlightcolor:: {{{color}}}
{{#labels}}omnivore_highlightlabels:: #[[{{{name}}}]] {{/labels}}
{{#note.length}}omnivore_highlightnote:: {{{note}}} {{/note.length}}
'''
"""

from datetime import datetime
from tqdm import tqdm
from pathlib import Path
import fire
import pdb
import signal

import LogseqMarkdownParser


class omnivore_to_anki:
    def __init__(
            self,
            graph_dir,
            start_name,
            context_size=2000,
            unhighlight_others=True,
            debug=True,
            ):
        """
        parameters:
        ----------
        graph_dir
            path to your logseq dir

        start_name
            the common beginning of the name of the files created by omnivore
        context_size
            number of characters to take around each highlight

         unhighlight_others: bool, default True
            if True, remove highlight '==' around highlights when creating the cloze

         debug: bool, default True
        """
        assert Path(graph_dir).exists(), f"Dir not found: {graph_dir}"

        self.csize = context_size
        self.debug = debug
        self.unhighlight_others=unhighlight_others

        # make the script interruptible
        if debug:
            signal.signal(signal.SIGINT, (lambda signal, frame : pdb.set_trace()))

        # get list of files to check
        files = [f
                 for f in (Path(graph_dir) / "pages").iterdir()
                 if f.name.startswith(start_name)
                 and f.name.endswith(".md")
                 ]

        assert files, f"No files found in {graph_dir} with start_name {start_name}"

        # sort files by date
        def _parse_date(path):
            cont = path.read_text()
            s = cont.split("date-saved:: ")[1].split("]]")[0][2:]
            date = datetime.strptime(s, "%d-%m-%Y")
            return date

        files = sorted(
                files,
                key=lambda f: _parse_date(f)
                )

        # filter only those that contain TODO
        files = [f for f in files if "- TODO " in f.read_text()]
        assert files, "No files contained TODO"

        print(f"Found {len(files)} omnivore articles to create anki cards for")

        for f_article in tqdm(files, unit="article"):
            self.parse_one_article(f_article)


    def parse_one_article(self, f_article):
        anki_clozes = {}  # store cloze for each highlight block UUID
        article = None

        parsed = LogseqMarkdownParser.parse_file(f_article, verbose=False)
        assert len(parsed.blocks) > 4

        blocks = parsed.blocks.copy()
        for ib, block in enumerate(tqdm(blocks, unit="block")):
            # find the block containing the article
            if article is None:
                if block.content.startswith("\t- ### Content"):
                    article = blocks[ib+1]
                    art_cont = self.parse_block_content(article)
                continue

            prop = block.properties

            # check that no anki cards were created already
            if "omnivore-type" in prop:
                assert prop["omnivore-type"] != "highlightcloze", f"Cloze already created?! {prop} for {block}"

            # highlight
            if block.TODO_state == "TODO":
                assert prop["omnivore-type"] == "highlight", f"Unexpected block properties: {prop}"
                assert block.indentation_level > 2, f"Unexpected block indentation: {prop.indentation_level}"

                # get content of highlight
                high = self.parse_block_content(block)

                # remove quot indent
                assert high.startswith("> "), f"Highlight should begin with '> ': '{high}'"
                high = high[2:].strip()
                assert high

                if high not in art_cont:
                    breakpoint()
                assert high in art_cont, f"Highlight not part of article:\n{high}\nNot in:\n{art_cont}"

                # TODO check position of the highlight but for now it's
                # always stuck at 0
                if str(prop["omnivore_highlightposition"]) != "0":
                    breakpoint()

                if art_cont.count(high) == 1:
                    # if present only once: proceed
                    ind = art_cont.index(high)
                    before = art_cont[max(0, ind-self.csize//2):ind]
                    remaining = max(self.csize // 2, self.csize - len(before)) + len(high)
                    after = art_cont[ind:ind+remaining]
                    context = before + after
                    assert context
                    assert high in context
                    assert abs(len(context) / self.csize - 1) < 0.3

                    # add cloze
                    cloze = self.context_to_cloze(high, context)

                    # store position and cloze
                    anki_clozes[block.UUID] = cloze

                else:
                    # if present several times: concatenate all the cloze as once
                    # this is by far the simplest way to do it

                    # getting all positions in the text
                    positions = []
                    for ic in range(art_cont.count(high)):
                        if not positions:
                            positions.append(art_cont.index(high))
                        else:
                            positions.append(art_cont.index(high, positions[-1]+1))

                    # first case: all appearances are withing the context_size
                    if max(positions) - min(positions) < self.csize:
                        context = art_cont[min(positions) - self.csize//4:max(positions)+self.csize // 4]
                        assert len(context) < 2 * self.csize
                        assert context.count(high) == art_cont.count(high)

                        cloze = self.context_to_cloze(high, context)

                        anki_clozes[block.UUID] = cloze

                    # else: create one cloze for each and one card containing all those clozes
                    else:
                        # find ranges of each clozes
                        ranges = []
                        for p in positions:
                            ranges.append([max(0, p-self.csize//2)])
                            remaining = max(self.csize//2, self.csize-ranges[-1][-1]) + len(high)
                            ranges[-1].append(p+remaining)

                        # fuse ranges that are close together
                        while True:
                            for ir, r in enumerate(ranges):
                                if ir == len(ranges):  # special case: last range
                                    if r[0] < ranges[ir-1][1]:
                                        ranges[ir][0] = ranges[ir-1][0]
                                        ranges[ir-1] = None
                                        break
                                else:
                                    if r[1] > ranges[ir+1][0]:
                                        ranges[ir][1] = ranges[ir+1][1]
                                        ranges[ir+1] = None
                                        break
                            if None not in ranges:
                                ranges = [r for r in ranges if r is not None]
                                break
                            if len(ranges) == 1:
                                break
                        assert ranges
                        assert all (r1<r2 for r1, r2 in ranges)

                        clozes = []
                        for r1, r2 in ranges:
                            context = art_cont[r1 - self.csize//4:r2+self.csize//4]
                            clozes.append(self.context_to_cloze(high, context))
                        cloze = "\n\n".join(clozes)

                        anki_clozes[block.UUID] = cloze

        assert article is not None, f"Failed to find article in blocks: {blocks}"
        assert len(anki_clozes) == len(blocks)

        # insert cloze as blocks
        done = []
        for uuid, cloze in anki_clozes.items():
            for ib, block in parsed.blocks:
                if block.UUID == uuid:
                    break
            assert block.UUID == uuid

            # turn the cloze into a block
            cloze_block = LogseqMarkdownParser.MdBlock("- " + cloze, verbose=False)
            cloze_block.indentation_level = block.indentation_level + 4
            cloze_block.set_property("omnivore-type", "highlightcloze")
            cloze_block.set_property("omnivore-clozedate", str(datetime.today()))
            cloze_block.set_property("omnivore-clozeparentuuid", block.UUID)

            # add the cloze as block
            parsed.blocks.insert(ib+1, cloze_block)
            parsed.blocks[ib].TODO_state = "DONE"


        # export to file
        print(f"Exporting {f_article}")
        parsed.export_to(f_article.parent / (f_article.name + "_temp"), overwrite=False)

        breakpoint()
        # delete old
        f_article.unlink()
        # rename
        (f_article.parent / (f_article.name + "_temp")).rename(f_article)

    def parse_block_content(self, block):
        cont = block.content
        prop = block.properties
        for k, v in prop.items():
            cont = cont.replace(f"{k}:: {v}", "")
        if block.TODO_state:
            cont = cont.replace(block.TODO_state, "")
        cont = cont.replace("- ", "", 1)
        cont = cont.strip()
        if self.unhighlight_others:
            cont = cont.replace("==", "").strip()
        return cont

    def context_to_cloze(self, highlight, context):
        assert highlight in context

        if self.unhighlight_others:
            context = context.replace("==", "")
            cloze = "..." + context.replace(highlight, "=={{c1 " + highlight + " }}==") + "..."
        else:
            cloze = "..." + context.replace(highlight, "{{c1 " + highlight + " }}") + "..."

        return cloze




if __name__ == "__main__":
    fire.Fire(omnivore_to_anki)
