/*
 * prefs.c
 * Claude Assistant for Classic Mac OS 7.5
 *
 * Preferences management
 *
 * Think C 7.0 Compatible Code
 */

#include "globals.h"
#include <String.h>
#include <Memory.h>

/* Preferences structure */
typedef struct {
    Str255 serverIP;
    short serverPort;
    short defaultMode;
    long version;  /* For future compatibility */
} Preferences;

/* Preferences file constants */
#define kPrefsFileName  "\pClaude Assistant Prefs"
#define kPrefsFileType  'PREF'
#define kPrefsCreator   'CLAU'
#define kPrefsVersion   1

/* Forward declarations */
static OSErr GetPrefsFile(FSSpec *spec, Boolean create);
static OSErr ReadPrefsFromFile(FSSpec *spec, Preferences *prefs);
static OSErr WritePrefsToFile(FSSpec *spec, Preferences *prefs);
static void SetDefaultPrefs(Preferences *prefs);
static Boolean ValidatePrefs(Preferences *prefs);

/*
 * LoadPreferences
 *
 * Load preferences from file or use defaults
 */
void LoadPreferences(void)
{
    OSErr err;
    FSSpec prefsFile;
    Preferences prefs;

    /* Try to find prefs file */
    err = GetPrefsFile(&prefsFile, false);
    if (err == noErr) {
        /* File exists, try to read it */
        err = ReadPrefsFromFile(&prefsFile, &prefs);
        if (err == noErr && ValidatePrefs(&prefs)) {
            /* Valid prefs, apply them */
            BlockMove(prefs.serverIP, gServerIP, prefs.serverIP[0] + 1);
            gServerPort = prefs.serverPort;
            gCurrentMode = prefs.defaultMode;
            return;
        }
    }

    /* No valid prefs found, use defaults */
    SetDefaultPrefs(&prefs);
    BlockMove(prefs.serverIP, gServerIP, prefs.serverIP[0] + 1);
    gServerPort = prefs.serverPort;
    gCurrentMode = prefs.defaultMode;

    /* Try to save defaults */
    err = GetPrefsFile(&prefsFile, true);
    if (err == noErr) {
        WritePrefsToFile(&prefsFile, &prefs);
    }
}

/*
 * SavePreferences
 *
 * Save current preferences to file
 */
void SavePreferences(void)
{
    OSErr err;
    FSSpec prefsFile;
    Preferences prefs;

    /* Build prefs from globals */
    BlockMove(gServerIP, prefs.serverIP, gServerIP[0] + 1);
    prefs.serverPort = gServerPort;
    prefs.defaultMode = gCurrentMode;
    prefs.version = kPrefsVersion;

    /* Get or create prefs file */
    err = GetPrefsFile(&prefsFile, true);
    if (err != noErr) {
        return;
    }

    /* Write to file */
    WritePrefsToFile(&prefsFile, &prefs);
}

/*
 * ShowPreferencesDialog
 *
 * Display preferences dialog and handle user input
 */
void ShowPreferencesDialog(void)
{
    DialogPtr dialog;
    short itemHit;
    Boolean done;
    Handle itemHandle;
    Rect itemRect;
    short itemType;
    Str255 ipString;
    Str255 portString;
    short newMode;
    long newPort;
    OSErr err;

    /* Get dialog from resources */
    dialog = GetNewDialog(rPrefsDialog, NULL, (WindowPtr)-1);
    if (dialog == NULL) {
        return;
    }

    /* Set current values */
    /* IP address (item 4) */
    GetDialogItem(dialog, 4, &itemType, &itemHandle, &itemRect);
    SetDialogItemText(itemHandle, gServerIP);

    /* Port (item 6) */
    sprintf((char*)portString, "%d", gServerPort);
    c2pstr((char*)portString);
    GetDialogItem(dialog, 6, &itemType, &itemHandle, &itemRect);
    SetDialogItemText(itemHandle, portString);

    /* Mode radio buttons (items 8, 9, 10) */
    GetDialogItem(dialog, 8 + gCurrentMode, &itemType, &itemHandle, &itemRect);
    SetControlValue((ControlHandle)itemHandle, 1);

    /* Show dialog and handle events */
    ShowWindow(dialog);
    done = false;

    while (!done) {
        ModalDialog(NULL, &itemHit);

        switch (itemHit) {
            case 1:  /* OK button */
                /* Get IP address */
                GetDialogItem(dialog, 4, &itemType, &itemHandle, &itemRect);
                GetDialogItemText(itemHandle, ipString);

                /* Get port */
                GetDialogItem(dialog, 6, &itemType, &itemHandle, &itemRect);
                GetDialogItemText(itemHandle, portString);
                p2cstr(portString);
                newPort = atoi((char*)portString);
                c2pstr((char*)portString);

                /* Validate */
                if (ipString[0] > 0 && newPort > 0 && newPort < 65536) {
                    /* Update globals */
                    BlockMove(ipString, gServerIP, ipString[0] + 1);
                    gServerPort = newPort;

                    /* Get selected mode */
                    GetDialogItem(dialog, 8, &itemType, &itemHandle, &itemRect);
                    if (GetControlValue((ControlHandle)itemHandle)) {
                        gCurrentMode = kModeCode;
                    }
                    GetDialogItem(dialog, 9, &itemType, &itemHandle, &itemRect);
                    if (GetControlValue((ControlHandle)itemHandle)) {
                        gCurrentMode = kModeRez;
                    }
                    GetDialogItem(dialog, 10, &itemType, &itemHandle, &itemRect);
                    if (GetControlValue((ControlHandle)itemHandle)) {
                        gCurrentMode = kModeAsk;
                    }

                    /* Save preferences */
                    SavePreferences();

                    done = true;
                } else {
                    /* Invalid input */
                    SysBeep(1);
                }
                break;

            case 2:  /* Cancel button */
                done = true;
                break;

            case 8:  /* Code radio */
            case 9:  /* Rez radio */
            case 10: /* Ask radio */
                /* Handle radio button */
                GetDialogItem(dialog, 8, &itemType, &itemHandle, &itemRect);
                SetControlValue((ControlHandle)itemHandle, (itemHit == 8) ? 1 : 0);
                GetDialogItem(dialog, 9, &itemType, &itemHandle, &itemRect);
                SetControlValue((ControlHandle)itemHandle, (itemHit == 9) ? 1 : 0);
                GetDialogItem(dialog, 10, &itemType, &itemHandle, &itemRect);
                SetControlValue((ControlHandle)itemHandle, (itemHit == 10) ? 1 : 0);
                break;
        }
    }

    DisposDialog(dialog);
}

/*
 * GetPrefsFile (local function)
 *
 * Get FSSpec for preferences file
 */
static OSErr GetPrefsFile(FSSpec *spec, Boolean create)
{
    OSErr err;
    short prefVRefNum;
    long prefDirID;

    /* Find Preferences folder */
    err = FindFolder(kOnSystemDisk, kPreferencesFolderType, kCreateFolder,
                     &prefVRefNum, &prefDirID);
    if (err != noErr) {
        return err;
    }

    /* Make FSSpec for prefs file */
    err = FSMakeFSSpec(prefVRefNum, prefDirID, kPrefsFileName, spec);

    if (err == fnfErr && create) {
        /* File doesn't exist but we want to create it */
        err = FSpCreate(spec, kPrefsCreator, kPrefsFileType, smSystemScript);
    }

    return err;
}

/*
 * ReadPrefsFromFile (local function)
 *
 * Read preferences from file
 */
static OSErr ReadPrefsFromFile(FSSpec *spec, Preferences *prefs)
{
    OSErr err;
    short refNum;
    long count;

    /* Open file */
    err = FSpOpenDF(spec, fsRdPerm, &refNum);
    if (err != noErr) {
        return err;
    }

    /* Read prefs */
    count = sizeof(Preferences);
    err = FSRead(refNum, &count, prefs);

    /* Close file */
    FSClose(refNum);

    return err;
}

/*
 * WritePrefsToFile (local function)
 *
 * Write preferences to file
 */
static OSErr WritePrefsToFile(FSSpec *spec, Preferences *prefs)
{
    OSErr err;
    short refNum;
    long count;

    /* Delete old file if it exists */
    FSpDelete(spec);

    /* Create new file */
    err = FSpCreate(spec, kPrefsCreator, kPrefsFileType, smSystemScript);
    if (err != noErr) {
        return err;
    }

    /* Open file */
    err = FSpOpenDF(spec, fsWrPerm, &refNum);
    if (err != noErr) {
        return err;
    }

    /* Write prefs */
    count = sizeof(Preferences);
    err = FSWrite(refNum, &count, prefs);

    /* Close file */
    FSClose(refNum);

    return err;
}

/*
 * SetDefaultPrefs (local function)
 *
 * Set default preferences
 */
static void SetDefaultPrefs(Preferences *prefs)
{
    /* Default server IP */
    prefs->serverIP[0] = strlen(kDefaultServerIP);
    BlockMove(kDefaultServerIP, &prefs->serverIP[1], prefs->serverIP[0]);

    /* Default port */
    prefs->serverPort = kDefaultServerPort;

    /* Default mode */
    prefs->defaultMode = kModeCode;

    /* Version */
    prefs->version = kPrefsVersion;
}

/*
 * ValidatePrefs (local function)
 *
 * Validate preferences structure
 */
static Boolean ValidatePrefs(Preferences *prefs)
{
    /* Check version */
    if (prefs->version != kPrefsVersion) {
        return false;
    }

    /* Check IP string length */
    if (prefs->serverIP[0] < 7 || prefs->serverIP[0] > 15) {
        return false;  /* Invalid IP length */
    }

    /* Check port range */
    if (prefs->serverPort < 1 || prefs->serverPort > 65535) {
        return false;
    }

    /* Check mode */
    if (prefs->defaultMode < kModeCode || prefs->defaultMode > kModeChat) {
        return false;
    }

    return true;
}
