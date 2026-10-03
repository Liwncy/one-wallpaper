param(
    [Parameter(Mandatory = $true)][string]$Path,
    [ValidateSet('Fill', 'Fit', 'Stretch', 'Tile', 'Center', 'Span')][string]$Style = 'Fill'
)

# Sets the given image as the desktop wallpaper.
# NOTE: keep this file pure ASCII. Windows PowerShell 5.1 decodes
# BOM-less .ps1 files as ANSI/GBK, so non-ASCII comments here would
# turn into mojibake and break parsing (UnexpectedToken).
# The image path is passed in as an argument, so it may contain
# non-ASCII characters without any problem.

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Error "Image not found: $Path"
    exit 1
}

$full = (Resolve-Path -LiteralPath $Path).Path

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class WallpaperApi {
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);

    public const int SPI_SETDESKWALLPAPER = 20;
    public const int SPIF_UPDATEINIFILE = 0x01;
    public const int SPIF_SENDCHANGE = 0x02;

    public static void Set(string path) {
        SystemParametersInfo(SPI_SETDESKWALLPAPER, 0, path,
            SPIF_UPDATEINIFILE | SPIF_SENDCHANGE);
    }
}
"@

# Write the fit mode to the registry first, then push the wallpaper.
$key = 'HKCU:\Control Panel\Desktop'
switch ($Style) {
    'Fill'    { Set-ItemProperty $key -Name WallpaperStyle -Value '10' }
    'Fit'     { Set-ItemProperty $key -Name WallpaperStyle -Value '6'  }
    'Stretch' { Set-ItemProperty $key -Name WallpaperStyle -Value '2'  }
    'Tile'    { Set-ItemProperty $key -Name WallpaperStyle -Value '0'  }
    'Center'  { Set-ItemProperty $key -Name WallpaperStyle -Value '0'  }
    'Span'    { Set-ItemProperty $key -Name WallpaperStyle -Value '22' }
}
Set-ItemProperty $key -Name TileWallpaper -Value '0'

[WallpaperApi]::Set($full)
Write-Output "Wallpaper set: $full"
