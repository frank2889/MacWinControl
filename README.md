# MacWinControl 2.0 🖥️🔗💻

Bedien je Windows PC met je Mac muis en toetsenbord – en andersom! Net als Synergy, maar gratis.

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows-lightgrey)

## ✨ Features

- 🖱️ **Naadloze Muisbesturing** – Muis vloeit tussen Mac en Windows
- ⌨️ **Gedeeld Toetsenbord** – Typ op beide machines met één toetsenbord
- 📋 **Clipboard Sync** – Kopieer op Mac, plak op Windows (en andersom!)
- 🔄 **Bidirectioneel** – Besturing werkt beide kanten op
- ⌘ **Key Swapping** – ⌘ Command ↔ ⊞ Windows key mapping
- 🎨 **Moderne UI** – Strakke, uniforme interface op beide platformen

## 🎯 Wat doet het?

MacWinControl laat je naadloos je muis van je Mac schermen naar je Windows schermen bewegen. Wanneer je muis de rand van je Mac scherm verlaat, neemt de Mac app de controle over en stuurt alle muis- en toetsenbordbewegingen door naar de Windows computer.

```
┌─────────────────────────────┐                    ┌─────────────────────────────┐
│         MAC                 │      WiFi          │        WINDOWS              │
│  ┌─────────┐ ┌─────────┐   │  ◄───────────►     │  ┌─────────┐ ┌─────────┐   │
│  │ Scherm 1│ │ Scherm 2│   │   Mouse/Keys       │  │ Scherm 1│ │ Scherm 2│   │
│  └─────────┘ └─────────┘   │                    │  └─────────┘ └─────────┘   │
│        🖱️ ──────────────────────────────────────────► 🖱️                     │
└─────────────────────────────┘                    └─────────────────────────────┘
```

## 🍎 Mac Installatie

### Simpel (geen Xcode nodig!)

1. **Open de app**: Dubbelklik op `MacApp/MacWinControl.app`
2. **Geef permissies**: Klik "Ja" als gevraagd wordt om Accessibility toegang
3. **Noteer het IP adres** dat in de app staat

> ⚠️ Als de app niet opent, rechtermuisklik → "Open" om Gatekeeper te omzeilen

### Accessibility Permissies

De app heeft toegang nodig om je muis/toetsenbord te kunnen doorsturen:
1. Open **Systeemvoorkeuren** → **Privacy & Beveiliging** → **Toegankelijkheid**
2. Voeg **MacWinControl** toe en zet het aan

## 🪟 Windows Installatie

### Vereisten
- Windows 10/11
- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)

### Stappen

1. Open PowerShell of Command Prompt
2. Run:

```powershell
cd WindowsApp
dotnet run --project MacWinControlClient
```

3. Voer het IP adres van je Mac in en klik "Verbinden"

### Bouwen als standalone .exe

```powershell
cd WindowsApp
dotnet publish -c Release -r win-x64 --self-contained
```

De .exe staat dan in: `bin/Release/net8.0-windows/win-x64/publish/`

## 🎮 Gebruik

1. **Start de Mac app** - Dubbelklik op MacWinControl.app
2. **Start de Windows app** - Run `dotnet run` of de .exe
3. **Verbind** - Voer Mac's IP adres in op Windows en klik Verbinden
4. **Klaar!** - Beweeg je muis naar de rand om naar Windows te gaan

### Sneltoetsen

- `Ctrl+Alt+M` - Terug naar Mac

### Schermen Rangschikken

Klik "Schermen Rangschikken" in de Mac app om de Windows schermen naar de juiste positie te slepen (links, rechts, boven of onder je Mac schermen).

## 🔧 Troubleshooting

### Mac

- **App start niet**: Rechtermuisklik → Open
- **Muis werkt niet**: Check Accessibility in Systeemvoorkeuren
- **Poort in gebruik**: `lsof -ti:52525 | xargs kill -9`

### Windows

- **Verbinden mislukt**: Check of beide computers op hetzelfde WiFi zitten
- **dotnet niet gevonden**: Installeer .NET 8 SDK
- **Firewall blokkade**: Sta poort 52525 toe

## 📁 Projectstructuur

```text
MacWinControl/
├── MacApp/
│   ├── app_v2.py             ← Moderne Mac GUI app
│   ├── bridge3.py            ← Standalone bridge (geen GUI)
│   └── clipboard_manager.py  ← Clipboard sync
├── WindowsApp/
│   └── MacWinControlClient/
│       ├── MainWindow_v2.xaml      ← Moderne Windows UI
│       ├── BridgeController.cs     ← Hoofd control logic
│       ├── InputHookManager.cs     ← Muis/toetsenbord hooks
│       ├── EdgeDetector.cs         ← Schermrand detectie
│       ├── ClipboardManager.cs     ← Clipboard sync
│       └── Protocol.cs             ← Netwerk protocol
├── shared/
│   ├── design_system.py      ← Uniforme kleuren/fonts
│   └── protocol.py           ← Message definities
└── README.md
```

## 🔒 Privacy

- Alle communicatie is lokaal via je WiFi
- Er worden geen gegevens naar het internet gestuurd
- Alleen muis/toetsenbord events worden doorgestuurd

## 📝 Licentie

MIT License

---

Gemaakt met ❤️ voor productiviteit tussen platforms.
