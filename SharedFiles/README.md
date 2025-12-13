# SharedFiles - MacWinControl

Deze map is bedoeld voor het delen van bestanden tussen Mac en Windows machines voor debugging doeleinden.

## Gebruik

### Screenshots
- Plaats screenshots hier vanuit beide machines
- Naamgeving: `{mac|win}_{datum}_{beschrijving}.png`
- Voorbeeld: `win_20250112_error_message.png`

### Logs
- Copy-paste relevante log output naar `.txt` files
- Naamgeving: `{mac|win}_{datum}_{log}.txt`
- Voorbeeld: `mac_20250112_connection_log.txt`

## Synchronisatie

### Optie 1: Gedeelde netwerk map
Configureer deze map als een SMB share:
- **Mac**: Ga naar System Preferences → Sharing → File Sharing → voeg deze map toe
- **Windows**: Connect via `\\<mac-ip>\SharedFiles`

### Optie 2: Cloud sync
Plaats deze map in iCloud Drive, Dropbox, of OneDrive

### Optie 3: Copy via Terminal
```bash
# Van Mac naar Windows (vanuit Mac terminal):
scp /Users/Frank/MacWinControl/SharedFiles/* user@windows-ip:C:/SharedFiles/

# Van Windows naar Mac (vanuit Windows PowerShell):
scp C:\SharedFiles\* user@mac-ip:/Users/Frank/MacWinControl/SharedFiles/
```

## Actuele Debug Info

### Mac IP: 192.168.178.105
### Windows IP: 192.168.178.133
### TCP Port: 52525
### UDP Port: 52526

## Log Locaties

### Mac
- App logs: `/tmp/macwincontrol.log` (als geconfigureerd)
- Console: Open Console.app → filter op "MacWinControl"

### Windows
- App logs: `C:\Users\<user>\AppData\Local\MacWinControl\logs\`
- Event Viewer: Windows Logs → Application
