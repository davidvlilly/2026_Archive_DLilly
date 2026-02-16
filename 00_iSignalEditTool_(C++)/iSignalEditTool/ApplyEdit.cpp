// Utility implementation for finding time index
#include "App.h"
#include <algorithm>
#include <cmath>

size_t FindIndexForTime(const H5AData& data, double time) {
    if (data.time.empty()) return 0;

    // Find the closest index to the given time
    auto it = std::lower_bound(data.time.begin(), data.time.end(), time);
    
    // If time is beyond the last sample, return last index
    if (it == data.time.end()) {
        return data.time.size() - 1;
    }

    // Calculate which index is closer
    size_t index = std::distance(data.time.begin(), it);
    
    // Prevent out-of-bounds access
    return std::min(index, data.time.size() - 1);
}

// Update ApplyEdit function in this file as well
void ApplyEdit(AppState& state) {
    if (!state.hasStartPoint || !state.hasEndPoint) return;

    // Find indices corresponding to start and end times
    size_t startIndex = FindIndexForTime(state.h5aData, state.startTime);
    size_t endIndex = FindIndexForTime(state.h5aData, state.endTime);

    // Update state detection data
    if (state.editTarget == EditTarget::StateDet) {
        for (size_t i = startIndex; i <= endIndex; ++i) {
            switch (state.editMode) {
                case EditMode::None:   state.h5aData.stateDet[i] = 0; break;
                case EditMode::Blood:  state.h5aData.stateDet[i] = 1; break;
                case EditMode::Wall:   state.h5aData.stateDet[i] = 2; break;
                case EditMode::Clot:   state.h5aData.stateDet[i] = 3; break;
                default: break;
            }
        }
    }

    // Preserve existing plot range if initialized
    if (g_plotRangeInitialized) {
        state.xRangeMin = g_xRangeMin;
        state.xRangeMax = g_xRangeMax;
    }

    // Mark plots for update without rescaling
    state.plotsNeedUpdate = true;
    state.hasUnsavedChanges = true;

    // Reset selection points
    state.hasStartPoint = false;
    state.hasEndPoint = false;
}
