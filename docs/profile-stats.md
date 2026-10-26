# Profile stats

The profile embeds committed SVG snapshots from `assets/`. Visitors load them
from GitHub without waiting for the Vercel stats service to generate a card.
The images share a paragraph so they sit side by side when space allows and
wrap naturally on mobile. The refresh gives both SVG canvases the same height,
preserving their original widths and text sizes rather than stretching the
language card. Their combined width is 767 pixels plus the space between them.
Each filename includes a hash of the SVG contents. The refresh updates the
README references in the same commit and retains older images for cached pages. New
data therefore gets a new image URL; identical data keeps its existing URL.
This prevents a cached six-language card from surviving a twelve-language update.

The language request uses the service's supported `langs_count=12` option with
`hide_progress=true`, which renders up to 12 languages in two columns. The
service obtains the language data from GitHub and ranks it by byte count by
default; no language names, rankings or values are added locally. If the service
finds fewer than 12 languages, the card shows only those available. See the
[upstream language-count documentation](https://github.com/anuraghazra/github-readme-stats#show-more-languages).

The original [API handler](https://github.com/anuraghazra/github-readme-stats/blob/master/api/top-langs.js)
passes `langs_count` through to the renderer, which sorts the data and limits
the displayed languages to that count (maximum 20). `hide_progress=true`
selects the compact two-column layout, whose default count is six only when
`langs_count` is omitted. The deployed account's
[fork renderer](https://github.com/Victorcorcos/github-readme-stats/blob/master/src/cards/top-languages-card.js)
supports the same options. Its
[fetcher](https://github.com/Victorcorcos/github-readme-stats/blob/master/src/fetchers/top-languages-fetcher.js)
queries GitHub GraphQL for owned, non-fork repositories and aggregates their
reported language bytes; it requests up to 100 repositories and ten languages
per repository. These are the source's coverage limits, not a fabricated list.

When the six-language display was reported after the update, remote `main`
and the profile's actual image URL both returned all 12 language entries.
The successful Actions run also retained all 12. The raw image URL advertised
`Cache-Control: max-age=300`; the old six-language image had used that same URL.
Stale caching is therefore consistent with the observed display, although the
old response could not be reproduced. Relative `?v=` cache-busting is unsuitable:
GitHub's `/raw/main/` redirect drops the query string. Content-based filenames
avoid that redirect behavior and make each README reference unambiguous.

Previously, both images used live Vercel endpoints through GitHub's Camo proxy.
During investigation, uncached responses took 4.2–6.3 seconds compared with
0.3–0.5 seconds for cached responses. Both returned valid SVGs with HTTP 200;
the intermittent broken response was not reproduced. This timing is consistent
with a cold generation/proxy timeout on the first visit. Serving snapshots
removes that dependency from page loads, regardless of the upstream failure.

The `Update profile stats` workflow refreshes both cards daily at 06:17 UTC,
when its implementation changes on `main`, or through **Run workflow** in
GitHub Actions. It uses the existing endpoints and display options, requires
only the automatic `GITHUB_TOKEN` with `contents: write`, and commits changed
cards together with their README references. GitHub Actions must be enabled and repository rules must allow
the bot to push to `main`.

The refresh retries network and validation failures three times. It checks the
MIME type, SVG structure, expected heading and statistics before replacing
either snapshot. This rejects HTML and HTTP-200 SVG error cards. If either
download fails, the workflow fails and the committed images remain available.
An upstream outage can therefore make the numbers stale without breaking them.

To refresh locally with Python 3 and no additional dependencies:

```sh
python3 -B -m unittest discover -s tests
python3 -B scripts/update_stats.py
```

References: [GitHub's Camo documentation](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/about-anonymized-urls)
and [GitHub Readme Stats reliability guidance](https://github.com/anuraghazra/github-readme-stats#deploy-on-your-own).
