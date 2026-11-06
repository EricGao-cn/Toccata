#!/usr/bin/env python3
"""Guard personal Actions builds and upload verified artifacts as drafts only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

import publish
import release


def context(tag):
    if not re.fullmatch('personal-v' + publish.VERSION, tag):
        raise release.ReleaseError('Use a canonical personal-vX.Y.Z stable tag')
    if (os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('GITHUB_REPOSITORY') != publish.REPOSITORY
            or os.environ.get('GITHUB_SERVER_URL') != 'https://github.com'):
        raise release.ReleaseError('This entry point only runs in the personal GitHub repository Actions')
    event, ref = os.environ.get('GITHUB_EVENT_NAME'), os.environ.get('GITHUB_REF')
    event_sha = os.environ.get('GITHUB_SHA', '')
    if not re.fullmatch(r'[0-9a-f]{40}', event_sha):
        raise release.ReleaseError('Missing workflow source commit')
    if event == 'push':
        payload = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
        if (not isinstance(payload, dict) or ref != 'refs/tags/' + tag
                or payload.get('created') is not True or payload.get('deleted') is not False
                or payload.get('forced') is not False):
            raise release.ReleaseError('Only a new personal tag push is allowed; never move or delete release tags')
    elif event == 'workflow_dispatch':
        if ref != 'refs/heads/codex/personal':
            raise release.ReleaseError('Manually run this workflow from codex/personal')
    else:
        raise release.ReleaseError('Only personal tag pushes or manual runs are supported')
    return event, event_sha


def resolve(tag):
    """Resolve a tag from the accepted mainline before checking out any tag code."""
    event, event_sha = context(tag)
    personal = release.git('rev-parse', '--verify', 'refs/remotes/origin/codex/personal^{commit}')
    if release.git('rev-parse', 'HEAD') != personal or release.git('status', '--porcelain'):
        raise release.ReleaseError('Resolve release tags from a clean fetched codex/personal checkout')
    tag_object = release.git('rev-parse', '--verify', f'refs/tags/{tag}^{{tag}}')
    header = release.git('cat-file', '-p', tag_object).splitlines()
    if len(header) < 2 or header[1] != 'type commit':
        raise release.ReleaseError('The annotated personal tag must point directly to a commit')
    commit = release.git('rev-parse', '--verify', f'refs/tags/{tag}^{{commit}}')
    if event == 'push' and event_sha != commit:
        raise release.ReleaseError('Pushed tag and workflow source commit differ')
    for source in (commit, event_sha):
        subprocess.run(['git', '-C', str(release.ROOT), 'merge-base', '--is-ancestor', source, personal], check=True)
    return {'tag': tag, 'commit': commit, 'tag_object': tag_object}


def checkout(tag):
    event, event_sha = context(tag)
    settings = release.config()
    if tag != 'personal-v' + settings['version']:
        raise release.ReleaseError('Tag must match the checked-out personal release configuration')
    # A full checkout fetches origin/codex/personal, even when HEAD is detached at a tag.
    personal = release.git('rev-parse', '--verify', 'refs/remotes/origin/codex/personal^{commit}')
    head = release.git('rev-parse', 'HEAD')
    if event == 'push' and event_sha != head:
        raise release.ReleaseError('Pushed tag and workflow source commit differ')
    for commit in (head, event_sha):
        subprocess.run(['git', '-C', str(release.ROOT), 'merge-base', '--is-ancestor', commit, personal], check=True)
    existing = subprocess.run(['git', '-C', str(release.ROOT), 'show-ref', '--verify', '--quiet',
                               'refs/heads/codex/personal'], check=False)
    if existing.returncode == 1:
        subprocess.run(['git', '-C', str(release.ROOT), 'branch', '--no-track', 'codex/personal', personal], check=True)
    elif existing.returncode or release.git('rev-parse', 'codex/personal') != personal:
        raise release.ReleaseError('Local personal branch differs from the fetched accepted mainline')
    commit, tag_object = release.release_provenance(settings, tag)
    # Reject nested annotated tags as well as lightweight tags: the remote check uses the same policy.
    if release.git('cat-file', '-p', tag_object).splitlines()[1] != 'type commit':
        raise release.ReleaseError('The annotated personal tag must point directly to a commit')
    notes = release.ROOT / 'docs/releases' / (tag + '.md')
    if not notes.is_file() or not notes.read_text().strip():
        raise release.ReleaseError('Commit nonempty release notes named docs/releases/<personal-tag>.md')
    return {'tag': tag, 'commit': commit, 'tag_object': tag_object}


def verify_bundle(bundle, tag, commit, tag_object, archive_sha256=None):
    expected = checkout(tag)
    if expected != {'tag': tag, 'commit': commit, 'tag_object': tag_object}:
        raise release.ReleaseError('Checkout differs from the verified build job provenance')
    metadata = publish.verify_bundle(bundle)
    archive = f'Toccata-Personal-{tag.removeprefix("personal-v")}-arm64.dmg'
    if (any(metadata.get(key) != value for key, value in expected.items())
            or metadata['archive'] != archive):
        raise release.ReleaseError('Actions requires the expected personal stable arm64 DMG')
    digest = metadata['files'][archive]
    if archive_sha256 is not None and digest != archive_sha256:
        raise release.ReleaseError('Downloaded DMG differs from the verified build job SHA-256')
    notes = release.ROOT / 'docs/releases' / (tag + '.md')
    if (Path(bundle) / 'RELEASE.md').read_text() != notes.read_text():
        raise release.ReleaseError('Artifact release notes differ from the committed tagged source')
    return metadata


def check_uploaded_draft(metadata):
    # The by-tag REST endpoint is for published releases. Find drafts with the
    # authenticated paginated listing, then address the exact numeric release ID.
    matches = [item for item in publish.remote_releases() if item['tag_name'] == metadata['tag']]
    if len(matches) != 1 or type(matches[0].get('id')) is not int or matches[0]['id'] <= 0:
        raise release.ReleaseError('Cannot identify one uploaded draft; inspect GitHub before retrying')
    release_id = matches[0]['id']
    draft = publish.github(f'repos/{publish.REPOSITORY}/releases/{release_id}')
    assets = draft.get('assets', []) if isinstance(draft, dict) else []
    names = {metadata['archive'], metadata['archive'] + '.sha256', 'release.json', 'release.json.sha256'}
    url_prefix = 'https://github.com/' + publish.REPOSITORY + '/releases/'
    if (not isinstance(draft, dict) or type(draft.get('id')) is not int or draft['id'] != release_id
            or draft.get('draft') is not True or draft.get('prerelease') is not False or draft.get('published_at') is not None
            or draft.get('tag_name') != metadata['tag'] or not isinstance(assets, list) or len(assets) != len(names)
            or any(not isinstance(asset, dict) or not isinstance(asset.get('name'), str) for asset in assets)
            or {asset.get('name') for asset in assets} != names
            or any(asset.get('state') != 'uploaded' or asset.get('digest') != 'sha256:' + metadata['files'][asset['name']]
                   for asset in assets)
            or not isinstance(draft.get('body'), str)
            or hashlib.sha256(draft['body'].encode()).hexdigest() != metadata['files']['RELEASE.md']
            or not isinstance(draft.get('html_url'), str) or not draft['html_url'].startswith(url_prefix)):
        raise release.ReleaseError('Uploaded draft verification failed; inspect the draft before retrying; no cleanup or publication attempted')
    publish.check_remote_tag(metadata)
    return draft['html_url']


def outputs(values):
    path = os.environ.get('GITHUB_OUTPUT')
    if path:
        # Only validated canonical tags and hex digests reach workflow outputs.
        with Path(path).open('a') as stream:
            for key in ('tag', 'commit', 'tag_object', 'archive_sha256'):
                if key in values:
                    stream.write(key + '=' + values[key] + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    source = commands.add_parser('resolve')
    source.add_argument('--tag', required=True)
    check = commands.add_parser('check')
    check.add_argument('--tag', required=True)
    check.add_argument('--commit', required=True)
    check.add_argument('--tag-object', required=True)
    for name in ('verify', 'draft'):
        command = commands.add_parser(name)
        command.add_argument('--bundle', type=Path, required=True)
        command.add_argument('--tag', required=True)
        command.add_argument('--commit', required=True)
        command.add_argument('--tag-object', required=True)
        command.add_argument('--archive-sha256', required=name == 'draft')
        if name == 'draft':
            command.add_argument('--execute', action='store_true')
            command.add_argument('--ack-upload', action='store_true')
    args = parser.parse_args()
    try:
        if args.command in ('resolve', 'check'):
            result = resolve(args.tag) if args.command == 'resolve' else checkout(args.tag)
            if args.command == 'check' and result != {'tag': args.tag, 'commit': args.commit, 'tag_object': args.tag_object}:
                raise release.ReleaseError('Tag changed after resolution; refusing to build a different release')
            publish.check_remote(result)
            outputs(result)
        else:
            if args.command == 'draft' and args.execute and not args.ack_upload:
                raise release.ReleaseError('Draft upload requires --execute --ack-upload')
            metadata = verify_bundle(args.bundle, args.tag, args.commit, args.tag_object, args.archive_sha256)
            if args.command == 'draft' and args.execute:
                try:
                    result = publish.create_draft(args.bundle, expected_metadata=metadata)
                    result['draft_url'] = check_uploaded_draft(metadata)
                except (release.ReleaseError, publish.maintenance.MaintenanceError, OSError, ValueError, KeyError,
                        subprocess.SubprocessError) as error:
                    raise release.ReleaseError('Draft upload/readback did not complete. A draft may exist; inspect '
                        'https://github.com/' + publish.REPOSITORY + '/releases before retrying. '
                        'No retry, deletion, overwrite or publication attempted. ' + str(error)) from error
            else:
                result = {key: metadata[key] for key in ('tag', 'commit', 'tag_object')}
                result['archive_sha256'] = metadata['files'][metadata['archive']]
                result['mode'] = 'plan-only' if args.command == 'draft' else 'verified'
                outputs(result)
        print(json.dumps(result, indent=2))
    except (release.ReleaseError, publish.maintenance.MaintenanceError, OSError, ValueError, KeyError,
            subprocess.SubprocessError) as error:
        parser.exit(1, f'Personal Actions: {error}\n')


if __name__ == '__main__':
    main()
