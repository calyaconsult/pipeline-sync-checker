$source = "C:\Users\<PATH TO MASTER DIRECTORY>\*"
$output = Join-Path $PSScriptRoot "master_list.csv"

Get-ChildItem -Path $source -Include *.txt,*.md -File |
    Select-Object Name,
        @{N='LastMod';E={$_.LastWriteTime.ToString("yyyy-MM-dd HH:mm")}},
        @{N='Size';E={$_.Length}} |
    Export-Csv -Path $output -NoTypeInformation -Encoding UTF8
