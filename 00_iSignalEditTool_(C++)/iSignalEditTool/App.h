// App.h - iSignalEditTool Application Header
// ivrbDetect Solution
#pragma once

#include "iFileIO.h"

//=============================================================================
// EDIT MODE ENUMERATION
//=============================================================================

enum class EditMode {
    Inactive,   // No editing - no button selected
    None,       // Setting segments to 0 (None)
    Blood,      // Setting segments to 1 (Blood)
    Wall,       // Setting segments to 2 (Wall)
    Clot        // Setting segments to 3 (Clot)
};

enum class EditTarget {
    StateDet,   // Edit meta.stateDet
    StateTru    // Edit meta.stateTru
};

//=============================================================================
// APPLICATION STATE
//=============================================================================

struct AppState {
    // Data
    H5AData h5aData;
    
    // File state
    std::string currentFilePath;
    bool hasUnsavedChanges = false;
    
    // Edit target (stateDet or stateTru)
    EditTarget editTarget = EditTarget::StateDet;
    
    // Edit mode
    EditMode editMode = EditMode::Inactive;
    
    // Selection state for editing
    bool hasStartPoint = false;
    double startTime = 0.0;
    bool hasEndPoint = false;
    double endTime = 0.0;
    
    // Plot range preservation
    double xRangeMin = 0.0;
    double xRangeMax = 0.0;
    
    // Pending update (for 0.4s delay)
    bool pendingUpdate = false;
    double pendingUpdateTime = 0.0;
    
    // HDF5 Inspector
    HDF5FileInfo hdf5Info;
    bool showHDF5Inspector = false;
    
    // UI State
    bool dataTipEnabled = false;
    bool plotsNeedUpdate = false;
    bool showAboutDialog = false;
};

//=============================================================================
// INITIALIZATION
//=============================================================================

void InitializeAppState(AppState& state);

//=============================================================================
// RENDERING FUNCTIONS
//=============================================================================

// Main render function - calls all sub-renderers
void RenderMainWindow(AppState& state, bool& running);

// Menu bar
void RenderMenuBar(AppState& state, bool& running);

// Toolbar
void RenderToolbar(AppState& state);

// Plot area
void RenderPlots(AppState& state);

// Dialogs
void RenderAboutDialog(AppState& state);
void RenderHDF5Inspector(AppState& state);

//=============================================================================
// EDIT FUNCTIONS
//=============================================================================

// Utility to find index for a given time
size_t FindIndexForTime(const H5AData& data, double time);

// Apply the edit to stateDet based on start/end times
void ApplyEdit(AppState& state);

//=============================================================================
// PLOT STATE (external access for toolbar)
//=============================================================================

extern double g_xRangeMin;
extern double g_xRangeMax;
extern bool g_plotRangeInitialized;
