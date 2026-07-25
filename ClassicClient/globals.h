/*
 * globals.h
 * Claude Assistant for Classic Mac OS 7.5
 *
 * Global definitions and shared variables
 *
 * CRITICAL - Think C 7.0 Requirements:
 * - NO // comments (only /* */)
 * - Declare variables at start of functions
 * - Pascal strings for UI
 * - Handle-based memory management
 */

#ifndef GLOBALS_H
#define GLOBALS_H

#include <Types.h>
#include <QuickDraw.h>
#include <Windows.h>
#include <Menus.h>
#include <TextEdit.h>
#include <Dialogs.h>
#include <Events.h>
#include <Controls.h>
#include <Files.h>
#include <Scrap.h>
#include <StandardFile.h>

/* Resource IDs */
#define rMenuBar          128
#define rAppleMenu        128
#define rFileMenu         129
#define rEditMenu         130
#define rCodeMenu         131

#define mApple            128
#define mFile             129
#define mEdit             130
#define mCode             131

/* Menu item indices */
#define iAbout            1   /* Apple menu */
#define iPrefs            1   /* File menu */
#define iQuit             2   /* File menu */
#define iCopy             1   /* Edit menu */
#define iSendToServer     1   /* Code menu */
#define iModeCode         2   /* Code menu */
#define iModeRez          3   /* Code menu */
#define iModeAsk          4   /* Code menu */
#define iModeChat         5   /* Code menu */

#define rMainWindow       128
#define rAboutDialog      128
#define rPrefsDialog      129
#define rErrorAlert       130

/* Mode constants */
#define kModeCode         0
#define kModeRez          1
#define kModeAsk          2
#define kModeChat         3

/* Network constants */
#define kDefaultServerIP  "127.0.0.1"
#define kDefaultServerPort 8080
#define kMaxResponseSize  32768L   /* 32 KB max response */
#define kPollInterval     120      /* Ticks (2 seconds) */
#define kMaxJobWaitTime   10800    /* Ticks (3 minutes) */

/* UI constants */
#define kInputTETop       50
#define kInputTELeft      10
#define kInputTEBottom    150
#define kInputTERight     590

#define kOutputTETop      170
#define kOutputTELeft     10
#define kOutputTEBottom   370
#define kOutputTERight    590

#define kButtonTop        380
#define kSendButtonLeft   10
#define kCopyButtonLeft   120
#define kSaveButtonLeft   230
#define kClearButtonLeft  340
#define kButtonWidth      100
#define kButtonHeight     20

#define kStatusBarTop     410
#define kStatusBarHeight  20

/* Global variables */
extern WindowPtr    gMainWindow;
extern TEHandle     gInputTE;
extern TEHandle     gOutputTE;
extern Boolean      gDone;
extern EventRecord  gEvent;
extern short        gCurrentMode;
extern Boolean      gIsPolling;
extern long         gCurrentJobID;
extern Str255       gServerIP;
extern short        gServerPort;
extern Str255       gStatusText;

/* Function prototypes - main.c */
void InitToolbox(void);
void HandleEvent(EventRecord *event);
void HandleMouseDown(EventRecord *event);
void HandleKeyDown(EventRecord *event);
void HandleUpdate(EventRecord *event);
void HandleActivate(EventRecord *event);
void HandleMenuChoice(long menuChoice);
void DoAboutBox(void);
void HandleButtonClick(short buttonID);
void DoSendToServer(void);
void DoSaveToFile(void);
void DoClearAll(void);
void CopyAnswerToClipboard(void);
void UpdateModeMenu(void);

/* Function prototypes - ui.c */
void SetupMenus(void);
void CreateMainWindow(void);
void CreateTextEditControls(WindowPtr window);
void DrawWindow(WindowPtr window);
void UpdateTextEdit(TEHandle te);
void ShowStatus(Str255 message);
void DrawButtons(void);
Boolean ButtonHit(Point where, short *buttonID);

/* Function prototypes - network.c (Phase 2) */
OSErr SendJobRequest(char *prompt, char *mode, char *jobID);
OSErr CheckJobStatus(char *jobID, Boolean *isDone, Handle *result);
OSErr GetTextFromTE(TEHandle te, char **text, long *length);
void SetTextInTE(TEHandle te, char *text, long length);
void ClearTE(TEHandle te);

/* Function prototypes - prefs.c (Phase 3) */
void ShowPreferencesDialog(void);
void LoadPreferences(void);
void SavePreferences(void);

#endif /* GLOBALS_H */
