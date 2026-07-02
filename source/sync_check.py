#!/usr/bin/env python3
"""
File Sync Checker: Compare Windows master list against Linux server directories
Uses ISO 8601 date format (YYYY-MM-DD HH:MM) on both sides for unambiguous parsing.
"""

import csv
import re
from datetime import datetime
from collections import defaultdict
import os


def parse_bash_listing(listing_text):
    """
    Parse bash ls -l --time-style=long-iso output to extract file info.
    Returns dict: filename -> {size, date, date_str, directory, status}
    """
    files = {}
    current_dir = None

    lines = listing_text.strip().split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Detect directory path (e.g., "~/users/user1/unprocessed")
        if line.startswith('~/') or line.startswith('/'):
            current_dir = line.strip().rstrip('/')
            continue

        # Skip "total X" lines
        if line.startswith('total '):
            continue

        # Parse ls -l --time-style=long-iso line:
        # -rw-r--r-- 1 user1 user1 6055 2026-02-28 17:00 0fqfrcbt3hrmt0cwmftr7amrbr.txt
        match = re.match(
            r'^[-dl].+?\s+\d+\s+\S+\s+\S+\s+(\d+)\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(.+)$',
            line
        )

        if match:
            size = int(match.group(1))
            date_str = match.group(2).strip()
            filename = match.group(3).strip()

            # Simple, unambiguous ISO parsing
            dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")

            # Extract directory status from path
            dir_status = os.path.basename(current_dir) if current_dir else 'unknown'

            files[filename] = {
                'size': size,
                'date': dt,
                'date_str': date_str,
                'directory': current_dir,
                'status': dir_status
            }

    return files


def parse_master_csv(csv_text):
    """
    Parse the Windows master list CSV with ISO dates.
    Returns dict: filename -> {last_mod, size}
    """
    files = {}
    reader = csv.DictReader(csv_text.strip().split('\n'))

    for row in reader:
        filename = row['File'].strip()
        size = int(row['Size'])

        # Parse ISO date: "2026-02-28 17:00"
        date_str = row['LastMod'].strip()
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M")

        files[filename] = {
            'size': size,
            'date': dt,
            'date_str': date_str
        }

    return files


def compare_files(master_files, linux_files):
    """
    Cross-reference master list with Linux files.
    Only considers .txt and .md files from the master list.
    """

    # FILTER: Keep only .txt and .md files from master list
    allowed_extensions = ('.txt', '.md')
    master_files = {
        fn: info for fn, info in master_files.items()
        if fn.lower().endswith(allowed_extensions)
    }

    results = {
        'missing_on_linux': [],      # On master (and .txt/.md), not on Linux
        'found_on_linux': [],        # On master (and .txt/.md), found on Linux
        'orphan_on_linux': [],       # On Linux, not on master
        'date_mismatches': [],       # Date differences (day-level)
    }

    master_filenames = set(master_files.keys())
    linux_filenames = set(linux_files.keys())

    # Files missing on Linux
    for filename in sorted(master_filenames - linux_filenames):
        results['missing_on_linux'].append({
            'filename': filename,
            'master_size': master_files[filename]['size'],
            'master_date': master_files[filename]['date_str']
        })

    # Files found on Linux
    for filename in sorted(master_filenames & linux_filenames):
        master = master_files[filename]
        linux = linux_files[filename]

        # Compare dates (ignore time)
        date_diff = None
        if master['date'] and linux['date']:
            master_date = master['date'].date()
            linux_date = linux['date'].date()
            delta = (master_date - linux_date).days
            if delta != 0:
                date_diff = {
                    'master_date': master_date.strftime('%Y-%m-%d'),
                    'linux_date': linux_date.strftime('%Y-%m-%d'),
                    'days_diff': delta
                }

        if date_diff:
            results['date_mismatches'].append({
                'filename': filename,
                'status': linux['status'],
                'date_diff': date_diff
            })

        results['found_on_linux'].append({
            'filename': filename,
            'status': linux['status'],
            'linux_dir': linux['directory'],
            'master_size': master['size'],
            'linux_size': linux['size'],
            'size_match': master['size'] == linux['size'],
            'master_date': master['date_str'],
            'linux_date': linux['date_str'],
            'date_diff': date_diff
        })

    # Orphan files on Linux (not on master)
    for filename in sorted(linux_filenames - master_filenames):
        results['orphan_on_linux'].append({
            'filename': filename,
            'status': linux_files[filename]['status'],
            'linux_dir': linux_files[filename]['directory'],
            'size': linux_files[filename]['size'],
            'date': linux_files[filename]['date_str']
        })

    return results


def generate_report(results):
    """Generate a formatted text report."""
    lines = []
    lines.append("=" * 80)
    lines.append("FILE SYNC CHECK REPORT")
    lines.append("=" * 80)
    lines.append("")

    # 1. Missing files
    lines.append("-" * 80)
    lines.append(f"1. FILES ON MASTER LIST BUT MISSING ON LINUX SERVER ({len(results['missing_on_linux'])} files)")
    lines.append("-" * 80)
    if results['missing_on_linux']:
        for item in sorted(results['missing_on_linux'], key=lambda x: x['filename']):
            lines.append(f"  ❌ {item['filename']}")
            lines.append(f"     Master: {item['master_date']}, {item['master_size']} bytes")
    else:
        lines.append("  ✓ All master list files are present on the Linux server")
    lines.append("")

    # 2. Found files with status
    lines.append("-" * 80)
    lines.append(f"2. FILES FOUND ON LINUX SERVER WITH STATUS ({len(results['found_on_linux'])} files)")
    lines.append("-" * 80)

    # Group by status
    by_status = defaultdict(list)
    for item in results['found_on_linux']:
        by_status[item['status']].append(item)

    for status in sorted(by_status.keys()):
        lines.append(f"\n  [{status.upper()}] ({len(by_status[status])} files):")
        for item in sorted(by_status[status], key=lambda x: x['filename']):
            size_ok = "✓" if item['size_match'] else "⚠ SIZE MISMATCH"
            lines.append(f"    {size_ok} {item['filename']}")
            lines.append(f"       Linux:  {item['linux_date']}, {item['linux_size']} bytes")
            lines.append(f"       Master: {item['master_date']}, {item['master_size']} bytes")
            if item['date_diff']:
                d = item['date_diff']
                lines.append(f"       ⚠ DATE DIFF: Master {d['master_date']} vs Linux {d['linux_date']} ({d['days_diff']:+,d} days)")
    lines.append("")

    # 3. Date mismatches
    lines.append("-" * 80)
    lines.append(f"3. DATE MISMATCHES (day-level) ({len(results['date_mismatches'])} files)")
    lines.append("-" * 80)
    if results['date_mismatches']:
        for item in sorted(results['date_mismatches'], key=lambda x: x['filename']):
            d = item['date_diff']
            lines.append(f"  ⚠ {item['filename']} [{item['status']}]")
            lines.append(f"    Master: {d['master_date']} | Linux: {d['linux_date']} | Diff: {d['days_diff']:+,d} days")
    else:
        lines.append("  ✓ No date mismatches found (ignoring time)")
    lines.append("")

    # 4. Orphan files
    lines.append("-" * 80)
    lines.append(f"4. FILES ON LINUX SERVER BUT NOT ON MASTER LIST ({len(results['orphan_on_linux'])} files)")
    lines.append("-" * 80)
    if results['orphan_on_linux']:
        for item in sorted(results['orphan_on_linux'], key=lambda x: (x['status'], x['filename'])):
            lines.append(f"  ⚠ {item['filename']} [{item['status']}]")
            lines.append(f"     Dir: {item['linux_dir']}")
            lines.append(f"     {item['date']}, {item['size']} bytes")
    else:
        lines.append("  ✓ No orphan files found")
    lines.append("")

    # Summary
    lines.append("=" * 80)
    lines.append("SUMMARY")
    lines.append("=" * 80)
    total_master = len(results['missing_on_linux']) + len(results['found_on_linux'])
    lines.append(f"Total master list files (.txt/.md): {total_master}")
    lines.append(f"  Found on Linux:                   {len(results['found_on_linux'])}")
    lines.append(f"  Missing on Linux:                 {len(results['missing_on_linux'])}")
    lines.append(f"Date mismatches (day-level):        {len(results['date_mismatches'])}")
    lines.append(f"Orphan files on Linux:              {len(results['orphan_on_linux'])}")
    lines.append("=" * 80)

    return '\n'.join(lines)


def main():
    # Read from files (recommended for production use)
    try:
        with open('master_list.csv', 'r', encoding='utf-8') as f:
            csv_text = f.read()
    except FileNotFoundError:
        print("ERROR: master_list.csv not found.")
        print("Generate it on Windows, using the PowerShell script `create-master-list.ps1`")
        return

    try:
        with open('bash_listing.txt', 'r', encoding='utf-8') as f:
            listing_text = f.read()
    except FileNotFoundError:
        print("ERROR: bash_listing.txt not found.")
        print("Generate it on Linux with `create-pipeline-listing.sh`")
        return

    # Parse inputs
    linux_files = parse_bash_listing(listing_text)
    master_files = parse_master_csv(csv_text)

    # Compare
    results = compare_files(master_files, linux_files)

    # Generate and print report
    report = generate_report(results)
    print(report)

    # Save to file
    with open('sync_report.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    print("\nReport saved to sync_report.txt")

if __name__ == '__main__':
    main()  
