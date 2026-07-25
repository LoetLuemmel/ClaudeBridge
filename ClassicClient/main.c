/*
 * main.c
 * Claude Assistant for Classic Mac OS 7.5
 *
 * Main event loop and initialization
 *
 * Think C 7.0 Compatible Code
 */

#include "globals.h"

/* Global variables (defined here, declared extern in globals.h) */
WindowPtr    gMainWindow = NULL;
TEHandle     gInputTE = NULL;
TEHandle     gOutputTE = NULL;
Boolean      gDone = false;
EventRecord  gEvent;
short        gCurrentMode = kModeCode;
Boolean      gIsPolling = false;
long         gCurrentJobID = 0;
Str255       gServerIP = "\p127.0.0.1";
short        gServerPort = 8080;
Str255       gStatusText = "\pReady";

/*
 * main
 *
 * Entry point for the application
 */
void main(void)
{
    /* Initialize Toolbox */
    InitToolbox();

    /* Load preferences */
    LoadPreferences();

    /* Setup menus */
    SetupMenus();

    /* Update mode menu checkmarks */
    UpdateModeMenu();

    /* Create main window */
    CreateMainWindow();

    /* Main event loop */
    gDone = false;
    while (!gDone) {
        if (WaitNextEvent(everyEvent, &gEvent, 10, NULL)) {
            HandleEvent(&gEvent);
        }
    }

    /* Cleanup */
    if (gInputTE != NULL) {
        TEDispose(gInputTE);
    }
    if (gOutputTE != NULL) {
        TEDispose(gOutputTE);
    }
}

/*
 * InitToolbox
 *
 * Initialize Mac Toolbox managers
 */
void InitToolbox(void)
{
    /* Initialize QuickDraw */
    InitGraf(&qd.thePort);

    /* Initialize Font Manager */
    InitFonts();

    /* Initialize Window Manager */
    InitWindows();

    /* Initialize Menu Manager */
    InitMenus();

    /* Initialize TextEdit */
    TEInit();

    /* Initialize Dialog Manager */
    InitDialogs(NULL);

    /* Initialize Cursor */
    InitCursor();

    /* Set up more memory */
    MaxApplZone();
    MoreMasters();
    MoreMasters();
    MoreMasters();
}

/*
 * HandleEvent
 *
 * Dispatch events to appropriate handlers
 */
void HandleEvent(EventRecord *event)
{
    WindowPtr window;

    switch (event->what) {
        case mouseDown:
            HandleMouseDown(event);
            break;

        case keyDown:
        case autoKey:
            HandleKeyDown(event);
            break;

        case updateEvt:
            HandleUpdate(event);
            break;

        case activateEvt:
            HandleActivate(event);
            break;
    }
}

/*
 * HandleMouseDown
 *
 * Handle mouse down events
 */
void HandleMouseDown(EventRecord *event)
{
    WindowPtr window;
    short part;
    long menuChoice;
    Point localPt;
    short buttonID;

    part = FindWindow(event->where, &window);

    switch (part) {
        case inMenuBar:
            menuChoice = MenuSelect(event->where);
            HandleMenuChoice(menuChoice);
            break;

        case inSysWindow:
            SystemClick(event, window);
            break;

        case inDrag:
            if (window != NULL) {
                DragWindow(window, event->where, &qd.screenBits.bounds);
            }
            break;

        case inGoAway:
            if (window != NULL && TrackGoAway(window, event->where)) {
                gDone = true;
            }
            break;

        case inContent:
            if (window != NULL) {
                if (window != FrontWindow()) {
                    SelectWindow(window);
                } else {
                    /* Check if clicking in TextEdit */
                    localPt = event->where;
                    GlobalToLocal(&localPt);

                    /* Check if clicking buttons */
                    if (ButtonHit(localPt, &buttonID)) {
                        HandleButtonClick(buttonID);
                    }
                    /* Check if clicking in TextEdit */
                    else if (gInputTE != NULL && PtInRect(localPt, &(*gInputTE)->viewRect)) {
                        TEClick(localPt, (event->modifiers & shiftKey) != 0, gInputTE);
                    }
                    else if (gOutputTE != NULL && PtInRect(localPt, &(*gOutputTE)->viewRect)) {
                        TEClick(localPt, (event->modifiers & shiftKey) != 0, gOutputTE);
                    }
                }
            }
            break;
    }
}

/*
 * HandleKeyDown
 *
 * Handle keyboard events
 */
void HandleKeyDown(EventRecord *event)
{
    char key;
    long menuChoice;

    key = event->message & charCodeMask;

    /* Check for Command-key equivalents */
    if ((event->modifiers & cmdKey) != 0) {
        menuChoice = MenuKey(key);
        HandleMenuChoice(menuChoice);
    }
    /* Send to active TextEdit */
    else if (gInputTE != NULL && gMainWindow == FrontWindow()) {
        TEKey(key, gInputTE);
    }
}

/*
 * HandleUpdate
 *
 * Handle update events
 */
void HandleUpdate(EventRecord *event)
{
    WindowPtr window;
    GrafPtr savePort;

    window = (WindowPtr)event->message;

    GetPort(&savePort);
    SetPort(window);

    BeginUpdate(window);
    DrawWindow(window);
    EndUpdate(window);

    SetPort(savePort);
}

/*
 * HandleActivate
 *
 * Handle activate/deactivate events
 */
void HandleActivate(EventRecord *event)
{
    WindowPtr window;
    Boolean isActivating;

    window = (WindowPtr)event->message;
    isActivating = (event->modifiers & activeFlag) != 0;

    if (window == gMainWindow) {
        if (gInputTE != NULL) {
            TEActivate(gInputTE);
        }
    }
}

/*
 * HandleMenuChoice
 *
 * Handle menu selections
 */
void HandleMenuChoice(long menuChoice)
{
    short menu;
    short item;
    Str255 daName;

    if (menuChoice == 0) {
        return;
    }

    menu = HiWord(menuChoice);
    item = LoWord(menuChoice);

    switch (menu) {
        case mApple:
            if (item == iAbout) {
                DoAboutBox();
            } else {
                GetMenuItemText(GetMenuHandle(mApple), item, daName);
                OpenDeskAcc(daName);
            }
            break;

        case mFile:
            if (item == iPrefs) {
                ShowPreferencesDialog();
                UpdateModeMenu();  /* Update menu after prefs change */
            } else if (item == iQuit) {
                gDone = true;
            }
            break;

        case mEdit:
            if (item == iCopy) {
                CopyAnswerToClipboard();
            }
            break;

        case mCode:
            if (item == iSendToServer) {
                DoSendToServer();
            } else if (item >= iModeCode && item <= iModeChat) {
                /* Handle mode selection */
                gCurrentMode = item - iModeCode;
                UpdateModeMenu();
            }
            break;
    }

    HiliteMenu(0);
}

/*
 * DoAboutBox
 *
 * Display About dialog
 */
void DoAboutBox(void)
{
    DialogPtr dialog;
    short itemHit;

    dialog = GetNewDialog(rAboutDialog, NULL, (WindowPtr)-1);
    if (dialog != NULL) {
        ModalDialog(NULL, &itemHit);
        DisposDialog(dialog);
    }
}

/*
 * CopyAnswerToClipboard
 *
 * Copy output TextEdit to clipboard
 */
void CopyAnswerToClipboard(void)
{
    Handle textHandle;
    long textLen;
    OSErr err;

    if (gOutputTE == NULL) {
        return;
    }

    /* Get text from Output TextEdit */
    textHandle = TEGetText(gOutputTE);
    textLen = (*gOutputTE)->teLength;

    if (textLen == 0) {
        ShowStatus("\pNo text to copy");
        return;
    }

    /* Copy to clipboard */
    err = ZeroScrap();
    if (err == noErr) {
        HLock(textHandle);
        err = PutScrap(textLen, 'TEXT', *textHandle);
        HUnlock(textHandle);

        if (err == noErr) {
            ShowStatus("\pCopied to Clipboard!");
        } else {
            ShowStatus("\pCopy failed");
        }
    }
}

/*
 * HandleButtonClick
 *
 * Handle button clicks (1=Send, 2=Copy, 3=Save, 4=Clear)
 */
void HandleButtonClick(short buttonID)
{
    switch (buttonID) {
        case 1:  /* Send */
            DoSendToServer();
            break;

        case 2:  /* Copy */
            CopyAnswerToClipboard();
            break;

        case 3:  /* Save */
            DoSaveToFile();
            break;

        case 4:  /* Clear */
            DoClearAll();
            break;
    }
}

/*
 * DoSendToServer
 *
 * Send input text to Claude server
 */
void DoSendToServer(void)
{
    OSErr err;
    char *inputText;
    long inputLen;
    char jobID[64];
    Boolean isDone;
    Handle result;
    long startTime;
    long elapsedTicks;
    char statusMsg[256];
    char *modeStr;

    /* Get input text */
    err = GetTextFromTE(gInputTE, &inputText, &inputLen);
    if (err != noErr || inputLen == 0) {
        ShowStatus("\pPlease enter a question or code");
        if (inputText != NULL) {
            DisposPtr(inputText);
        }
        return;
    }

    /* Initialize network */
    err = InitNetwork();
    if (err != noErr) {
        ShowStatus("\pNetwork initialization failed");
        DisposPtr(inputText);
        return;
    }

    /* Determine mode string based on gCurrentMode */
    char *modeStr;
    switch (gCurrentMode) {
        case kModeCode:  modeStr = "code"; break;
        case kModeRez:   modeStr = "rez"; break;
        case kModeAsk:   modeStr = "ask"; break;
        case kModeChat:  modeStr = "chat"; break;
        default:         modeStr = "code"; break;
    }

    /* Send job request */
    ShowStatus("\pSending to Claude...");
    err = SendJobRequest(inputText, modeStr, jobID);
    DisposPtr(inputText);

    if (err != noErr) {
        ShowStatus("\pFailed to send request");
        return;
    }

    /* Poll for result */
    ShowStatus("\pClaude is working...");
    startTime = TickCount();
    isDone = false;
    result = NULL;

    while (!isDone && !gDone) {
        /* Process events to keep UI responsive */
        if (WaitNextEvent(everyEvent, &gEvent, 10, NULL)) {
            /* Don't handle full events during polling */
            /* Just check for Quit */
            if (gEvent.what == mouseDown) {
                WindowPtr window;
                short part;
                part = FindWindow(gEvent.where, &window);
                if (part == inGoAway && window == gMainWindow) {
                    if (TrackGoAway(window, gEvent.where)) {
                        gDone = true;
                        return;
                    }
                }
            }
        }

        /* Check job status every 2 seconds */
        elapsedTicks = TickCount() - startTime;
        if ((elapsedTicks % 120) == 0) {
            err = CheckJobStatus(jobID, &isDone, &result);
            if (err != noErr) {
                ShowStatus("\pError checking status");
                return;
            }

            /* Update status with elapsed time */
            sprintf(statusMsg, "Working... %ld sec", elapsedTicks / 60);
            c2pstr(statusMsg);
            ShowStatus((unsigned char*)statusMsg);
            p2cstr((unsigned char*)statusMsg);
        }

        /* Timeout after 3 minutes */
        if (elapsedTicks > kMaxJobWaitTime) {
            ShowStatus("\pRequest timed out");
            return;
        }
    }

    /* Display result */
    if (isDone && result != NULL) {
        HLock(result);
        SetTextInTE(gOutputTE, *result, strlen(*result));
        HUnlock(result);
        DisposHandle(result);

        ShowStatus("\pDone!");

        /* Redraw window */
        InvalRect(&gMainWindow->portRect);
    } else {
        ShowStatus("\pNo response received");
    }
}

/*
 * DoSaveToFile
 *
 * Save output text to file using StandardFile
 */
void DoSaveToFile(void)
{
    StandardFileReply reply;
    OSErr err;
    short refNum;
    long count;
    char *outputText;
    long outputLen;

    if (gOutputTE == NULL) {
        return;
    }

    /* Check if there's text to save */
    if ((*gOutputTE)->teLength == 0) {
        ShowStatus("\pNo text to save");
        return;
    }

    /* Get output text */
    err = GetTextFromTE(gOutputTE, &outputText, &outputLen);
    if (err != noErr) {
        ShowStatus("\pError reading text");
        return;
    }

    /* Show StandardFile dialog */
    StandardPutFile("\pSave Claude's answer as:", "\pClaudeOutput.txt", &reply);

    if (!reply.sfGood) {
        /* User cancelled */
        DisposPtr(outputText);
        return;
    }

    /* Create file */
    err = FSpCreate(&reply.sfFile, 'CWIE', 'TEXT', reply.sfScript);
    if (err != noErr && err != dupFNErr) {
        ShowStatus("\pCould not create file");
        DisposPtr(outputText);
        return;
    }

    /* Open file */
    err = FSpOpenDF(&reply.sfFile, fsWrPerm, &refNum);
    if (err != noErr) {
        ShowStatus("\pCould not open file");
        DisposPtr(outputText);
        return;
    }

    /* Write text to file */
    count = outputLen;
    err = FSWrite(refNum, &count, outputText);

    /* Close file */
    FSClose(refNum);

    /* Clean up */
    DisposPtr(outputText);

    if (err == noErr) {
        ShowStatus("\pFile saved!");
    } else {
        ShowStatus("\pError saving file");
    }
}

/*
 * DoClearAll
 *
 * Clear both input and output TextEdit controls
 */
void DoClearAll(void)
{
    ClearTE(gInputTE);
    ClearTE(gOutputTE);
    ShowStatus("\pCleared");

    /* Redraw window */
    if (gMainWindow != NULL) {
        InvalRect(&gMainWindow->portRect);
    }
}

/*
 * UpdateModeMenu
 *
 * Update checkmarks in Mode menu
 */
void UpdateModeMenu(void)
{
    MenuHandle modeMenu;
    short i;

    modeMenu = GetMenuHandle(mCode);
    if (modeMenu == NULL) {
        return;
    }

    /* Clear all checkmarks */
    for (i = iModeCode; i <= iModeChat; i++) {
        CheckMenuItem(modeMenu, i, false);
    }

    /* Set checkmark for current mode */
    CheckMenuItem(modeMenu, iModeCode + gCurrentMode, true);
}
