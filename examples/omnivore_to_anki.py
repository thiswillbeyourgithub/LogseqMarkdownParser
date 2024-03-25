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

import magic
import re
import tempfile
import requests
import json
from textwrap import dedent
from datetime import datetime
from tqdm import tqdm
from pathlib import Path
import fire
import uuid

import pandas as pd
from joblib import Parallel, delayed, Memory

from typing import List
from math import inf

import Levenshtein as lev

# to parse PDF
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain_community.document_loaders import PyPDFium2Loader
from langchain_community.document_loaders import PyMuPDFLoader
# from langchain_community.document_loaders import PDFMinerPDFasHTMLLoader
from langchain_community.document_loaders import PDFMinerLoader
from langchain_community.document_loaders import PDFPlumberLoader
from langchain_community.document_loaders import OnlinePDFLoader
from functools import partial
from unstructured.cleaners.core import clean_extra_whitespace
try:
    import pdftotext
except Exception as err:
    print(f"Failed to import pdftotext: '{err}'")
if "pdftotext" in globals():
    class pdftotext_loader_class:
        "simple wrapper for pdftotext to make it load by pdf_loader"
        def __init__(self, path):
            self.path = path

        def load(self):
            with open(self.path, "rb") as f:
                return "\n\n".join(pdftotext.PDF(f))
emptyline_regex = re.compile(r"^\s*$", re.MULTILINE)
emptyline2_regex = re.compile(r"\n\n+", re.MULTILINE)
linebreak_before_letter = re.compile(
    r"\n([a-záéíóúü])", re.MULTILINE
)  # match any linebreak that is followed by a lowercase letter





#import LogseqMarkdownParser
import sys
saved_path = sys.path
sys.path.insert(0, "../src")
sys.path.insert(0, "../src/LogseqMarkdownParser")
import LogseqMarkdownParser
sys.path = saved_path

mem = Memory(".cache", verbose=False)

context_extenders = {
    re.compile(r"\s+\# .+"): 300,
    re.compile(r"\s+\#\# .+"): 300,
    re.compile(r"\s+\#\#\# .+"): 300,
    re.compile(r"\s+\#\#\#\# .+"): 300,
    re.compile(r"\s+\#\#\#\# .+"): 300,
    re.compile(r"\n\n+"): 300,
    re.compile(r"\n"): 300,
    re.compile(". "): 300,
    re.compile(" "): 300,
}
highlight_extenders = {
    re.compile(". "): 5,
    re.compile("."): 5,
    re.compile(" "): 5,
}
# backwards
bkw_cont_ext = {}
for k, v in context_extenders.items():
    k = k.pattern[::-1]
    k = list(k)
    for ik, kk in enumerate(k):
        if kk in ["\\", "+", "*"]:
            k[ik] = k[ik-1]
            k[ik-1] = kk
    k = "".join(k)
    bkw_cont_ext[re.compile(k)] = v
bkw_high_ext = {}
for k, v in highlight_extenders.items():
    k = k.pattern[::-1]
    k = list(k)
    for ik, kk in enumerate(k):
        if kk in ["\\", "+", "*"]:
            k[ik] = k[ik-1]
            k[ik-1] = kk
    k = "".join(k)
    bkw_high_ext[re.compile(k)] = v



class omnivore_to_anki:
    def __init__(
        self,
        graph_dir: str,
        start_name: str,
        anki_deck_target: str,
        context_size: int = 2000,
        prepend_tag: str = "",
        append_tag: List[str] = "",
        n_article_to_process: int = -1,
        n_cards_to_create: int = -1,
        recent_article_fist: bool = True,
        unhighlight_others: bool = False,
        overwrite_flashcard_page: bool = False,
        only_process_TODO_highlight_blocks: bool = True,
        article_name_as_tag: bool = True,
        create_cards_if_no_content: bool = True,
        debug: bool = False
            ):
        """
        parameters:
        ----------
        graph_dir
            path to your logseq dir

        start_name: str
            the common beginning of the name of the files created by omnivore
        anki_deck_target: str
            name of the anki deck to send the cards to
        context_size
            number of characters to take around each highlight
        prepend_tag: str, default ""
            if a string, will be used to specify a parent tag to
            any tag specified in the card
        append_tag: list, default ""
            list of tags to add to each new cloze. This will not be
            prepended by prepen_tag
        n_article_to_process: int, default -1
            Only process that many articles. Useful to handle a backlog.
            -1 to disable
        n_cards_to_create: int, default -1
            stops when it has created at least this many cards.
            -1 to disable
        recent_article_fist: bool, default True

         unhighlight_others: bool, default False
            if True, remove highlight '==' around highlights when creating
            the cloze
        overwrite_flashcard_page: bool, default False
            wether to allow overwriting any ___flashcards for the article
            if present
        only_process_TODO_highlight_blocks: bool, default True
        article_name_as_tag: bool, default True
            if True the name of the article will be appended as tag
        create_cards_if_no_content: True
            if no content is found, will try to download a PDF if a link
            is found. If something fails during parsing and this is True
            will proceed to create flashcards, otherwise will skip this article.

         debug: bool, default False
            currently useless
        """
        assert Path(graph_dir).exists(), f"Dir not found: {graph_dir}"

        self.csize = context_size
        self.debug = debug
        self.unhighlight_others = unhighlight_others

        self.anki_deck_target = anki_deck_target.replace("::", "/")
        if not isinstance(append_tag, list):
            append_tag = [append_tag]
        self.append_tag = append_tag
        if prepend_tag:
            self.prepend_tag = "::".join(prepend_tag.split("::")) + "::"
        else:
            self.prepend_tag = ""
        assert isinstance(overwrite_flashcard_page, bool), "overwrite_flashcard_page must be a bool"
        self.overwrite_flashcard_page = overwrite_flashcard_page
        assert isinstance(only_process_TODO_highlight_blocks, bool), "only_process_TODO_highlight_blocks must be a bool"
        self.only_process_TODO_highlight_blocks = only_process_TODO_highlight_blocks
        assert isinstance(article_name_as_tag, bool), "article_name_as_tag must be a bool"
        self.article_name_as_tag = article_name_as_tag
        assert isinstance(create_cards_if_no_content, bool), "create_cards_if_no_content must be a bool"
        self.create_cards_if_no_content = create_cards_if_no_content

        # get list of files to check
        files = [f
                 for f in (Path(graph_dir) / "pages").iterdir()
                 if f.name.startswith(start_name)
                 and f.name.endswith(".md")
                 and not f.name.endswith("___flashcards.md")
                 ]

        assert files, (
                f"No files found in {graph_dir} with start_name {start_name}")

        files = sorted(
                files,
                key=lambda f: parse_date(f),
                reverse=True if recent_article_fist else False,
                )

        # filter only those that contain TODO
        files = [f for f in files if "- TODO " in f.read_text()]
        assert files, "No files contained TODO"

        self.p(f"Found {len(files)} omnivore articles to create anki cards for")

        n_created = 0
        for f_article in tqdm(files[:n_article_to_process], unit="article"):
            self.p(f"Processing {f_article}")
            n_new = self.parse_one_article(f_article)
            n_created += n_new
            if n_cards_to_create != -1:
                if n_created > n_cards_to_create:
                    self.p(f"Done because of number of new cards reached threshold.")
                    break
        self.p(f"Number of new cards: {n_created}")


    def parse_one_article(self, f_article: Path) -> int:
        article = None
        empty_article = False  # True if pdf parsing fails
        site = None
        article_name = None
        article_candidates = {}

        article_properties = {}

        parsed = LogseqMarkdownParser.parse_file(f_article, verbose=False)
        assert len(parsed.blocks) > 4

        page_prop = parsed.page_properties
        if "labels" in page_prop:
            page_labels = [self.parse_label(lab) for lab in page_prop["labels"].split(",")]
        else:
            page_labels = []

        n_highlight_blocks = 0
        assert len(set(b.UUID for b in parsed.blocks)) == len(parsed.blocks), (
                "Some blocks have non unique UUID")
        df = pd.DataFrame(index=[])

        for ib, block in enumerate(tqdm(parsed.blocks, unit="block")):
            # find the block containing the article
            if "date-saved" in block.properties and not article_properties:
                article_properties.update(block.properties)
                continue
            if block.content.lstrip().startswith("- ### Highlights"):
                continue
            if block.content.startswith("\t- ### Content"):
                if article is None and not empty_article:
                    assert not empty_article
                    assert article is None
                    article = parsed.blocks[ib+1]
                    try:
                        art_cont = self.parse_block_content(article)
                        assert art_cont != "### Highlights"
                    except Exception as err:
                        article = None
                        # no content means it's a PDF
                        self.p(
                            f"No article content for {f_article}. "
                            "Treading as  PDF.")
                        site = article_properties["site"].strip()
                        if site.startswith("[") and "](" in site:
                            article_name = site.split("](")[0][1:]
                        else:
                            article_name = site
                        article_name = article_name.replace(" ", "_")
                        if len(article_name) > 50:
                            article_name = article_name[:50] + "…"
                        if not site.startswith("http"):
                            assert site.startswith("[") and site.endswith(")") and "](" in site, f"Unexpected site format: {site}"
                            site = site.split("](")[1][:-1]
                        assert site.startswith("http")
                        assert site is not None, (
                            f"No URL for PDF found in {f_article}")
                        # download and save the pdf
                        try:
                            pdf = download_pdf(site)
                            with tempfile.NamedTemporaryFile(
                                prefix=article_name,
                                suffix=".pdf",
                                delete=False) as temp_file:
                                temp_file.write(pdf)
                                temp_file.flush()
                            article_candidates = parse_pdf(temp_file.name, site)
                        except Exception as err:
                            self.p(
                                f"Failed to parse pdf:\n"
                                "URL: {URL}\n"
                                "Reason: {err}"
                                )
                            if self.create_cards_if_no_content:
                                self.p(f"Continuing with empty article.")
                                empty_article = True
                            else:
                                self.p("Ignoring this article")
                                return 0
                continue

            prop = block.properties

            # check that no anki cards were created already
            if "omnivore-type" in prop:
                assert prop["omnivore-type"] != "highlightcloze", (
                    f"Cloze already created?! {prop} for {block}")

            # highlight
            if (self.only_process_TODO_highlight_blocks and block.TODO_state == "TODO") or (not self.only_process_TODO_highlight_blocks):

                n_highlight_blocks += 1
                assert prop["omnivore-type"] == "highlight", (
                        f"Unexpected block properties: {prop}")
                assert block.indentation_level > 2, (
                    f"Unexpected block indentation: {prop.indentation_level}")

                # get content of highlight
                high = self.parse_block_content(block)

                # remove quot indent
                assert high.startswith("> "), (
                    f"Highlight should begin with '> ': '{high}'")
                high = high[2:].strip()
                assert high, "Empty highlight?"

                if article is None and not empty_article:
                    assert article_candidates
                    for k, v in article_candidates.items():
                        if high in v:
                            self.p(f"Best matching pdf parser: {k}")
                            art_cont = v
                            break
                    # high never found in f: compute best matching substring
                    if high not in v:
                        best_candidate = None
                        min_dist = inf
                        for k, v in article_candidates.items():
                            _, dist = match_highlight_to_corpus(
                                    query=high,
                                    corpus=v,
                                    n_jobs=4)
                            if dist < min_dist:
                                min_dist = dist
                                best_candidate = k
                        assert best_candidate
                        art_cont = article_candidates[best_candidate]
                                             #
                # add id property if missing
                if "id" not in block.properties:
                    block_hash = self.hash(art_cont, high)
                    block.set_property("id", block_hash)
                buid = block.properties["id"]

                # the id of the cloze block should be a hash that only
                # depends on the highlight and article
                df.loc[buid, "cloze_hash"] = self.hash(high, art_cont)

                matching_art_cont = dedent(art_cont).strip()
                if high not in art_cont and not empty_article:
                    if len(art_cont) >= 100_000:
                        self.p(
                            f"Article contains {len(art_cont)} "
                            "characters so it might be too hard to find "
                            "a substring for in the current "
                            "implemeentation. Open an issue.")
                    best_substring_match, min_distance = match_highlight_to_corpus(
                        query=high,
                        corpus=art_cont,
                        n_jobs=4)
                    ratio = lev.ratio(high, best_substring_match)
                    assert ratio > 0.92, f"Too low lev ratio after substring matching: {ratio:4f}"
                    matching_art_cont = art_cont.replace(best_substring_match, high, 1)
                assert high in matching_art_cont or empty_article, f"Highlight not part of article:\n{high}\nNot in:\n{art_cont}"

                # get block labels for use as tags
                if "labels" in prop:
                    df.loc[buid, "block_labels"] = json.dumps([
                        self.parse_label(lab)
                        for lab in prop["labels"].split(",")
                    ])
                else:
                    df.loc[buid, "block_labels"] = json.dumps([])

                # TODO check position of the highlight but for now it's
                # always stuck at 0
                # if str(prop["omnivore_highlightposition"]) != "0":
                    # breakpoint()

                if matching_art_cont.count(high) == 1:
                    # if present only once: proceed
                    ind = matching_art_cont.index(high)
                    before = matching_art_cont[max(0, ind-self.csize * 3 // 4):ind]
                    after = matching_art_cont[ind:ind+self.csize]
                    context = (before + after).strip()
                    context = self.extend_context(context, matching_art_cont)
                    assert context
                    assert high in context
                    assert len(context) / self.csize - 1 < 1.3

                    # add cloze
                    cloze = self.context_to_cloze(high, context)

                    # store position and cloze
                    df.loc[buid, "cloze"] = cloze

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

                        df.loc[buid, "cloze"] = cloze

                    # else: create one cloze for each and one card containing all those clozes
                    else:
                        # find ranges of each clozes
                        ranges = []
                        for p in positions:
                            ranges.append([max(0, p-self.csize//2)])
                            ranges[-1].append(p+self.csize)

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
                            context = self.extend_context(context, matching_art_cont)
                            clozes.append(self.context_to_cloze(high, context))
                        cloze = "\n\n".join(clozes)

                        df.loc[buid, "cloze"] = cloze

                elif empty_article:
                    cloze = self.context_to_cloze(high, high)
                    df.loc[buid, "cloze"] = cloze

                else:
                    raise ValueError(f"Highlight was not part of the article? {high}")

        assert article is not None or article_candidates or empty_article, (
            f"Failed to find article in blocks: {parsed.blocks}")
        assert len(df) == n_highlight_blocks

        # insert cloze as blocks in a new page
        newpage = LogseqMarkdownParser.classes.LogseqPage(content="", verbose=False)
        newpage.set_property("omnivore-type", "flashcard_page")
        done = []
        for buid, row in df.iterrows():
            cloze = row["cloze"]
            for ib, block in enumerate(parsed.blocks):
                if block.UUID == buid:
                    break
            assert block.UUID == buid

            # turn the cloze into a block
            cont = f"- {cloze.strip()}"
            cloze_block = LogseqMarkdownParser.classes.LogseqBlock(cont, verbose=False)
            cloze_block.indentation_level = 0
            cloze_block.set_property("omnivore-type", "highlightcloze")
            cloze_block.set_property("omnivore-clozedate", str(datetime.today()))
            cloze_block.set_property("omnivore-clozeparentuuid", buid)
            cloze_block.set_property("id", df.loc[buid, "cloze_hash"])
            cloze_block.set_property("deck", self.anki_deck_target)
            cloze_block.set_property("parent", f"#{buid}")

            if self.article_name_as_tag:
                if "tags" in block.properties:
                    tags = block.properties["tags"].split(",")
                else:
                    tags = []
                assert article_name, "failed to parse article name"
                tags += [article_name]
                cloze_block.set_property("tags", ",".join(tags))

            if self.prepend_tag:
                if "tags" in block.properties:
                    tags = [self.parse_label(lab) for lab in block.properties["tags"].split(",")]
                    tags = [self.prepend_tag + t for t in tags]
                else:
                    tags = []
                tags.extend([self.prepend_tag + pl for pl in page_labels])
                tags.extend([self.prepend_tag + pl for pl in json.loads(df.loc[buid, "block_labels"])])
                if tags:
                    cloze_block.set_property("tags", ",".join(tags))

            if self.append_tag:
                if "tags" in block.properties:
                    tags = block.properties["tags"].split(",")
                    tags += self.append_tag
                else:
                    tags = self.append_tag
                cloze_block.set_property("tags", ",".join(tags))

            # add the cloze as block in the newpage
            newpage.blocks.append(cloze_block)

            if self.only_process_TODO_highlight_blocks:
                assert parsed.blocks[ib].TODO_state == "TODO", "Expected a TODO highlight block"
                parsed.blocks[ib].TODO_state = "DONE"

        # create new file
        self.p(f"Saving as {f_article.stem}___flashcards.md")
        newpage.export_to(
            f_article.parent / (f_article.stem + "___flashcards.md"),
            overwrite=self.overwrite_flashcard_page)
        if parsed.content != f_article.read_text():
            parsed.export_to(f_article, overwrite=True)
        return len(df)

    def parse_block_content(self, block):
        cont = block.content
        prop = block.properties
        for k, v in prop.items():
            cont = cont.replace(f"{k}:: {v}", "")
        if block.TODO_state:
            cont = cont.replace(block.TODO_state, "")
        cont = cont.replace("- ", "", 1)
        cont = cont.strip()

        # highlight fix
        cont = cont.replace("==!==", "!")
        cont = cont.replace("==:==", ":")
        cont = cont.replace("==.==", ".")
        cont = cont.replace("== ==", " ")

        if self.unhighlight_others:
            cont = cont.replace("==", "").strip()
        if cont == "-":
            raise Exception("Empty block")
        return cont

    def context_to_cloze(self, highlight, context):
        assert highlight in context

        before, after = context.split(highlight)
        for sep, tol in highlight_extenders.items():
            match = re.search(sep, after[:tol])
            if match:
                highlight = highlight + after[:match.end()]
                break

        before = before[::-1]
        for sep, tol in bkw_high_ext.items():
            match = re.search(sep, before[:tol])
            if match:
                highlight = before[:match.end()][::-1] + highlight
                break
        before = before[::-1]

        cloze = "…" + before + " == {{c1 " + highlight + " }} == " + after + "…"

        return cloze

    def extend_context(self, context: str, article: str) -> str:
        o_context = context
        assert context in article

        before, after = article.split(context)
        for sep, tol in context_extenders.items():
            match = re.search(sep, after[:tol])
            if match:
                context = context + after[:match.end()]
                break

        before = before[::-1].rstrip()
        for sep, tol in bkw_cont_ext.items():
            match = re.search(sep, before[:tol])
            if match:
                context = before[:match.end()][::-1] + context
                break
        before = before[::-1].lstrip()

        assert len(context) >= len(o_context)
        assert len(context) <= len(article)

        return context

    def hash(self, *args: List[str]) -> str:
        temp = args[0]
        for new in args[1:]:
            temp += new
        return str(
                uuid.uuid3(
                    uuid.NAMESPACE_URL,
                    temp)
        )

    def parse_label(self, label: str) -> str:
        label = label.replace("[", "").replace("]", "").replace("#", "").strip()
        assert label
        return label

    def p(self, text: str) -> str:
        "simple printer"
        tqdm.write(text)
        return text


def parse_date(path: Path) -> datetime:
    "return the date property of a logseq page"
    cont = path.read_text()
    s = cont.split("date-saved:: ")[1].split("]]")[0][2:]
    date = datetime.strptime(s, "%d-%m-%Y")
    return date


@mem.cache(ignore=["n_jobs"])
def match_highlight_to_corpus(
        query: str,
        corpus: str,
        case_sensitive: bool = True,
        step_factor: int = 128,
        favour_smallest: bool = False,
        n_jobs: int = -1,
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
    - n_jobs: int
        number of jobs to use for multithreading. 1 to disable

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
    dists = Parallel(
        backend="threading",
        n_jobs=n_jobs,
    )(delayed(lev.distance)(ngram, query) for ngram in corpus_ngrams)
    for idx, ngram in enumerate(corpus_ngrams):
        ngram_dist = dists[idx]
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
    def ld_set(ngram_set, query):
        dists = []
        for ngram in ngram_set:
            dists.append(lev.distance(ngram, query))
        return dists
    dist_list = Parallel(
        backend="threading",
        n_jobs=n_jobs,
    )(delayed(ld_set)(ngram_set, query) for ngram_set in narrowed_corpus_ngrams)
    for ing, ngram_set in enumerate(narrowed_corpus_ngrams):
        for iing, ngram in enumerate(ngram_set):
            ngram_dist = dist_list[ing][iing]
            if ngram_dist < min_dist:
                min_dist = ngram_dist
                closest_match = ngram

    return closest_match, min_dist

@mem.cache()
def download_pdf(url):
    "cached call to download a pdf from a url"
    response = requests.get(url)
    if str(response.status_code) != "200":
        raise Exception(f"Unexpected status code: {response.status_code}")
    filetype = magic.from_buffer(response.content)
    if "pdf" not in filetype.lower():
        raise Exception("Downloaded file is not a PDF but {filetype}")
    return response.content

@mem.cache()
def parse_pdf(path, url):
    loaded_docs = {}
    loaders = {
        "pdftotext": None,  # optional support
        "PDFMiner": PDFMinerLoader,
        "PyPDFLoader": PyPDFLoader,
        "Unstructured_elements_hires": partial(
            UnstructuredPDFLoader,
            mode="elements",
            strategy="hi_res",
            post_processors=[clean_extra_whitespace],
            infer_table_structure=True,
            # languages=["fr"],
        ),
        "Unstructured_elements_fast": partial(
            UnstructuredPDFLoader,
            mode="elements",
            strategy="fast",
            post_processors=[clean_extra_whitespace],
            infer_table_structure=True,
            # languages=["fr"],
        ),
        "Unstructured_hires": partial(
            UnstructuredPDFLoader,
            strategy="hi_res",
            post_processors=[clean_extra_whitespace],
            infer_table_structure=True,
            # languages=["fr"],
        ),
        "Unstructured_fast": partial(
            UnstructuredPDFLoader,
            strategy="fast",
            post_processors=[clean_extra_whitespace],
            infer_table_structure=True,
            # languages=["fr"],
        ),
        "PyPDFium2": PyPDFium2Loader,
        "PyMuPDF": PyMuPDFLoader,
        "PdfPlumber": PDFPlumberLoader,
        "online": OnlinePDFLoader,
    }
    # pdftotext is kinda weird to install on windows so support it
    # only if it's correctly imported
    if "pdftotext" in globals():
        loaders["pdftotext"] = pdftotext_loader_class
    else:
        del loaders["pdftotext"]

    # using language detection to keep the parsing with the highest lang
    # probability
    for loader_name, loader_func in loaders.items():
        try:
            print(f"Trying to parse {path} using {loader_name}")

            if loader_name == "online":
                loader = loader_func(url)
            else:
                loader = loader_func(path)
            content = loader.load()

            if "Unstructured" in loader_name:
                content = "\n".join([d.page_content.strip() for d in content])
                # remove empty lines. frequent in pdfs
                content = re.sub(emptyline_regex, "", content)
                content = re.sub(emptyline2_regex, "\n", content)
                content = re.sub(linebreak_before_letter, r"\1", content)

            temp = ""
            if isinstance(content, list):
                for cont in content:
                    if isinstance(cont, str):
                        temp += cont
                    elif hasattr(cont, "page_content"):
                        temp += cont.page_content
                    else:
                        raise ValueError(type(cont))
            content = temp.strip()

            assert isinstance(content, str), f"content is not string but {type(content)}"

            assert content, "Empty content after parsing"

            loaded_docs[loader_name] = content
            print("  OK")

        except Exception as err:
            print(f"Error when parsing '{path}' with {loader_name}: {err}")

    assert loaded_docs, f"No parser successfuly parsed the file"
    return loaded_docs



if __name__ == "__main__":
    fire.Fire(omnivore_to_anki)
