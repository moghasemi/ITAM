# Iran administrative geography seed data

This directory contains the province and county JSON records used by ITAM's
`load_iran_geography` management command.

## Provenance

- Dataset: [list-of-cities-in-Iran](https://github.com/sajaddp/list-of-cities-in-Iran)
- Pinned upstream commit: `ace21bb251f96ced350bbc01541acffd71121feb`
- Source files: `dist/json/provinces.json` and `dist/json/counties.json`
- Source release documents administrative divisions through the end of Solar
  Hijri year 1404.
- Included records: 31 provinces and 484 counties.
- The upstream project is licensed under GNU GPL v3. See `LICENSE.txt`.
- This is a developer convenience dataset, not a legal authority. For legal or
  official use, verify the current divisions against Ministry of Interior /
  National Open Data Portal publications.

## Data semantics

A county (شهرستان) is not a city (شهر). This seed intentionally imports only
provinces and counties into ITAM's organizational hierarchy. It does not create
operational IT centers for every county. Centers remain separate records that
must be created for actual participating organizations.
