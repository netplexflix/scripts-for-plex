$URL = 'http://localhost:32400/status/sessions?X-Plex-Token=_YOUR_PLEX_TOKEN_HERE'
$qBittorrentProcess = $null

while ($true)
{
    $PlexStatus = Invoke-RestMethod -Uri $URL

    if ($PlexStatus.MediaContainer.Size -eq 0)
    {
        echo Plex is not streaming. Closing qbittorent
        
        # Close qBittorrent gracefully
        $qBittorrentProcess = Get-Process qbittorrent -ErrorAction SilentlyContinue
        if ($qBittorrentProcess -ne $null)
        {
            $qBittorrentProcess.CloseMainWindow()
        }
        
        # Shutdown
        echo Shutting Down in 60 seconds
        Start-Sleep -Seconds 60
        Invoke-Expression -Command 'shutdown -s -f -t 1'
    }
    
    echo Plex is streaming
    Start-Sleep -Seconds 300
}
