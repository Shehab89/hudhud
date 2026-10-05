# Adding posts by hand (accounts we cannot collect)

X cannot be read without a paid API plan (REQUIRES CONFIGURATION), and scraping X or using
mirror sites is not permitted. The platform therefore collects the X accounts of the public
figures in the registry **only when someone supplies their posts**. Nothing is fetched from X.

## How

1. Create a CSV file in `data/social-posts/` (GitHub: Add file, Create new file; any name
   ending in `.csv`, for example `2026-10-week1.csv`).
2. Paste one row per post, with this header:

```csv
source,url,posted_at,text,language
SOURCE_ID,https://x.com/HANDLE/status/POST_ID,2026-09-20T08:30:00Z,Text of the post,en
```

| column | meaning |
|---|---|
| `source` | the source id from [source-selection.csv](source-selection.csv) (column `source_id`) |
| `url` | the link to the post; its account must be one registered for that source |
| `posted_at` | the post's date and time (ISO 8601). Required: dates are never estimated |
| `text` | the post's text; only an excerpt (about 600 characters) is stored |
| `language` | optional, `ar` or `en` |

A JSON file with a list of objects with the same keys works too.

## What is checked

* The source must be a curated record of the registry.
* The URL must belong to one of that source's registered accounts (platform and handle), so a post
  cannot be filed under the wrong person. Posts from accounts that are not in the registry are rejected.
* Posts without a date, or dated in the future, are rejected. Each rejection is reported with its row
  and reason.
* Importing the same link again changes nothing; an edited text becomes a new version.

Imported posts are analysed like any other item and shown as **Social post**. They are a sample
chosen by whoever pastes them, not a complete record of the account, and they say nothing about
accuracy. Only add posts of public figures in their public role.

To test a file without storing anything: `hudhud import-posts FILE --dry-run`.
