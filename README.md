# creator-store-scraper

Scrapes a 3D-model marketplace storefront into a ready-to-import Etsy listing
CSV, for reselling physical prints of licensed models.

```
$ python -m scrapers.creator_store --site myminifactory --creator STUDIO --out listings.csv

  1043 products visible ...
Resuming: 380 of 1043 items already done, 380 will be skipped. 663 remain.
  invalid (no images): https://www.myminifactory.com/object/...
  ...
Stopping: 10 consecutive items failed to parse. This is what rate limiting
looks like -- the server is returning its generic page instead of content.
Progress is saved; wait a while and rerun to continue from here.
```

That halt is the most important feature in the tool. See below.

## The problem

A creator storefront holds hundreds to thousands of models. Turning each into a
resale listing by hand — pull the title, the description, the images, rewrite
the copy for a physical product — takes 3–5 minutes, and there are 1,000+
products per creator.

Neither marketplace offers a usable public API for reading a storefront.
MyMiniFactory has an API for uploading to *its own* library, nothing for
reading someone's shop. So this is browser automation.

## Approach

**One parameterised scraper, not one script per creator.** The previous
incarnation had a separate script per creator, which meant five copies of every
bug and five places to fix each one. Site-specific selectors and URL patterns
live in small adapter classes; everything else is shared.

**Adapters take HTML text, not a driver.** `parse_product(html)` is a pure
function over a string. That one decision is why this repo has 97 tests: the
parsing, the URL extraction, the validation and all the copy rewriting are
tested against fixture markup with no browser and no network.

**It attaches to a Chrome you started yourself** rather than launching its own
driver, reusing your logged-in session. A fresh Selenium profile fails
immediately on anything requiring a login and trips bot detection on much else.

## The failure this is built around

On one ~1,100-product run, requests from roughly product 380 onward were
silently blocked. The server returned HTTP 200 with the site's generic landing
page instead of the product. The scraper kept going and wrote **700 rows of
plausible-looking garbage** that only revealed itself as missing images much
later, after the file had been imported.

Four countermeasures, all on by default:

1. **Every parsed product is validated.** No title or no images is a *failure*,
   not a row. A block page parses to an invalid product and is rejected.
2. **Sustained failure halts the run.** After N consecutive invalid parses
   (default 10), it stops, saves progress, and says plainly that this is what
   rate limiting looks like. Stopping early costs minutes; not stopping costs
   the run and the trust in its output.
3. **Randomised delay** between requests.
4. **Checkpoint every 10 products**, resuming skips completed IDs, and the skip
   count is stated on startup — a silent resume that skips 700 items looks
   exactly like a run that found nothing to do.

The final summary always reports the count of rows carrying images. **Success is
never reported without that number.**

## Three ways to get the URLs

All three produce the same artifact — a deduplicated URL list — so they are
interchangeable and stage 2 consumes any of them.

| Mode | When |
|---|---|
| **live scroll** | Normal case. Auto-scrolls until the product count *stops growing* — not a fixed count. The old version scrolled five times and silently returned zero products. |
| **saved HTML** | The reliable fallback. Save storefront pages as "Complete Webpage", point at the folder, IDs come out by regex. |
| **open tabs** | Enumerates the attached Chrome's tabs. Useful for a hand-picked selection across several creators in one pass. |

When live mode finds zero URLs it **dumps every anchor href on the page** rather
than just erroring. That output is the difference between a ten-minute selector
fix and an hour of guessing.

## Rewriting the copy

Source listings sell a *digital file*. These listings sell a physical printed
object, so the description has to be rewritten, and some of it is policy risk
rather than just wrong:

- STL/mesh/file-format/instant-download language and commercial licence lines
  are removed.
- **All external links go.** Etsy prohibits linking to outside sales channels;
  a leftover Patreon link risks the listing, not just its quality.
- A **config-supplied IP denylist** is applied to titles, descriptions and tags.
  Some rightsholders in this space pursue takedowns against proxy and lookalike
  terms rather than only their own trademarks. **That list is never committed** —
  publishing it would publish a map of which terms attract enforcement. Ship an
  empty file; the tool runs fine without one.
- Optional phrase-level translation from a config glossary, for creators
  publishing in German. Deliberately not machine translation: output goes
  straight onto a live listing, and a deterministic substitution table produces
  a diff a human can approve.

**Every removal is reported per listing**, because these are the edits you get
asked to justify.

## Usage

```bash
pip install -r requirements.txt
python -m pytest                      # 97 tests, no browser needed
```

Start Chrome with the debug port open, once:

```bash
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"
```

Then:

```bash
python -m scrapers.creator_store --site myminifactory --creator STUDIO --out out.csv
python -m scrapers.creator_store --site cults3d --from-folder ./saved --out out.csv
python -m scrapers.creator_store --site myminifactory --from-tabs --out out.csv
```

Useful flags: `--limit N`, `--denylist path`, `--delay-min/--delay-max`,
`--halt-after N`, `--price`.

Images are referenced as URLs and both Etsy and Shopify fetch them, so
downloading is only needed for archival or a platform requiring uploads:

```bash
python -m scrapers.download_images --csv out.csv --out images/
```

That skips files already on disk — the original run died at 171 of 224 and
resuming mattered.

## Output

A Vela CSV (Etsy's bulk-listing format), plus `post_import_todo.txt` naming any
listings needing a Vela Profile applied by hand — custom buyer-input options
cannot be set through the CSV at all, and dropping that information silently
would leave the listings quietly incomplete.

SKUs are `{CREATOR}-{slug}`, with the slug derived from the **cleaned** title. A
SKU built from the original while the listing shows the rewritten name is a
mismatch that surfaces much later, in whichever system joins on SKU.

## Notes and limitations

**Provenance.** This tool ran in production against creator catalogues of 1,000+
products; the lessons above are all paid for. That original source was lost and
this repository is a rebuild from the specification those runs produced — so the
approach is proven and the rules are real, while the rebuilt code is verified
against fixtures rather than re-run against a live storefront. Treat a first run
as a first run: use `--limit`, check the image count, then go wide.

**The browser layer is untested by design.** `common/browser.py` and the
acquisition loop need a live Chrome. They are kept thin precisely so the logic
around them — parsing, validation, the halt, the copy rewriting — is testable
without one. Selenium is not in `requirements.txt` for the tested paths; install
it to run the scraper itself.

**`common/` is vendored.** These modules also live in a broader toolkit repo.
Duplicated deliberately so this repo stands alone and can be cloned and run
without pulling an unrelated project.

**Respect the sites.** Delays default to 1.5–4s and the halt exists partly to
stop the tool being a nuisance. Scrape catalogues you have licensed.

## Licence

MIT — see [LICENSE](LICENSE).
