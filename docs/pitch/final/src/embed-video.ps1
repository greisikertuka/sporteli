# Inserts demo/sportel-demo.mp4 on slide 3 over the poster frame, plays on click. Usage: embed-video.ps1 <in.pptx> <out.pptx>
param([string]$in, [string]$out)
$in = (Resolve-Path $in).Path
$video = (Resolve-Path (Join-Path $PSScriptRoot "..\demo\sportel-demo.mp4")).Path
$app = New-Object -ComObject PowerPoint.Application
$pres = $app.Presentations.Open($in, $false, $false, $false)
$slide = $pres.Slides.Item(3)
$poster = $null
foreach ($sh in $slide.Shapes) { if ($sh.AlternativeText -eq "sportel-demo-video") { $poster = $sh } }
$m = $slide.Shapes.AddMediaObject2($video, $false, $true, $poster.Left, $poster.Top, $poster.Width, $poster.Height)
$m.AnimationSettings.PlaySettings.PlayOnEntry = 0
$m.AnimationSettings.PlaySettings.HideWhileNotPlaying = 0
$m.MediaFormat.SetDisplayPictureFromFile((Resolve-Path (Join-Path $PSScriptRoot "..\..\assets\screens\video-cover.png")).Path)
$poster.Delete()
$pres.SaveAs($out)
$pres.Close()
"embedded video -> $out"
