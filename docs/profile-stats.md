# Profile stats

The profile embeds committed SVG snapshots from `assets/`. Visitors load them
from GitHub without waiting for the Vercel stats service to generate a card.
The images share a paragraph so they sit side by side when space allows and
wrap naturally on mobile. The refresh gives both SVG canvases the same height,
preserving their original widths and text sizes rather than stretching the
language card. Their combined width is 767 pixels plus the space between them.

Previously, both images used live Vercel endpoints through GitHub's Camo proxy.
During investigation, uncached responses took 4.2–6.3 seconds compared with
0.3–0.5 seconds for cached responses. Both returned valid SVGs with HTTP 200;
the intermittent broken response was not reproduced. This timing is consistent
with a cold generation/proxy timeout on the first visit. Serving snapshots
removes that dependency from page loads, regardless of the upstream failure.

The `Update profile stats` workflow refreshes both cards daily at 06:17 UTC,
when its implementation changes on `main`, or through **Run workflow** in
GitHub Actions. It uses the existing endpoints and display options, requires
only the automatic `GITHUB_TOKEN` with `contents: write`, and commits only
changed cards. GitHub Actions must be enabled and repository rules must allow
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
