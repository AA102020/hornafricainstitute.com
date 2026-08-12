# Horn of Africa Institute Publication Policy

This file records the governing publication-identification and catalogue rules for Horn of Africa Institute (HAI) publications.

## 1. Publication series and identifiers

HAI uses five fixed publication-series prefixes:

| Series | Identifier format |
| --- | --- |
| Research Papers | `HAI-RP-YYYY-##` |
| Working Papers | `HAI-WP-YYYY-##` |
| Policy Briefs | `HAI-PB-YYYY-##` |
| Commentary | `HAI-CM-YYYY-##` |
| Special Reports | `HAI-SR-YYYY-##` |

The series prefix is mandatory and must correspond to the publication's assigned series.

## 2. Authority to assign year and number

The publisher assigns the `YYYY-##` portion of every publication identifier.

The repository must not infer, generate, reserve, or require the next chronological or numerical identifier unless the publisher explicitly instructs it to do so for a specific publication.

Publication numbers do not need to be contiguous. Gaps are permitted. Numerical order does not establish publication chronology.

Historical publications restored from earlier HAI websites, archives, or publication records may retain their original year and sequence number. A later restoration date does not require reassignment to the current year or the next available number.

## 3. Identifier validation

Automation may validate an identifier supplied by the publisher. Validation is limited to:

1. the identifier uses the correct series prefix;
2. the year contains four digits;
3. the sequence contains two digits; and
4. the complete identifier is not already assigned to another publication.

Automation must not reject an identifier because its year predates the current website, its sequence is noncontiguous, another publication has a higher or lower number, or the identifier does not represent the next apparent number in a series.

## 4. Authoritative publication registry

`data/publications.json` is the authoritative machine-readable publication registry.

Each publication appears once in the registry. Published records contain the assigned identifier, series, title, author, publication date, landing-page path, PDF path, and publication status. Additional fields such as subtitles may be used where appropriate.

Items listed on the website that have not been assigned publication metadata may remain in the registry with a `locked` status and null identifier, author, publication date, landing-page path, and PDF path.

## 5. Public catalogue

`publications.html` is the public presentation layer. Its publication records must remain consistent with `data/publications.json`.

Publication changes should use the targeted publication-management tooling in `scripts/manage_publications.py` so that only the requested series block is modified and registry/catalogue changes are validated together.

## 6. Publication status

The repository recognizes two catalogue states:

- `locked`: listed on the Publications page and not publicly available;
- `published`: publicly available with the required publication metadata and publication files.

A publication moves from `locked` to `published` only when the publisher authorizes publication and supplies or approves the required metadata and files.

## 7. Historical restoration

Historical publications may be added or restored at any time. Restoration must preserve the publication's established identifier when one is known and approved by the publisher. Historical insertion must not renumber existing publications or trigger automatic renumbering of any series.

## 8. Technical safeguards

Repository validation should enforce structural correctness, registry/catalogue consistency, valid series prefixes, identifier syntax, uniqueness, required published metadata, and required local publication assets.

Repository validation must not impose contiguous numbering, chronological numbering, automatic sequence assignment, or automatic year assignment.

## 9. Editorial authority

Publication-series assignment, title, author attribution, publication date, year-number assignment, historical identifier restoration, and the decision to publish remain editorial decisions of the Horn of Africa Institute publisher. Repository automation implements and validates those decisions; it does not replace them.
