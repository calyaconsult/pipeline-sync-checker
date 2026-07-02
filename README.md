# Create and Sync a List of Files on a Windows PC with a Remote Server

Use three scripts that work together to create a report on the status of a file processing queue and keept it in sync with a master list on your Windows machine.

- `create-master-list.ps1` is a PowerShell script that searches a directory that serves as master directory for `.txt` and `.md` files and creates a CSV file
- `create-pipeline-listing.sh` is a bash script that lists three (or more) directories on a Linux machine and creates a file with the names and modification times of the files in the processing queue.
- `sync_check.py` is a Python script that compares the master list (the Windows CSV file) with the list of files in the queue and returns information about the status of each file and, if applicable, an overview of missing or orphaned files.
 
