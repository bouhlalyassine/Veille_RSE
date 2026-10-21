# Enregistre les cles API LLM dans Key Vault (saisie masquee, laisser vide pour ignorer).
# L'application relit les secrets a son redemarrage.
param([Parameter(Mandatory)][string]$KeyVault)
$ErrorActionPreference = 'Stop'

foreach ($name in 'GOOGLE-API-KEY', 'GOOGLE-API-KEY-1', 'GROQ-API-KEY', 'GROQ-API-KEY-1') {
    $secure = Read-Host "$name (Entree pour ignorer)" -AsSecureString
    $value = [System.Net.NetworkCredential]::new('', $secure).Password
    if (-not $value) { continue }
    $file = New-TemporaryFile
    try {
        # Passage par fichier : la cle n'apparait pas dans la ligne de commande.
        [IO.File]::WriteAllText($file, $value)
        az keyvault secret set --vault-name $KeyVault -n $name --file $file -o none
        if ($LASTEXITCODE) { throw "Echec pour $name" }
        Write-Host "  $name enregistre"
    }
    finally { Remove-Item $file -Force }
}
