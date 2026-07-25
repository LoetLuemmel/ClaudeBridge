/*
 * ClaudeAssistant.r
 * Claude Assistant for Classic Mac OS 7.5
 *
 * Rez resource definitions
 *
 * Compile with: Rez ClaudeAssistant.r -o ClaudeAssistant
 */

#include "Types.r"
#include "SysTypes.r"

/* Main Window */
resource 'WIND' (128, "Main Window", purgeable) {
    {50, 50, 480, 650},     /* top, left, bottom, right */
    documentProc,            /* Window type */
    visible,                 /* Visible */
    goAway,                  /* Has close box */
    0x0,                     /* RefCon */
    "Claude Assistant",      /* Title */
    centerMainScreen         /* Position */
};

/* Menu Bar */
resource 'MBAR' (128, preload) {
    { 128, 129, 130, 131 }  /* Menu IDs: Apple, File, Edit, Code */
};

/* Apple Menu */
resource 'MENU' (128, "Apple Menu", preload) {
    128,                     /* Menu ID */
    textMenuProc,            /* Menu type */
    0b1111111111111111111111111111101,  /* Enable flags (all but item 1) */
    enabled,                 /* Whole menu enabled */
    apple,                   /* Title (Apple symbol) */
    {
        "About Claude Assistant...",
            noIcon, noKey, noMark, plain,
        "-",
            noIcon, noKey, noMark, plain
    }
};

/* File Menu */
resource 'MENU' (129, "File Menu", preload) {
    129,                     /* Menu ID */
    textMenuProc,
    0b1111111111111111111111111111111,  /* All items enabled */
    enabled,
    "File",
    {
        "Preferences...",
            noIcon, noKey, noMark, plain,
        "-",
            noIcon, noKey, noMark, plain,
        "Quit",
            noIcon, "Q", noMark, plain
    }
};

/* Edit Menu */
resource 'MENU' (130, "Edit Menu", preload) {
    130,                     /* Menu ID */
    textMenuProc,
    0b1111111111111111111111111111111,
    enabled,
    "Edit",
    {
        "Copy Answer",
            noIcon, "C", noMark, plain
    }
};

/* Code Menu */
resource 'MENU' (131, "Code Menu", preload) {
    131,                     /* Menu ID */
    textMenuProc,
    0b1111111111111111111111111111111,
    enabled,
    "Mode",
    {
        "Send to Server",
            noIcon, "S", noMark, plain,
        "-",
            noIcon, noKey, noMark, plain,
        "Code Mode",
            noIcon, noKey, check, plain,
        "Rez Mode",
            noIcon, noKey, noMark, plain,
        "Ask Mode",
            noIcon, noKey, noMark, plain,
        "Chat Mode",
            noIcon, noKey, noMark, plain
    }
};

/* About Dialog */
resource 'DLOG' (128, "About Dialog", purgeable) {
    {100, 100, 250, 450},    /* top, left, bottom, right */
    dBoxProc,                /* Dialog type */
    visible,
    noGoAway,
    0x0,
    128,                     /* DITL ID */
    "About",
    centerMainScreen
};

/* About Dialog Item List */
resource 'DITL' (128, "About DITL", purgeable) {
    {
        /* OK Button */
        {120, 130, 140, 220},
        Button {
            enabled,
            "OK"
        },

        /* Icon */
        {10, 20, 42, 52},
        Icon {
            disabled,
            1
        },

        /* Title */
        {10, 60, 30, 340},
        StaticText {
            disabled,
            "Claude Assistant for Mac OS 7.5"
        },

        /* Version */
        {35, 60, 50, 340},
        StaticText {
            disabled,
            "Version 1.0 - Think C Edition"
        },

        /* Copyright */
        {55, 60, 70, 340},
        StaticText {
            disabled,
            "Connects to Claude AI via AppleBridge"
        },

        /* Info */
        {75, 60, 105, 340},
        StaticText {
            disabled,
            "A native Mac application for code assistance, resource generation, and AI chat."
        }
    }
};

/* Preferences Dialog */
resource 'DLOG' (129, "Preferences Dialog", purgeable) {
    {100, 100, 280, 450},
    dBoxProc,
    visible,
    noGoAway,
    0x0,
    129,                     /* DITL ID */
    "Preferences",
    centerMainScreen
};

/* Preferences Dialog Item List */
resource 'DITL' (129, "Preferences DITL", purgeable) {
    {
        /* OK Button */
        {150, 180, 170, 260},
        Button {
            enabled,
            "OK"
        },

        /* Cancel Button */
        {150, 90, 170, 170},
        Button {
            enabled,
            "Cancel"
        },

        /* Server IP Label */
        {20, 20, 35, 120},
        StaticText {
            disabled,
            "Server IP:"
        },

        /* Server IP Edit Text */
        {20, 130, 36, 330},
        EditText {
            enabled,
            "127.0.0.1"
        },

        /* Server Port Label */
        {50, 20, 65, 120},
        StaticText {
            disabled,
            "Server Port:"
        },

        /* Server Port Edit Text */
        {50, 130, 66, 200},
        EditText {
            enabled,
            "8080"
        },

        /* Mode Label */
        {80, 20, 95, 120},
        StaticText {
            disabled,
            "Default Mode:"
        },

        /* Mode Radio: Code */
        {80, 130, 96, 200},
        RadioButton {
            enabled,
            "Code"
        },

        /* Mode Radio: Rez */
        {100, 130, 116, 200},
        RadioButton {
            enabled,
            "Rez"
        },

        /* Mode Radio: Ask */
        {120, 130, 136, 200},
        RadioButton {
            enabled,
            "Ask"
        }
    }
};

/* Error Alert */
resource 'ALRT' (130, "Error Alert", purgeable) {
    {100, 100, 200, 400},
    130,                     /* DITL ID */
    {
        OK, visible, silent,
        OK, visible, silent,
        OK, visible, silent,
        OK, visible, silent
    },
    centerMainScreen
};

/* Error Alert Item List */
resource 'DITL' (130, "Error DITL", purgeable) {
    {
        /* OK Button */
        {70, 110, 90, 190},
        Button {
            enabled,
            "OK"
        },

        /* Error Icon */
        {10, 20, 42, 52},
        Icon {
            disabled,
            2  /* Stop icon */
        },

        /* Error Message */
        {10, 60, 60, 290},
        StaticText {
            disabled,
            "^0"  /* Parameterized text */
        }
    }
};

/* Application Icon (ICN#) */
resource 'ICN#' (128, purgeable) {
    {
        /* Icon bitmap (32x32) */
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000",

        /* Mask */
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
        $"00000000 00000000 00000000 00000000"
    }
};

/* Signature (for Finder) */
type 'CLAS' as 'STR ';

resource 'CLAS' (0) {
    "Claude Assistant"
};

/* Version String */
resource 'vers' (1, purgeable) {
    0x01,               /* Major version */
    0x00,               /* Minor version */
    release,            /* Release stage */
    0x00,               /* Non-final version */
    verUS,              /* Region code */
    "1.0",              /* Short version string */
    "1.0, © 2025 Claude Assistant for Classic Mac"  /* Long version string */
};

/* Bundle - File type associations */
resource 'BNDL' (128, purgeable) {
    'CLAU',             /* Signature */
    0,                  /* Resource ID */
    {
        'ICN#',         /* Icon family */
        {
            0, 128      /* Local ID, Actual ID */
        },
        'FREF',         /* File reference */
        {
            0, 128      /* Local ID, Actual ID */
        }
    }
};

/* File Reference */
resource 'FREF' (128, purgeable) {
    'APPL',             /* File type */
    0,                  /* Icon local ID */
    ""                  /* File name (empty = use default) */
};

/* Size Resource - Memory allocation */
resource 'SIZE' (-1, purgeable) {
    reserved,
    acceptSuspendResumeEvents,
    reserved,
    canBackground,
    doesActivateOnFGSwitch,
    backgroundAndForeground,
    dontGetFrontClicks,
    ignoreAppDiedEvents,
    is32BitCompatible,
    notHighLevelEventAware,
    onlyLocalHLEvents,
    notStationeryAware,
    dontUseTextEditServices,
    reserved,
    reserved,
    reserved,
    512 * 1024,         /* Preferred size: 512 KB */
    256 * 1024          /* Minimum size: 256 KB */
};
