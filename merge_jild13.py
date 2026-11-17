#!/usr/bin/env python3
"""Merge Jild 13 tashreeh chunks into jild-13.json.

Re-runnable: reads every jild-13-chunk-*.json listed in the manifest,
merges in chunk order, validates (unique ids, page coverage vs manifest,
no empty jawab), writes jild-13.json, and updates the manifest statuses.

SPECIAL CASES (coordinator instructions, verified on disk by the parent):
4 combine cases are ONE mas'ala split across chunks and must be
COMBINED into a single item, NOT renamed by the duplicate-id rule.
After combining all 4 cases, the merged file has 966 items (974 - 8)
covering 580 unique pages. Combine rules (parts ordered by min page;
sawal from the FIRST part; jawab = all parts concatenated in page
order; pages = UNION of all parts' pages; notes = all parts' notes):
  masala 11:  02 pp. 197-199 + 03 pp. 200-201 (SAME id twice).
              Pages [197, 198, 199, 200, 201].
  masala 94:  04 'jild13-masala-94' p. 323 + 05 'jild13-p325' p. 325
              (DIFFERENT ids, same mas'ala). Pages [323, 325]
              (p. 324 is a source gap).
  masala 168: 06 pp. 445-448 + 07 pp. 449-451 (SAME id twice).
              Discard 07's empty sawal (Jild 11 masala-16 rule).
  masala 214: 08 'jild13-masala-214' pp. 511-562 + 09's five sections
              'jild13-p563' pp. 563-564, 'jild13-p564' pp. 564-566,
              'jild13-p566' pp. 566-569, 'jild13-p569' pp. 569-571,
              'jild13-p571' pp. 571-574 — a SIX-way combine.
              Pages = UNION [511-574] (the five sections' page ranges
              overlap each other, so union, never sum).
For every combined item: pages = union of all parts' pages,
start_page = min, notes = all parts' notes combined.

Distinct items that merely look similar are NOT combined — they already
have distinct ids and stay separate: the printed number 92 occurs twice
as two different masail (chunk 04's pp. 321-322 keeps plain
'jild13-masala-92'; chunk 05's pp. 327-328 is already renamed
'jild13-p327').

PLANNING NOTE: p. 200 was in NO chunk's planned range (chunk 02 ended
at 199, chunk 03 was planned to start at 201); chunk 03 caught it and
included it in masala-11. The manifest already records chunk 03's
start_page as 200, so the coverage check below uses the manifest as
written and expects chunk 03 to start at 200.

Duplicate-id rule (Jild 4 precedent) still applies to any OTHER
duplicate: earliest keeps the plain id, later ones get "-p<startpage>".
"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))

# result id -> list of source ids, in page order.
COMBINES = {
    'jild13-masala-11':  ['jild13-masala-11', 'jild13-masala-11'],
    'jild13-masala-94':  ['jild13-masala-94', 'jild13-p325'],
    'jild13-masala-168': ['jild13-masala-168', 'jild13-masala-168'],
    'jild13-masala-214': ['jild13-masala-214', 'jild13-p563', 'jild13-p564',
                          'jild13-p566', 'jild13-p569', 'jild13-p571'],
}


def combine_parts(result_id, parts):
    parts = sorted(parts, key=lambda it: min(it['pages']))
    first = parts[0]
    combined = {
        'id': result_id,
        'title': first.get('title') or '',
        'volume_id': 56,
        'pages': sorted(set().union(*[set(p['pages']) for p in parts])),
        'start_page': min(min(p['pages']) for p in parts),
        'tashreeh_sawal': first.get('tashreeh_sawal', '') or '',
        'tashreeh_jawab': ''.join((p.get('tashreeh_jawab', '') or '') for p in parts),
        'notes': [n for p in parts for n in (p.get('notes') or [])],
    }
    return combined


def main():
    manifest = json.load(open(os.path.join(BASE, 'chunks-manifest-jild13.json')))
    all_items = []
    merged_chunks = []
    for entry in manifest['chunks']:
        nn = entry['chunk']
        if entry.get('status') == 'split-halves':
            print(f'chunk {nn}: split-halves placeholder — halves are separate entries, skipping')
            continue
        path = os.path.join(BASE, entry['file'])
        if not os.path.exists(path):
            print(f'chunk {nn}: not yet written')
            continue
        try:
            d = json.load(open(path, encoding='utf-8'))
        except json.JSONDecodeError as e:
            # File may still be streaming from its translator; skip it
            # for now instead of crashing the whole merge.
            print(f'chunk {nn}: not valid JSON yet ({e}) — skipping for now')
            continue
        items = d['masail']
        # Normalize: some translators omit start_page; derive it from pages.
        for it in items:
            if 'start_page' not in it:
                assert it.get('pages'), f'chunk {nn} item {it.get("id")} has no pages'
                it['start_page'] = it['pages'][0]
                print(f'chunk {nn}: derived start_page={it["start_page"]} for {it["id"]}')
            assert it['start_page'] == min(it['pages']), \
                f'chunk {nn} item {it["id"]}: start_page != first page'
        all_items.extend(items)
        merged_chunks.append(nn)
        entry['status'] = 'merged'
        print(f'chunk {nn}: {len(items)} items merged')
    print(f'items before combines: {len(all_items)}')
    # COMBINE the 4 cases (one mas'ala split across chunks).
    for result_id, source_ids in COMBINES.items():
        parts = []
        seen_source = []
        for sid in source_ids:
            if sid in seen_source:
                continue  # same id listed twice (masala-11, masala-168): collect both items at once
            seen_source.append(sid)
            hits = [it for it in all_items if it['id'] == sid]
            expected_n = source_ids.count(sid)
            assert len(hits) == expected_n, \
                f'expected exactly {expected_n} {sid} item(s) for {result_id}, found {len(hits)}'
            parts.extend(sorted(hits, key=lambda it: min(it['pages'])))
        combined = combine_parts(result_id, parts)
        assert combined['tashreeh_jawab'], f'{result_id}: combined jawab is empty!'
        assert combined['tashreeh_sawal'], f'{result_id}: combined sawal is empty!'
        assert combined['start_page'] == min(combined['pages']), f'{result_id}: start_page != min(pages)'
        remove_ids = set(source_ids)
        all_items = [it for it in all_items if it['id'] not in remove_ids]
        all_items.append(combined)
        print(f'COMBINED {result_id}: {len(parts)} parts, pages {combined["pages"][0]}-{combined["pages"][-1]} '
              f'({len(combined["pages"])} pages), sawal {len(combined["tashreeh_sawal"])} chars, '
              f'jawab {len(combined["tashreeh_jawab"])} chars, notes {len(combined["notes"])}')
    # de-duplicate any OTHER ids: earliest keeps plain id, later ones get -p<startpage>
    seen = {}
    for it in all_items:
        if it['id'] in seen:
            new_id = f"{it['id']}-p{it['start_page']}"
            print(f'DUPLICATE ID {it["id"]} (start {it["start_page"]}) -> renamed {new_id}')
            it['id'] = new_id
        seen[it['id']] = True
    ids = [it['id'] for it in all_items]
    assert len(ids) == len(set(ids)), f'STILL DUPLICATE IDS: {[i for i in ids if ids.count(i) > 1]}'
    empty = [it['id'] for it in all_items if not it.get('tashreeh_jawab')]
    assert not empty, f'EMPTY JAWAB: {empty}'
    pages = set()
    for it in all_items:
        pages.update(it['pages'])
    expected = set()
    for entry in manifest['chunks']:
        if entry['chunk'] in merged_chunks:
            expected.update(range(entry['start_page'], entry['end_page'] + 1))
            expected.difference_update(entry['missing_pages'])
    missing_covered = expected - pages
    extra = pages - expected
    print(f'total items: {len(all_items)} | pages covered: {len(pages)} | expected: {len(expected)}')
    print(f'uncovered expected pages: {sorted(missing_covered)}')
    print(f'extra pages (outside merged chunks): {sorted(extra)}')
    assert not missing_covered, 'pages missing from merged chunks!'
    assert not extra, 'pages outside merged chunks!'
    assert len(all_items) == 966, f'expected 966 items after combines, got {len(all_items)}'
    assert len(pages) == 580, f'expected 580 pages, got {len(pages)}'
    # sort by start_page for the final file
    all_items.sort(key=lambda it: it['start_page'])
    with open(os.path.join(BASE, 'jild-13.json'), 'w', encoding='utf-8') as f:
        json.dump({'masail': all_items}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(BASE, 'chunks-manifest-jild13.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f'WROTE jild-13.json: {len(all_items)} items, {len(pages)} pages, chunks merged: {merged_chunks}')


if __name__ == '__main__':
    main()
