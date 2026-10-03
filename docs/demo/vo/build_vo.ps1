# Render the narration to one WAV per beat, offline, with Windows SAPI.
#
#   powershell -ExecutionPolicy Bypass -File build_vo.ps1
#
# There is no API key and no network call. System.Speech ships with Windows, so
# this works on a laptop with the Wi-Fi off, the same constraint the rest of
# the demo is built under.
#
# The beat order and slot lengths are read from ../beats.json rather than
# duplicated here, because encode.py derives the timeline from those numbers and
# a second hand-written copy would be free to drift from the encoded MP4.

$ErrorActionPreference = "Stop"

$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$OUT  = Join-Path $HERE "wav"

$script = Get-Content (Join-Path $HERE "script.json") -Raw | ConvertFrom-Json
$beats  = (Get-Content (Join-Path (Join-Path $HERE "..") "beats.json") -Raw | ConvertFrom-Json).beats

if ($beats.Count -ne $script.beats.Count) {
  throw "beats.json has $($beats.Count) beats, script.json has $($script.beats.Count). They must match."
}

# Same constants encode.py uses. If those change, these must change with them.
$XFADE = 0.5
$HOLD_PAD = 2.0

New-Item -ItemType Directory -Force -Path $OUT | Out-Null

Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer

$voice = $script.voice
if (-not ($synth.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Name -eq $voice })) {
  $fallback = $synth.GetInstalledVoices() | Select-Object -First 1
  Write-Warning "voice '$voice' not installed, falling back to $($fallback.VoiceInfo.Name)"
  $voice = $fallback.VoiceInfo.Name
}
$synth.SelectVoice($voice)
$synth.Rate = [int]$script.rate

# 16 kHz mono. This is narration under a screen recording, not a podcast, and it
# keeps the whole audio track around 4 MB.
$bits = [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen
$channels = [System.Speech.AudioFormat.AudioChannel]::Mono
$fmt = [System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(16000, $bits, $channels)

Write-Host "voice : $voice"
Write-Host "rate  : $($synth.Rate)"
Write-Host "output: $OUT"
Write-Host ""

$rows = @()
$t = 0.0
$i = 0

foreach ($b in $script.beats) {
  $i++
  $hold = [double]$beats[$i - 1].seconds + $HOLD_PAD
  $start = $t

  $path = Join-Path $OUT ("beat-{0:d2}.wav" -f $i)
  $synth.SetOutputToWaveFile($path, $fmt)
  $synth.Speak([string]$b.text)
  $synth.SetOutputToNull()

  $dur = ([System.Media.SoundPlayer]::new($path)).Load() 2>$null
  $len = (New-Object System.IO.FileInfo $path).Length
  # 16 kHz, 16-bit, mono -> 32000 bytes per second.
  $wavSeconds = $len / 32000.0

  $rows += [pscustomobject]@{
    beat     = $i
    start    = [math]::Round($start, 2)
    hold     = [math]::Round($hold, 2)
    speech   = [math]::Round($wavSeconds, 2)
    words    = ($b.text -split '\s+').Count
    chapter  = $b.chapter
    file     = [System.IO.Path]::GetFileName($path)
  }

  $t += $hold - $XFADE
}

$synth.Dispose()

$rows | Format-Table -AutoSize

# A line that runs past its beat is worse than no line at all: it overlaps the
# next caption, and the caption is what a muted judge reads.
$lead = [double]$script.lead_in_seconds
$tail = [double]$script.tail_seconds
$bad = @($rows | Where-Object { ($_.speech + $lead + $tail) -gt $_.hold })

Write-Host ""
if ($bad.Count -gt 0) {
  Write-Warning "$($bad.Count) beat(s) overflow their slot. Shorten the text or lower the rate."
  $bad | Format-Table -AutoSize
  exit 1
}

$total = [math]::Round($t, 2)
$audioBytes = (Get-ChildItem $OUT -Filter *.wav | Measure-Object -Property Length -Sum).Sum
Write-Host "all beats fit: longest speech $([math]::Round(($rows | Measure-Object -Property speech -Maximum).Maximum, 2))s"
Write-Host "timeline     : $total s"
Write-Host "audio total  : $([math]::Round($audioBytes / 1MB, 2)) MB"
