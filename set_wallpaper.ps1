param(
    [Parameter(Mandatory = $true)][string]$Path,
    [ValidateSet('Fill', 'Fit', 'Stretch', 'Tile', 'Center', 'Span')][string]$Style = 'Fill'
)

# Sets the given image as the desktop wallpaper on each monitor.
# NOTE: keep this file pure ASCII. Windows PowerShell 5.1 decodes
# BOM-less .ps1 files as ANSI/GBK, so non-ASCII comments here would
# turn into mojibake and break parsing (UnexpectedToken).
# The image path is passed in as an argument, so it may contain
# non-ASCII characters without any problem.
#
# One picture is painted across the whole virtual desktop. On every
# monitor it is scaled to that screen's height and centered left to
# right, so a taller screen is not left blank at the top.

if (-not (Test-Path -LiteralPath $Path)) {
    Write-Error "Image not found: $Path"
    exit 1
}

$full = (Resolve-Path -LiteralPath $Path).Path

$position = switch ($Style) {
    'Center'  { 0 }
    'Tile'    { 1 }
    'Stretch' { 2 }
    'Fit'     { 3 }
    'Fill'    { 4 }
    'Span'    { 5 }
}
$styleValue = switch ($Style) {
    'Fill'    { '10' }
    'Fit'     { '6' }
    'Stretch' { '2' }
    'Tile'    { '0' }
    'Center'  { '0' }
    'Span'    { '22' }
}

$key = 'HKCU:\Control Panel\Desktop'
if ($Style -eq 'Fill') { $styleValue = '22' }
Set-ItemProperty $key -Name WallpaperStyle -Value $styleValue
Set-ItemProperty $key -Name TileWallpaper -Value $(if ($Style -eq 'Tile') { '1' } else { '0' })

Add-Type -ReferencedAssemblies System.Drawing -TypeDefinition @"
using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Runtime.InteropServices;

public enum OneWallpaperPosition {
    Center = 0,
    Tile = 1,
    Stretch = 2,
    Fit = 3,
    Fill = 4,
    Span = 5
}

[StructLayout(LayoutKind.Sequential)]
public struct OneWallpaperRect {
    public int Left;
    public int Top;
    public int Right;
    public int Bottom;
}

[ComImport, Guid("B92B56A9-8B55-4E14-9A89-0199BBB6F93B")]
[InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IOneDesktopWallpaper {
    void SetWallpaper([MarshalAs(UnmanagedType.LPWStr)] string monitorID, [MarshalAs(UnmanagedType.LPWStr)] string wallpaper);
    [return: MarshalAs(UnmanagedType.LPWStr)]
    string GetWallpaper([MarshalAs(UnmanagedType.LPWStr)] string monitorID);
    [return: MarshalAs(UnmanagedType.LPWStr)]
    string GetMonitorDevicePathAt(uint monitorIndex);
    uint GetMonitorDevicePathCount();
    void GetMonitorRECT([MarshalAs(UnmanagedType.LPWStr)] string monitorID, out OneWallpaperRect displayRect);
    void SetBackgroundColor(uint color);
    uint GetBackgroundColor();
    void SetPosition(OneWallpaperPosition position);
    OneWallpaperPosition GetPosition();
    void SetSlideshow(IntPtr items);
    IntPtr GetSlideshow();
    void SetSlideshowOptions(int options, uint slideshowTick);
    void GetSlideshowOptions(out int options, out uint slideshowTick);
    void AdvanceSlideshow([MarshalAs(UnmanagedType.LPWStr)] string monitorID, int direction);
    uint GetStatus();
    void Enable([MarshalAs(UnmanagedType.Bool)] bool enable);
}

[ComImport, Guid("C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD")]
public class OneDesktopWallpaper { }

public static class OneWallpaperSetter {
    [DllImport("user32.dll")]
    static extern bool SetProcessDPIAware();

    public static string Apply(string path) {
        SetProcessDPIAware();
        var type = Type.GetTypeFromCLSID(new Guid("C2CF3110-460E-4fc1-B9D0-8A1C0C9CC4BD"));
        var wall = (IOneDesktopWallpaper)Activator.CreateInstance(type);
        using (var src = new Bitmap(path)) {
            uint count = wall.GetMonitorDevicePathCount();
            var rects = new OneWallpaperRect[count];
            int minL = int.MaxValue, minT = int.MaxValue, maxR = int.MinValue, maxB = int.MinValue;
            for (uint i = 0; i < count; i++) {
                string id = wall.GetMonitorDevicePathAt(i);
                wall.GetMonitorRECT(id, out rects[i]);
                if (rects[i].Left < minL) minL = rects[i].Left;
                if (rects[i].Top < minT) minT = rects[i].Top;
                if (rects[i].Right > maxR) maxR = rects[i].Right;
                if (rects[i].Bottom > maxB) maxB = rects[i].Bottom;
                Console.WriteLine("monitor {0} {1},{2} {3}x{4}", i, rects[i].Left, rects[i].Top, rects[i].Right - rects[i].Left, rects[i].Bottom - rects[i].Top);
            }
            int canvasW = Math.Max(1, maxR - minL);
            int canvasH = Math.Max(1, maxB - minT);
            string dest = Path.Combine(Path.GetDirectoryName(path), "desktop.png");
            using (var bmp = new Bitmap(canvasW, canvasH))
            using (var g = Graphics.FromImage(bmp)) {
                g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                g.Clear(Color.FromArgb(13, 16, 21));
                for (uint i = 0; i < count; i++) {
                    int w = rects[i].Right - rects[i].Left;
                    int h = rects[i].Bottom - rects[i].Top;
                    if (w < 1 || h < 1) continue;
                    int ox = rects[i].Left - minL;
                    int oy = rects[i].Top - minT;
                    float scale = h / (float)src.Height;
                    float dw = src.Width * scale;
                    float x = ox + (w - dw) / 2f;
                    g.SetClip(new Rectangle(ox, oy, w, h));
                    g.DrawImage(src, x, oy, dw, h);
                    g.ResetClip();
                }
                bmp.SetResolution(96, 96);
                bmp.Save(dest, ImageFormat.Png);
            }
            wall.SetPosition(OneWallpaperPosition.Span);
            wall.SetWallpaper(null, dest);
            Console.WriteLine("canvas {0}x{1}", canvasW, canvasH);
        }
        return "ok";
    }
}
"@

$ErrorActionPreference = 'Stop'
if ($Style -ne 'Fill') {
    Write-Error "Only Fill is placed per monitor."
    exit 1
}
[OneWallpaperSetter]::Apply($full) | Out-Null

Write-Output "Wallpaper set: $full"
