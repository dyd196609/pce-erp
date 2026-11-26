param([int]$Port)
$listener=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$Port)
try{$listener.Start();[Console]::Out.WriteLine('READY');[Console]::Out.Flush();while($true){Start-Sleep -Seconds 1}}finally{$listener.Stop()}
