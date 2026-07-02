# File Processing Pipeline: Windows Master → Linux Server

## Overview

This pipeline manages the flow of text and markdown files from a **Windows Master directory** to a **Linux processing server**, tracks their status across workflow stages, and generates a sync report to identify missing files, date mismatches, and orphaned files.

Both sides use **ISO 8601 date format** (`YYYY-MM-DD HH:MM`) to eliminate ambiguity and locale-dependent parsing issues.

```
┌─────────────────────┐      ┌─────────────────────────────────────────────┐
│   Windows Master    │      │              Linux Server                   │
│   (Source of Truth) │─────▶│  unprocessed → processing → processed        │
│   master_list.csv   │      │  (and other workflow directories)           │
└─────────────────────┘      └─────────────────────────────────────────────┘
                                      │
                                      ▼
                            ┌─────────────────────┐
                            │   Sync Report       │
                            │   (sync_report.txt) │
                            └─────────────────────┘
```

---

## 1. Windows Master Directory

### Location
A single directory on your Windows PC that acts as the **source of truth** for all files intended for processing.

### Supported File Types
Only the following extensions are tracked by the sync system:

```
| Extension | Purpose |
|-----------|---------|
| `.txt`    | Plain text files |
| `.md`     | Markdown files |
```

> **Note:** Files with other extensions (`.html`, `.png`, `.jpg`, `.pdf`, `.docx`, etc.) may exist in the Master directory but are **ignored** by the sync checker. They are not expected to be copied to the Linux server.

### Master List Format (`master_list.csv`)

The Master directory must contain a CSV file named `master_list.csv` with the following columns:

```csv
File,LastMod,Size
filename.txt,2026-03-15 10:00,12345
another-file.md,2026-02-20 14:30,9876
```

```
| Column | Format | Description |
|--------|--------|-------------|
| `File` | `filename.ext` | Filename with extension. Must match exactly on Linux. |
| `LastMod` | `YYYY-MM-DD HH:MM` | Last modification date in **ISO 8601** format. **Date is used for sync checks; time is ignored.** |
| `Size` | Integer (bytes) | File size in bytes. Used to verify integrity. |
```

#### CSV Generation Tips
- Use the same date format consistently: `YYYY-MM-DD HH:MM` (ISO 8601)
- Ensure filenames are exact matches (Linux is case-sensitive)
- Regenerate the CSV whenever files are added, removed, or modified in the Master directory

---

## 2. Linux Server Directory Structure

The Linux server contains workflow directories. Files move through these directories as they are processed.

### Standard Directories

```
| Directory | Purpose | Who Moves Files |
|-----------|---------|---------------|
| `~/project/unprocessed` | New files awaiting processing | User (manual upload or automated sync) |
| `~/project/processing` | Files currently being processed | Processing script / application |
| `~/project/processed` | Files that have completed processing | Processing script / application |
```

### Additional Directories
You may define additional workflow directories as needed (e.g., `tmp-generated-texts`, `review`, `archive`). The sync script detects all directories dynamically and reports the status of each file based on which directory it currently resides in.

> **Important:** A file should exist in **only one** directory at a time. If a file appears in multiple directories, it indicates a workflow error.

---

## 3. File Workflow

### Step 1: Copy from Windows to Linux
Copy `.txt` and `.md` files from the Windows Master directory to the Linux `unprocessed` directory.

**Recommended methods:**
- `scp` or `rsync` over SSH
- SFTP client (FileZilla, WinSCP)
- Automated sync script

**Preserve file metadata when possible:**
- Modification date (used for date-mismatch detection)
- Filename (must match exactly, including case)

### Step 2: Processing
A processing script or application moves files from `unprocessed` → `processing` → `processed`.

- Files in `processing` should not be modified by external processes
- Upon completion, files are moved to `processed`
- If processing fails, files may be moved to an error directory or left in `processing`

### Step 3: Sync Verification
Run the sync check script to compare the Windows Master list against the Linux server directories.

---

## 4. Sync Check Script

### Prerequisites
- Python 3.7+
- Access to the `master_list.csv` file
- Bash directory listing from the Linux server (with ISO dates)

### Step A: Generate `master_list.csv` on Windows (PowerShell)

Open PowerShell and run:

```powershell
$source = "C:\Users\User1\Master\*"
$output = Join-Path $PSScriptRoot "master_list.csv"

Get-ChildItem -Path $source -Include *.txt,*.md -File |
    Select-Object Name,
        @{N='LastMod';E={$_.LastWriteTime.ToString("yyyy-MM-dd HH:mm")}},
        @{N='Size';E={$_.Length}} |
    Export-Csv -Path $output -NoTypeInformation -Encoding UTF8
```

Copy `master_list.csv` to the directory where you will run the sync check script.

### Step B: Get the Linux Directory Listing

SSH into the Linux server and run:

```bash
for dir in unprocessed processing processed; do
    echo "~/$dir"
    ls -l --time-style=long-iso ~/$dir
    echo
done
```

If you have additional directories, include them:

```bash
for dir in unprocessed processing processed tmp-generated-texts review; do
    echo "~/$dir"
    ls -l --time-style=long-iso ~/$dir
    echo
done
```

Copy the entire output and save it as `bash_listing.txt` on your Windows PC.

> **Tip:** Use `--time-style=long-iso` to ensure unambiguous ISO 8601 dates. If your Linux distribution doesn't support `long-iso`, use `--time-style=+"%Y-%m-%d %H:%M"` instead. Do not use `ls -la` (hidden files are not needed).

### Step C: Run the Sync Check

1. Place `master_list.csv` and `bash_listing.txt` in the same directory as `sync_check.py`
2. Run:

```bash
python sync_check.py
```

3. Review the generated `sync_report.txt`

---

## 5. Understanding the Sync Report

The report is divided into four sections:

### Section 1: Missing Files
**Files on the Master list but NOT found on the Linux server.**

```
❌ missing-file.txt
   Master: 2026-03-15 10:00, 12345 bytes
```

**Action required:** Copy these files to the Linux `unprocessed` directory.

### Section 2: Files Found on Linux (with Status)
**Files that exist on both Master and Linux, grouped by their current directory/status.**

```
[PROCESSED] (42 files):
  ✓ completed-file.txt
     Linux:  2026-03-15 10:00, 12345 bytes
     Master: 2026-03-15 10:00, 12345 bytes
```

Each file shows:
- Linux size and date
- Master size and date
- Size match indicator (`✓` or `⚠ SIZE MISMATCH`)
- Date mismatch warning (if day-level difference detected)

### Section 3: Date Mismatches
**A dedicated summary of files where the date (day, month, year) differs between Master and Linux.**

```
⚠ my-file.md [processing]
  Master: 2026-06-05 | Linux: 2026-02-26 | Diff: +99 days
```

**Interpretation:**
- Positive diff: Master is newer than Linux copy
- Negative diff: Linux copy is newer than Master
- Time (hours/minutes) is ignored — only the calendar date matters

**Common causes:**
- File was modified on Linux after copying
- File was modified on Windows after copying
- Copy tool did not preserve modification date

### Section 4: Orphan Files
**Files found on the Linux server but NOT on the Master list.**

```
⚠ orphan-file.txt [processed]
   Dir: ~/project/processed
   2026-03-15 10:00, 12345 bytes
```

**Possible explanations:**
- File was generated by the processing pipeline (expected for output files)
- File was deleted from Master but not from Linux
- File was renamed on Master but not on Linux
- File was copied to Linux but never added to the Master list

**Action:** Review and decide whether to:
- Add the file to the Master list
- Delete the file from Linux
- Move it to an archive directory
- Ignore it (if it is a generated output file)

---

## 6. Best Practices

### Naming Conventions
- Use **kebab-case** or **snake_case**: `my-file-name.txt`, `my_file_name.md`
- Avoid spaces in filenames: `my file.txt` → `my-file.txt`
- Avoid special characters: `&`, `$`, `#`, `%`, `!`, `'`, `"`, etc.
- Use only ASCII characters to prevent encoding issues between Windows and Linux
- Keep extensions lowercase: `.txt`, `.md` (not `.TXT`, `.MD`)

### Date Handling
- The Master CSV uses `YYYY-MM-DD HH:MM` format (ISO 8601)
- The Linux `ls -l --time-style=long-iso` uses the same ISO format
- Both sides now use the same unambiguous format — no locale or timezone guessing needed
- If a file is modified on either side, update the Master CSV and re-copy if needed

### File Size
- Size is compared as a basic integrity check
- If sizes differ but dates match, the file content has changed
- For stronger integrity checks, consider adding MD5 or SHA-256 checksums to the pipeline

### Workflow Hygiene
- **One file, one directory:** A file should never exist in multiple status directories simultaneously
- **Move, don't copy:** Processing scripts should move files between directories, not copy them
- **Clean up orphans:** Periodically review orphan files and either add them to the Master list or delete them
- **Regenerate CSV:** Always regenerate `master_list.csv` after bulk changes to the Master directory

### Automation Recommendations
- Schedule the sync check weekly or after each batch upload
- Use `rsync -avz --include='*.txt' --include='*.md' --exclude='*'` to copy only relevant files while preserving dates
- Consider a pre-sync dry-run to preview what will be copied

---

## 7. Troubleshooting

### "File not found" but I copied it
- Check case sensitivity: `MyFile.txt` on Windows vs `myfile.txt` on Linux
- Check for trailing spaces or invisible characters in the filename
- Verify the file is in one of the expected directories, not a subdirectory

### Date mismatch on every file
- Your copy tool may not preserve modification times. Use `rsync -t` or `scp -p`
- The system clocks on Windows and Linux may differ. Synchronize with NTP
- Daylight saving time transitions can cause 1-day offsets

### Orphan files are actually expected outputs
- If your pipeline generates new files (e.g., summaries, converted formats), consider maintaining a separate "Generated Outputs" list
- Or add a dedicated directory (e.g., `generated/`) that is excluded from the Master list comparison

### Script fails to parse the listing
- Ensure you use `ls -l --time-style=long-iso` (not plain `ls -l`, `ls -la`, `ls -lh`, or `ls --full-time`)
- Ensure the directory paths are printed before each listing (as shown in the SSH command above)
- The ISO format works regardless of locale; no need to set `LANG=en_US.UTF-8`

---

## 8. File Extensions Reference

```
| Extension | Tracked by Sync | Expected on Linux | Notes |
|-----------|-----------------|-------------------|-------|
| `.txt` | ✅ Yes | ✅ Yes | Primary processing format |
| `.md` | ✅ Yes | ✅ Yes | Markdown processing format |
| `.html` | ❌ No | ❌ No | Ignored by sync checker |
| `.png` | ❌ No | ❌ No | Ignored by sync checker |
| `.jpg` | ❌ No | ❌ No | Ignored by sync checker |
| `.pdf` | ❌ No | ❌ No | Ignored by sync checker |
| `.docx` | ❌ No | ❌ No | Ignored by sync checker |
| `.csv` | ❌ No | ❌ No | Master list itself is `.csv` but data files are ignored |
```

---

## 9. Quick Command Reference

### Generate Master CSV (PowerShell)
```powershell
Get-ChildItem -Path "C:\Master" -Include *.txt,*.md |
    Select-Object Name,
        @{N='LastMod';E={$_.LastWriteTime.ToString("yyyy-MM-dd HH:mm")}},
        @{N='Size';E={$_.Length}} |
    Export-Csv -Path "master_list.csv" -NoTypeInformation -Encoding UTF8
```

### Get Linux Listing (SSH)
```bash
for dir in unprocessed processing processed; do
    echo "~/users/$USER/$dir"
    ls -l --time-style=long-iso ~/users/$USER/$dir
    echo
done > listing.txt
```

### Run Sync Check
```bash
python sync_check.py
```

---

## 10. Glossary

```
| Term | Definition |
|------|------------|
| **Master Directory** | The Windows source directory containing the canonical copy of all files |
| **Master List** | The `master_list.csv` file cataloging all `.txt` and `.md` files in the Master Directory |
| **Orphan** | A file on the Linux server that does not appear in the Master List |
| **Status** | The workflow stage of a file, determined by which Linux directory it resides in |
| **Date Mismatch** | When the calendar date (day/month/year) of a file differs between Master and Linux |
| **Source of Truth** | The Master Directory; its contents and metadata are considered authoritative |
| **ISO 8601** | International standard date format: `YYYY-MM-DD HH:MM` |
```

---

*Last updated: 2026-07-01*
*Pipeline version: 1.1*
