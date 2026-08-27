#!/usr/bin/env python3

import base64
import json
import pathlib
import sys
import urllib.error
import urllib.request


def upload(url: str, fixture: pathlib.Path, root: pathlib.Path) -> int:
    payload = json.dumps({
        'file_name': str(fixture.relative_to(root)).replace('/', '_'),
        'file': base64.b64encode(fixture.read_bytes()).decode('ascii'),
    }).encode('utf-8')
    request = urllib.request.Request(
        url,
        data=payload,
        headers={'Content-Type': 'application/json'},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def main() -> int:
    if len(sys.argv) != 3:
        print(f'Usage: {sys.argv[0]} API_URL FIXTURE_DIRECTORY', file=sys.stderr)
        return 2

    api_url, fixture_directory = sys.argv[1:]
    fixture_root = pathlib.Path(fixture_directory)
    failures = []
    fixture_count = 0

    for fixture in sorted(fixture_root.rglob('*')):
        if not fixture.is_file():
            continue
        fixture_count += 1
        try:
            status = upload(api_url, fixture, fixture_root)
        except (OSError, urllib.error.URLError) as error:
            failures.append(f'{fixture}: request failed: {error}')
            continue

        if status >= 500:
            failures.append(f'{fixture}: service returned HTTP {status}')

    print(f'Uploaded {fixture_count} upstream MAT2 fixtures.')
    if failures:
        print('\n'.join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())