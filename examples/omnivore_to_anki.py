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

from typing import List
from math import inf

from Levenshtein import distance as ld
import LogseqMarkdownParser


class omnivore_to_anki:
    def __init__(
            self,
            graph_dir,
            start_name,
            context_size=2000,
            unhighlight_others=False,
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

         unhighlight_others: bool, default False
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
        n_highlight_blocks = 0
        assert len(set(b.UUID for b in blocks)) == len(blocks), "Some blocks have non unique UUID"
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
                n_highlight_blocks += 1
                assert prop["omnivore-type"] == "highlight", f"Unexpected block properties: {prop}"
                assert block.indentation_level > 2, f"Unexpected block indentation: {prop.indentation_level}"

                # get content of highlight
                high = self.parse_block_content(block)

                # remove quot indent
                assert high.startswith("> "), f"Highlight should begin with '> ': '{high}'"
                high = high[2:].strip()
                assert high

                matching_art_cont = art_cont
                if high not in art_cont:
                    best_substring_match, min_distance = match_highlight_to_corpus(high, art_cont)
                    matching_art_cont = art_cont.replace(best_substring_match, high, 1)
                assert high in matching_art_cont, f"Highlight not part of article:\n{high}\nNot in:\n{art_cont}"

                # TODO check position of the highlight but for now it's
                # always stuck at 0
                if str(prop["omnivore_highlightposition"]) != "0":
                    breakpoint()

                if matching_art_cont.count(high) == 1:
                    # if present only once: proceed
                    ind = matching_art_cont.index(high)
                    before = matching_art_cont[max(0, ind-self.csize//2):ind]
                    remaining = max(self.csize * 3 // 4, self.csize - len(before)) - len(high)
                    after = matching_art_cont[ind:ind+remaining]
                    context = before + after
                    assert context
                    assert high in context
                    assert abs(len(context) / self.csize - 1) < 0.3

                    # add cloze
                    cloze = self.context_to_cloze(high, context)

                    # store position and cloze
                    anki_clozes[block.UUID] = cloze

                elif matching_art_cont.count(high) > 1:
                    # if present several times: concatenate all the cloze as once
                    # this is by far the simplest way to do it

                    # getting all positions in the text
                    positions = []
                    for ic in range(matching_art_cont.count(high)):
                        if not positions:
                            positions.append(matching_art_cont.index(high))
                        else:
                            positions.append(matching_art_cont.index(high, positions[-1]+1))

                    # first case: all appearances are withing the context_size
                    if max(positions) - min(positions) < self.csize:
                        context = matching_art_cont[min(positions) - self.csize//4:max(positions)+self.csize // 4]
                        assert len(context) < 2 * self.csize
                        assert context.count(high) == matching_art_cont.count(high)

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
                            context = matching_art_cont[r1 - self.csize//4:r2+self.csize//4]
                            clozes.append(self.context_to_cloze(high, context))
                        cloze = "\n\n".join(clozes)

                        anki_clozes[block.UUID] = cloze
                else:
                    raise ValueError(f"Highlight was not part of the article? {high}")

        assert article is not None, f"Failed to find article in blocks: {blocks}"
        assert len(anki_clozes) == n_highlight_blocks

        # insert cloze as blocks
        done = []
        for uuid, cloze in anki_clozes.items():
            for ib, block in enumerate(parsed.blocks):
                if block.UUID == uuid:
                    break
            assert block.UUID == uuid

            # turn the cloze into a block
            cloze_block = LogseqMarkdownParser.classes.MdBlock("- " + cloze, verbose=False)
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


def match_highlight_to_corpus(
        query: str,
        corpus: str,
        case_sensitive: bool = True,
        step_factor: int = 128,
        favour_smallest: bool = False,
    ) -> List:
    '''
    Source: https://stackoverflow.com/questions/36013295/find-best-substring-match
    Returns the substring of the corpus with the least Levenshtein distance from the query
    (May not always return optimal answer).

    Arguments
    - query: str
    - corpus: str
    - case_sensitive: bool
    - step_factor: int  
        Influences the resolution of the thorough search once the general region is found.
        The increment in ngrams lengths used for the thorough search is calculated as len(query)//step_factor.
        Increasing this increases the number of ngram lengths used in the thorough search and increases the chances 
        of getting the optimal solution at the cost of runtime and memory.
    - favour_smaller: bool
        Once the region of the best match is found, the search proceeds from larger to smaller ngrams or vice versa.
        If two or more ngrams have the same minimum distance then this flag controls whether the largest or smallest
        is returned.

    Returns  
    [Best matching substring of corpus, Levenshtein distance of closest match]
    '''

    if not case_sensitive:
        query = query.casefold()
        corpus = corpus.casefold()

    corpus_len = len(corpus)
    query_len = len(query)
    query_len_by_2 = max(query_len // 2, 1)
    query_len_by_step_factor = max(query_len // step_factor, 1)

    closest_match_idx = 0
    min_dist = inf
    # Intial search of corpus checks ngrams of the same length as the query
    # Step is half the length of the query.
    # This is found to be good enough to find the general region of the best match in the corpus
    corpus_ngrams = [corpus[i:i+query_len] for i in range(0, corpus_len-query_len+1, query_len_by_2)]
    for idx, ngram in enumerate(corpus_ngrams):
        ngram_dist = ld(ngram, query)
        if ngram_dist < min_dist:
            min_dist = ngram_dist
            closest_match_idx = idx

    closest_match_idx = closest_match_idx * query_len_by_2
    closest_match = corpus[closest_match_idx: closest_match_idx + query_len]
    left = max(closest_match_idx - query_len_by_2 - 1, 0)
    right = min((closest_match_idx+query_len-1) + query_len_by_2 + 2, corpus_len)
    narrowed_corpus = corpus[left: right]
    narrowed_corpus_len = len(narrowed_corpus)

    # Once we have the general region of the best match we do a more thorough search in the region
    # This is done by considering ngrams of various lengths in the region using a step of 1
    ngram_lens = [l for l in range(narrowed_corpus_len, query_len_by_2 - 1, -query_len_by_step_factor)]
    if favour_smallest:
        ngram_lens = reversed(ngram_lens)
    # Construct sets of ngrams where each set has ngrams of a particular length made over the region with a step of 1
    narrowed_corpus_ngrams = [
        [narrowed_corpus[i:i+ngram_len] for i in range(0, narrowed_corpus_len-ngram_len+1)]
        for ngram_len in ngram_lens
    ]

    # Thorough search of the region in which the best match exists
    for ngram_set in narrowed_corpus_ngrams:
        for ngram in ngram_set:
            ngram_dist = ld(ngram, query)
            if ngram_dist < min_dist:
                min_dist = ngram_dist
                closest_match = ngram

    return closest_match, min_dist


if __name__ == "__main__":
    fire.Fire(omnivore_to_anki)
