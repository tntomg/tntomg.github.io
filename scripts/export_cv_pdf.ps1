$cvRoot = Split-Path -Parent $PSScriptRoot
$cvDir = Join-Path $cvRoot 'public\cv'
$cvAliasBackupDir = Join-Path $cvRoot '.analysis\cv-alias-backups'
New-Item -ItemType Directory -Path $cvAliasBackupDir -Force | Out-Null
$cvWord = New-Object -ComObject Word.Application -ErrorAction Stop
$cvWord.Visible = $false
$cvWord.DisplayAlerts = 0
try {
    foreach ($cvLanguage in @('RU', 'EN')) {
        $cvDocx = Join-Path $cvDir "Aleksei-Pakhalko-CV-$cvLanguage-2026.docx"
        $cvPdf = Join-Path $cvDir "Aleksei-Pakhalko-CV-$cvLanguage-2026.pdf"
        $cvDocument = $cvWord.Documents.Open($cvDocx, $false, $true)
        try {
            $cvDocument.Repaginate()
            $cvDocument.ExportAsFixedFormat($cvPdf, 17)
        } finally { $cvDocument.Close(0) }
        foreach ($cvExtension in @('docx', 'pdf')) {
            $cvCanonical = Join-Path $cvDir "Aleksei-Pakhalko-CV-$cvLanguage-2026.$cvExtension"
            $cvAlias = Join-Path $cvDir "Alexey-Pakhalko-CV-$cvLanguage-2026.$cvExtension"
            $cvReplacement = "$cvAlias.replacement"
            Copy-Item -LiteralPath $cvCanonical -Destination $cvReplacement -Force -ErrorAction Stop
            if (Test-Path -LiteralPath $cvAlias) {
                $cvBackup = Join-Path $cvAliasBackupDir "Alexey-Pakhalko-CV-$cvLanguage-2026.$cvExtension.previous"
                [System.IO.File]::Replace($cvReplacement, $cvAlias, $cvBackup, $true)
            }
            else { Move-Item -LiteralPath $cvReplacement -Destination $cvAlias }
        }
        Write-Output "Updated CV ${cvLanguage}: professional title corrected, engineering positions preserved"
    }
} finally {
    $cvWord.Quit()
    [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($cvWord)
}

