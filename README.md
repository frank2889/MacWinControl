# MacWinControl 🖥️🔗💻

Bedien je Windows PC met je Mac muis en toetsenbord! Net als Synergy/Barrier, maar simpeler.

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
│   ├── MacWinControl.app/    ← Dubbelklik deze!
│   └── MacWinControlApp.py   ← Python source
├── WindowsApp/
│   ├── MacWinControlClient/  ← Windows project
│   └── WindowsApp.sln
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
