/*
 * ui.c
 * Claude Assistant for Classic Mac OS 7.5
 *
 * Window, Menu, TextEdit and UI management
 *
 * Think C 7.0 Compatible Code
 */

#include "globals.h"

/* Forward declarations for local functions */
static void CreateInputTextEdit(WindowPtr window);
static void CreateOutputTextEdit(WindowPtr window);
static void DrawStatusBar(void);

/*
 * SetupMenus
 *
 * Create and install menu bar
 */
void SetupMenus(void)
{
    MenuHandle menu;

    /* Apple Menu */
    menu = GetMenu(rAppleMenu);
    if (menu != NULL) {
        AppendResMenu(menu, 'DRVR');
        InsertMenu(menu, 0);
    }

    /* File Menu */
    menu = GetMenu(rFileMenu);
    if (menu != NULL) {
        InsertMenu(menu, 0);
    }

    /* Edit Menu */
    menu = GetMenu(rEditMenu);
    if (menu != NULL) {
        InsertMenu(menu, 0);
    }

    /* Code Menu */
    menu = GetMenu(rCodeMenu);
    if (menu != NULL) {
        InsertMenu(menu, 0);
    }

    DrawMenuBar();
}

/*
 * CreateMainWindow
 *
 * Create and show main window with TextEdit controls
 */
void CreateMainWindow(void)
{
    Rect bounds;
    GrafPtr savePort;

    /* Get the window from resources */
    gMainWindow = GetNewWindow(rMainWindow, NULL, (WindowPtr)-1);

    if (gMainWindow == NULL) {
        /* Error - could not create window */
        ExitToShell();
    }

    /* Set up port */
    GetPort(&savePort);
    SetPort(gMainWindow);

    /* Create TextEdit controls */
    CreateTextEditControls(gMainWindow);

    /* Show window */
    ShowWindow(gMainWindow);

    /* Restore port */
    SetPort(savePort);
}

/*
 * CreateTextEditControls
 *
 * Create input and output TextEdit controls
 */
void CreateTextEditControls(WindowPtr window)
{
    GrafPtr savePort;

    GetPort(&savePort);
    SetPort(window);

    /* Create Input TextEdit */
    CreateInputTextEdit(window);

    /* Create Output TextEdit */
    CreateOutputTextEdit(window);

    SetPort(savePort);
}

/*
 * CreateInputTextEdit (local function)
 *
 * Create editable input TextEdit
 */
static void CreateInputTextEdit(WindowPtr window)
{
    Rect destRect;
    Rect viewRect;

    /* Set up rectangles */
    SetRect(&destRect, kInputTELeft, kInputTETop, kInputTERight, kInputTEBottom);
    SetRect(&viewRect, kInputTELeft, kInputTETop, kInputTERight, kInputTEBottom);

    /* Create TextEdit */
    gInputTE = TENew(&destRect, &viewRect);

    if (gInputTE != NULL) {
        /* Set wrapping */
        (*gInputTE)->crOnly = -1;  /* Wrap at CR only */
    }
}

/*
 * CreateOutputTextEdit (local function)
 *
 * Create read-only output TextEdit
 */
static void CreateOutputTextEdit(WindowPtr window)
{
    Rect destRect;
    Rect viewRect;

    /* Set up rectangles */
    SetRect(&destRect, kOutputTELeft, kOutputTETop, kOutputTERight, kOutputTEBottom);
    SetRect(&viewRect, kOutputTELeft, kOutputTETop, kOutputTERight, kOutputTEBottom);

    /* Create TextEdit */
    gOutputTE = TENew(&destRect, &viewRect);

    if (gOutputTE != NULL) {
        /* Make read-only */
        (*gOutputTE)->crOnly = -1;  /* Wrap at CR only */
        /* Note: Read-only will be enforced in event handling */
    }
}

/*
 * DrawWindow
 *
 * Draw window contents (called on update)
 */
void DrawWindow(WindowPtr window)
{
    GrafPtr savePort;
    Rect r;
    Str255 modeLabel;

    GetPort(&savePort);
    SetPort(window);

    /* Erase window */
    EraseRect(&window->portRect);

    /* Draw mode indicator */
    MoveTo(kInputTELeft, 30);
    switch (gCurrentMode) {
        case kModeCode:  BlockMove("\pMode: Code Assistant", modeLabel, 21); break;
        case kModeRez:   BlockMove("\pMode: Resource Generator", modeLabel, 25); break;
        case kModeAsk:   BlockMove("\pMode: Ask & Answer", modeLabel, 20); break;
        case kModeChat:  BlockMove("\pMode: Chat", modeLabel, 12); break;
        default:         BlockMove("\pMode: Code", modeLabel, 11); break;
    }
    DrawString(modeLabel);

    /* Draw labels */
    MoveTo(kInputTELeft, kInputTETop - 5);
    DrawString("\pYour Question/Code:");

    MoveTo(kOutputTELeft, kOutputTETop - 5);
    DrawString("\pClaude's Answer:");

    /* Draw TextEdit frames */
    SetRect(&r, kInputTELeft - 1, kInputTETop - 1,
                kInputTERight + 1, kInputTEBottom + 1);
    FrameRect(&r);

    SetRect(&r, kOutputTELeft - 1, kOutputTETop - 1,
                kOutputTERight + 1, kOutputTEBottom + 1);
    FrameRect(&r);

    /* Update TextEdit contents */
    if (gInputTE != NULL) {
        UpdateTextEdit(gInputTE);
    }
    if (gOutputTE != NULL) {
        UpdateTextEdit(gOutputTE);
    }

    /* Draw buttons */
    DrawButtons();

    /* Draw status bar */
    DrawStatusBar();

    SetPort(savePort);
}

/*
 * UpdateTextEdit
 *
 * Update TextEdit display
 */
void UpdateTextEdit(TEHandle te)
{
    if (te != NULL) {
        TEUpdate(&(*te)->viewRect, te);
    }
}

/*
 * ShowStatus
 *
 * Update status bar text
 */
void ShowStatus(Str255 message)
{
    GrafPtr savePort;

    /* Copy to global status */
    BlockMove(message, gStatusText, message[0] + 1);

    /* Redraw status bar */
    if (gMainWindow != NULL) {
        GetPort(&savePort);
        SetPort(gMainWindow);
        DrawStatusBar();
        SetPort(savePort);
    }
}

/*
 * DrawStatusBar (local function)
 *
 * Draw status bar at bottom of window
 */
static void DrawStatusBar(void)
{
    Rect r;
    short windowWidth;

    /* Get window width */
    windowWidth = gMainWindow->portRect.right - gMainWindow->portRect.left;

    /* Erase status bar area */
    SetRect(&r, 0, kStatusBarTop, windowWidth, kStatusBarTop + kStatusBarHeight);
    EraseRect(&r);

    /* Draw separator line */
    MoveTo(0, kStatusBarTop);
    LineTo(windowWidth, kStatusBarTop);

    /* Draw status text */
    MoveTo(10, kStatusBarTop + 14);
    DrawString(gStatusText);
}

/*
 * DrawButtons
 *
 * Draw action buttons
 */
void DrawButtons(void)
{
    Rect r;

    /* Send Button */
    SetRect(&r, kSendButtonLeft, kButtonTop,
                kSendButtonLeft + kButtonWidth, kButtonTop + kButtonHeight);
    FrameRoundRect(&r, 8, 8);
    MoveTo(kSendButtonLeft + 30, kButtonTop + 14);
    DrawString("\pSend");

    /* Copy Button */
    SetRect(&r, kCopyButtonLeft, kButtonTop,
                kCopyButtonLeft + kButtonWidth, kButtonTop + kButtonHeight);
    FrameRoundRect(&r, 8, 8);
    MoveTo(kCopyButtonLeft + 30, kButtonTop + 14);
    DrawString("\pCopy");

    /* Save Button */
    SetRect(&r, kSaveButtonLeft, kButtonTop,
                kSaveButtonLeft + kButtonWidth, kButtonTop + kButtonHeight);
    FrameRoundRect(&r, 8, 8);
    MoveTo(kSaveButtonLeft + 30, kButtonTop + 14);
    DrawString("\pSave");

    /* Clear Button */
    SetRect(&r, kClearButtonLeft, kButtonTop,
                kClearButtonLeft + kButtonWidth, kButtonTop + kButtonHeight);
    FrameRoundRect(&r, 8, 8);
    MoveTo(kClearButtonLeft + 26, kButtonTop + 14);
    DrawString("\pClear");
}

/*
 * ButtonHit
 *
 * Check if point is in a button, return button ID
 */
Boolean ButtonHit(Point where, short *buttonID)
{
    Rect r;

    /* Send Button */
    SetRect(&r, kSendButtonLeft, kButtonTop,
                kSendButtonLeft + kButtonWidth, kButtonTop + kButtonHeight);
    if (PtInRect(where, &r)) {
        *buttonID = 1;  /* Send */
        return true;
    }

    /* Copy Button */
    SetRect(&r, kCopyButtonLeft, kButtonTop,
                kCopyButtonLeft + kButtonWidth, kButtonTop + kButtonHeight);
    if (PtInRect(where, &r)) {
        *buttonID = 2;  /* Copy */
        return true;
    }

    /* Save Button */
    SetRect(&r, kSaveButtonLeft, kButtonTop,
                kSaveButtonLeft + kButtonWidth, kButtonTop + kButtonHeight);
    if (PtInRect(where, &r)) {
        *buttonID = 3;  /* Save */
        return true;
    }

    /* Clear Button */
    SetRect(&r, kClearButtonLeft, kButtonTop,
                kClearButtonLeft + kButtonWidth, kButtonTop + kButtonHeight);
    if (PtInRect(where, &r)) {
        *buttonID = 4;  /* Clear */
        return true;
    }

    return false;
}
