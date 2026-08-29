Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force -Path 'assets' | Out-Null

function Generate-Icon {
    param (
        [string]$FilePath,
        [int]$Red,
        [int]$Green,
        [int]$Blue,
        [string]$Letter
    )

    $bmp = New-Object System.Drawing.Bitmap(64, 64)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)

    $color = [System.Drawing.Color]::FromArgb($Red, $Green, $Blue)
    $brush = New-Object System.Drawing.SolidBrush($color)
    $g.FillEllipse($brush, 2, 2, 60, 60)

    $font = New-Object System.Drawing.Font('Arial', 28, [System.Drawing.FontStyle]::Bold)
    $textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center

    $rect = New-Object System.Drawing.RectangleF(0, 0, 64, 64)
    $g.DrawString($Letter, $font, $textBrush, $rect, $sf)

    $hIcon = $bmp.GetHicon()
    $icon = [System.Drawing.Icon]::FromHandle($hIcon)
    $fs = New-Object System.IO.FileStream($FilePath, [System.IO.FileMode]::Create)
    $icon.Save($fs)
    $fs.Close()
    $bmp.Dispose()
    $g.Dispose()
}

Generate-Icon -FilePath 'assets/app.ico' -Red 37 -Green 99 -Blue 235 -Letter 'L'
Generate-Icon -FilePath 'assets/stop.ico' -Red 220 -Green 38 -Blue 38 -Letter 'S'
Write-Host 'Icons generated successfully in assets/ folder.'
