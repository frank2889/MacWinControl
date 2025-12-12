"""
py2app setup for MacWinControl
"""
from setuptools import setup

APP = ['simple_server.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'plist': {
        'CFBundleName': 'MacWinControl',
        'CFBundleDisplayName': 'MacWinControl',
        'CFBundleIdentifier': 'com.macwincontrol.app',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHighResolutionCapable': True,
        'NSAccessibilityUsageDescription': 'MacWinControl needs accessibility access to capture mouse and keyboard input.',
        'LSUIElement': False,
    },
    'packages': ['pynput'],
    'includes': ['pynput', 'pynput.mouse', 'pynput.keyboard', 'AppKit'],
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
