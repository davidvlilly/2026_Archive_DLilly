// App.cpp - iSignalEditTool Application Implementation
// ivrbDetect Solution

#include "App.h"
#include "imgui.h"
#include "implot.h"
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>
#include <algorithm>
#include <cmath>
#include <chrono>
#include <cfloat>

//=============================================================================
// PLOT STATE
//=============================================================================

double g_xRangeMin = 0.0;
double g_xRangeMax = 10.0;
bool g_plotRangeInitialized = false;

// Y-axis state
static double g_yRangeMin = -1.0;
static double g_yRangeMax = 1.0;

// Time tracking for pending updates
static std::chrono::steady_clock::time_point g_pendingStartTime;

//=============================================================================
// CONSTANTS
//=============================================================================

static const float LINE_THICKNESS = 1.5f;
static const float DOT_SIZE = 3.0f;
static const double VISIBLE_RANGE_FOR_DOTS = 20.0;
static const double PENDING_UPDATE_DELAY = 0.4;  // seconds

//=============================================================================
// INITIALIZATION
//=============================================================================

void InitializeAppState(AppState& state) {
    state.h5aData.Clear();
    state.currentFilePath.clear();
    state.hasUnsavedChanges = false;
    state.editMode = EditMode::Inactive;
    state.hasStartPoint = false;
    state.startTime = 0.0;
    state.hasEndPoint = false;
    state.endTime = 0.0;
    state.pendingUpdate = false;
    state.pendingUpdateTime = 0.0;
    state.hdf5Info.datasets.clear();
    state.hdf5Info.isValid = false;
    state.showHDF5Inspector = false;
    state.dataTipEnabled = false;
    state.plotsNeedUpdate = false;
    state.showAboutDialog = false;
}

//=============================================================================
// MAIN RENDER
//=============================================================================

void RenderMainWindow(AppState& state, bool& running) {
    // Check for pending update timeout
    if (state.pendingUpdate) {
        auto now = std::chrono::steady_clock::now();
        double elapsed = std::chrono::duration<double>(now - g_pendingStartTime).count();
        if (elapsed >= PENDING_UPDATE_DELAY) {
            ApplyEdit(state);
            state.pendingUpdate = false;
            state.hasStartPoint = false;
            state.hasEndPoint = false;
            state.plotsNeedUpdate = true;
        }
    }
    
    RenderMenuBar(state, running);
    RenderToolbar(state);
    RenderPlots(state);
    
    if (state.showAboutDialog) {
        RenderAboutDialog(state);
    }
    
    if (state.showHDF5Inspector) {
        RenderHDF5Inspector(state);
    }
}

//=============================================================================
// MENU BAR
//=============================================================================

void RenderMenuBar(AppState& state, bool& running) {
    // Increase menu bar height
    ImGui::PushStyleVar(ImGuiStyleVar_FramePadding, ImVec2(8, 8));
    
    if (ImGui::BeginMainMenuBar()) {
        ImGui::SetWindowFontScale(1.3f);  // 30% larger menu text
        
        // File Menu
        if (ImGui::BeginMenu("File")) {
            if (ImGui::MenuItem("Open", "Ctrl+O")) {
                std::string filepath = ShowOpenFileDialog(
                    "H5A Files (*.h5a)\0*.h5a\0All Files\0*.*\0");
                if (!filepath.empty()) {
                    if (LoadH5AFile(filepath, state.h5aData)) {
                        state.currentFilePath = filepath;
                        state.hasUnsavedChanges = false;
                        state.hasStartPoint = false;
                        state.hasEndPoint = false;
                        state.pendingUpdate = false;
                        state.plotsNeedUpdate = true;
                        g_plotRangeInitialized = false;
                    }
                }
            }
            
            ImGui::Separator();
            
            bool canSave = state.h5aData.isLoaded && !state.currentFilePath.empty();
            if (ImGui::MenuItem("Save", "Ctrl+S", false, canSave)) {
                if (SaveH5AFileFromData(state.currentFilePath, state.h5aData)) {
                    state.hasUnsavedChanges = false;
                }
            }
            
            bool canSaveAs = state.h5aData.isLoaded;
            if (ImGui::MenuItem("Save As...", "Ctrl+Shift+S", false, canSaveAs)) {
                std::string defaultName = state.h5aData.caseName + ".h5a";
                std::string filepath = ShowSaveFileDialog(
                    "H5A Files (*.h5a)\0*.h5a\0All Files\0*.*\0", defaultName);
                if (!filepath.empty()) {
                    if (SaveH5AFileFromData(filepath, state.h5aData)) {
                        state.currentFilePath = filepath;
                        state.hasUnsavedChanges = false;
                    }
                }
            }
            
            ImGui::Separator();
            
            if (ImGui::MenuItem("Exit", "Alt+F4")) {
                running = false;
            }
            
            ImGui::EndMenu();
        }
        
        // Select Menu
        if (ImGui::BeginMenu("Select")) {
            bool isStateDet = (state.editTarget == EditTarget::StateDet);
            bool isStateTru = (state.editTarget == EditTarget::StateTru);
            
            if (ImGui::MenuItem("meta.stateDet", nullptr, isStateDet)) {
                state.editTarget = EditTarget::StateDet;
            }
            if (ImGui::MenuItem("meta.stateTru", nullptr, isStateTru)) {
                state.editTarget = EditTarget::StateTru;
            }
            
            ImGui::EndMenu();
        }
        
        // Misc Menu
        if (ImGui::BeginMenu("Misc")) {
            if (ImGui::MenuItem("Show HDF5 Structure", nullptr, false, state.h5aData.isLoaded)) {
                if (!state.currentFilePath.empty()) {
                    if (InspectHDF5File(state.currentFilePath, state.hdf5Info)) {
                        state.showHDF5Inspector = true;
                    }
                }
            }
            
            ImGui::Separator();
            
            if (ImGui::MenuItem("Swap Det/Tru", nullptr, false, state.h5aData.isLoaded)) {
                // Swap the contents of stateDet and stateTru
                std::swap(state.h5aData.stateDet, state.h5aData.stateTru);
                state.hasUnsavedChanges = true;
            }
            
            ImGui::Separator();
            
            if (ImGui::MenuItem("About...")) {
                state.showAboutDialog = true;
            }
            
            ImGui::EndMenu();
        }
        
        ImGui::EndMainMenuBar();
    }
    
    ImGui::PopStyleVar();
}

//=============================================================================
// TOOLBAR
//=============================================================================

void RenderToolbar(AppState& state) {
    ImGuiIO& io = ImGui::GetIO();
    
    // Position toolbar below menu bar (account for increased menu bar padding)
    float menuBarHeight = ImGui::GetFrameHeight() + 8;  // Extra padding for larger menu bar
    ImGui::SetNextWindowPos(ImVec2(0, menuBarHeight));
    ImGui::SetNextWindowSize(ImVec2(io.DisplaySize.x, 36));  // Increased by 2 more
    
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(8, 4));
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(8, 4));
    
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar | 
                             ImGuiWindowFlags_NoResize | 
                             ImGuiWindowFlags_NoMove |
                             ImGuiWindowFlags_NoScrollbar |
                             ImGuiWindowFlags_NoSavedSettings;
    
    if (ImGui::Begin("##Toolbar", nullptr, flags)) {
        // Move buttons down 3 pixels
        ImGui::SetCursorPosY(ImGui::GetCursorPosY() + 3);
        
        // Data tip toggle (first)
        bool tipWasEnabled = state.dataTipEnabled;  // Capture state before button
        if (tipWasEnabled) {
            ImGui::PushStyleColor(ImGuiCol_Button, ImVec4(0.2f, 0.6f, 0.2f, 1.0f));
        }
        if (ImGui::Button("Tip", ImVec2(48, 22))) {
            state.dataTipEnabled = !state.dataTipEnabled;
        }
        if (tipWasEnabled) {
            ImGui::PopStyleColor();
        }
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("Data Tip: Show values on hover");
        }
        
        ImGui::SameLine();
        
        // Fit button
        if (ImGui::Button("Fit", ImVec2(48, 22))) {
            state.plotsNeedUpdate = true;
            g_plotRangeInitialized = false;
        }
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("Fit: Reset view to show all data");
        }
        
        ImGui::SameLine();
        ImGui::TextDisabled("|");
        ImGui::SameLine();
        
        // Edit mode buttons
        bool noneActive = (state.editMode == EditMode::None);
        bool bloodActive = (state.editMode == EditMode::Blood);
        bool wallActive = (state.editMode == EditMode::Wall);
        bool clotActive = (state.editMode == EditMode::Clot);
        
        // None button - gray
        ImVec4 noneColor = noneActive ? ImVec4(0.7f, 0.7f, 0.7f, 1.0f) : ImVec4(0.4f, 0.4f, 0.4f, 1.0f);
        ImGui::PushStyleColor(ImGuiCol_Button, noneColor);
        if (ImGui::Button("None", ImVec2(60, 22))) {
            if (state.editMode == EditMode::None) {
                state.editMode = EditMode::Inactive;
            } else {
                state.editMode = EditMode::None;
            }
            state.hasStartPoint = false;
            state.hasEndPoint = false;
            state.pendingUpdate = false;
        }
        ImGui::PopStyleColor();
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("Set segments to None (0)");
        }
        
        ImGui::SameLine();
        
        // Blood button - green
        ImVec4 bloodColor = bloodActive ? ImVec4(0.0f, 0.7f, 0.0f, 1.0f) : ImVec4(0.0f, 0.4f, 0.0f, 1.0f);
        ImGui::PushStyleColor(ImGuiCol_Button, bloodColor);
        if (ImGui::Button("Blood", ImVec2(60, 22))) {
            if (state.editMode == EditMode::Blood) {
                state.editMode = EditMode::Inactive;
            } else {
                state.editMode = EditMode::Blood;
            }
            state.hasStartPoint = false;
            state.hasEndPoint = false;
            state.pendingUpdate = false;
        }
        ImGui::PopStyleColor();
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("Set segments to Blood (1)");
        }
        
        ImGui::SameLine();
        
        // Wall button - blue
        ImVec4 wallColor = wallActive ? ImVec4(0.3f, 0.5f, 1.0f, 1.0f) : ImVec4(0.15f, 0.3f, 0.6f, 1.0f);
        ImGui::PushStyleColor(ImGuiCol_Button, wallColor);
        if (ImGui::Button("Wall", ImVec2(60, 22))) {
            if (state.editMode == EditMode::Wall) {
                state.editMode = EditMode::Inactive;
            } else {
                state.editMode = EditMode::Wall;
            }
            state.hasStartPoint = false;
            state.hasEndPoint = false;
            state.pendingUpdate = false;
        }
        ImGui::PopStyleColor();
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("Set segments to Wall (2)");
        }
        
        ImGui::SameLine();
        
        // Clot button - orange
        ImVec4 clotColor = clotActive ? ImVec4(1.0f, 0.6f, 0.0f, 1.0f) : ImVec4(0.6f, 0.35f, 0.0f, 1.0f);
        ImGui::PushStyleColor(ImGuiCol_Button, clotColor);
        if (ImGui::Button("Clot", ImVec2(60, 22))) {
            if (state.editMode == EditMode::Clot) {
                state.editMode = EditMode::Inactive;
            } else {
                state.editMode = EditMode::Clot;
            }
            state.hasStartPoint = false;
            state.hasEndPoint = false;
            state.pendingUpdate = false;
        }
        ImGui::PopStyleColor();
        if (ImGui::IsItemHovered()) {
            ImGui::SetTooltip("Set segments to Clot (3)");
        }
        
        // File info on right
        ImGui::SameLine(io.DisplaySize.x - 350);
        
        if (state.h5aData.isLoaded) {
            std::string displayName = state.h5aData.caseName.empty() ?
                GetFilenameFromPath(state.currentFilePath) :
                state.h5aData.caseName;
            
            const char* unsavedMarker = state.hasUnsavedChanges ? " *" : "";
            ImGui::Text("[H5A] %s (%zu segs)%s", displayName.c_str(), 
                state.h5aData.NumSegments(), unsavedMarker);
        } else {
            ImGui::TextDisabled("No file loaded");
        }
    }
    ImGui::End();
    
    ImGui::PopStyleVar(2);
}

//=============================================================================
// PLOTS
//=============================================================================

void RenderPlots(AppState& state) {
    ImGuiIO& io = ImGui::GetIO();
    
    float menuBarHeight = ImGui::GetFrameHeight() + 8;  // Extra padding for larger menu bar
    float toolbarHeight = 36;  // Increased by 2 more
    float topOffset = menuBarHeight + toolbarHeight;
    
    ImGui::SetNextWindowPos(ImVec2(0, topOffset));
    ImGui::SetNextWindowSize(ImVec2(io.DisplaySize.x, io.DisplaySize.y - topOffset));
    
    // Remove padding on left, right, top - keep bottom for info bar
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(0, 0));
    
    ImGuiWindowFlags flags = ImGuiWindowFlags_NoTitleBar | 
                             ImGuiWindowFlags_NoResize | 
                             ImGuiWindowFlags_NoMove |
                             ImGuiWindowFlags_NoCollapse |
                             ImGuiWindowFlags_NoSavedSettings;
    
    ImGui::Begin("##PlotArea", nullptr, flags);
    
    bool hasData = state.h5aData.isLoaded && !state.h5aData.time_S.empty();
    
    // Track when we need to reset axes
    static bool s_needsAxisReset = true;
    if (state.plotsNeedUpdate) {
        s_needsAxisReset = true;
        g_plotRangeInitialized = false;
        state.plotsNeedUpdate = false;
    }
    
    // Calculate data range for auto-fit
    if (!g_plotRangeInitialized && hasData) {
        const auto& timeS = state.h5aData.time_S;
        const auto& magR = state.h5aData.magR;
        
        g_xRangeMin = timeS.front();
        g_xRangeMax = timeS.back();
        
        double yMin = *std::min_element(magR.begin(), magR.end());
        double yMax = *std::max_element(magR.begin(), magR.end());
        double yPad = (yMax - yMin) * 0.1;
        g_yRangeMin = yMin - yPad;
        g_yRangeMax = yMax + yPad;
        
        g_plotRangeInitialized = true;
    }
    
    // Plot size - full width, leave room for info bar at bottom
    ImVec2 plotSize = ImVec2(io.DisplaySize.x, ImGui::GetContentRegionAvail().y - 25);
    
    // Plot setup - disable context menu when in edit mode
    ImPlotFlags plotFlags = ImPlotFlags_NoLegend;
    if (state.editMode != EditMode::Inactive) {
        plotFlags |= ImPlotFlags_NoMenus;  // Disable right-click menu in edit mode
    }
    ImPlotCond axisCond = s_needsAxisReset ? ImPlotCond_Always : ImPlotCond_Once;
    
    if (ImPlot::BeginPlot("##SignalPlot", plotSize, plotFlags)) {
        ImPlot::SetupAxes("Time (s)", "magR", ImPlotAxisFlags_None, ImPlotAxisFlags_None);
        ImPlot::SetupAxisLimits(ImAxis_X1, g_xRangeMin, g_xRangeMax, axisCond);
        ImPlot::SetupAxisLimits(ImAxis_Y1, g_yRangeMin, g_yRangeMax, axisCond);
        s_needsAxisReset = false;
        
        if (hasData) {
            const std::vector<double>& timeS = state.h5aData.time_S;
            const std::vector<double>& magR = state.h5aData.magR;
            int n = static_cast<int>(timeS.size());
            
            // Check zoom level for dots
            ImPlotRect limits = ImPlot::GetPlotLimits();
            double visibleRange = limits.X.Max - limits.X.Min;
            bool showDots = visibleRange <= VISIBLE_RANGE_FOR_DOTS;
            
            // Update stored limits
            g_xRangeMin = limits.X.Min;
            g_xRangeMax = limits.X.Max;
            g_yRangeMin = limits.Y.Min;
            g_yRangeMax = limits.Y.Max;
            
            // Select state vector based on editTarget
            const std::vector<int>& stateVec = (state.editTarget == EditTarget::StateDet) 
                ? state.h5aData.stateDet 
                : state.h5aData.stateTru;
            const char* targetLabel = (state.editTarget == EditTarget::StateDet) 
                ? "stateDet" 
                : "stateTru";
            
            // Store position for drawing label after plot (to allow font scaling)
            double labelX = limits.X.Max - (limits.X.Max - limits.X.Min) * 0.01;
            double labelY = limits.Y.Max - (limits.Y.Max - limits.Y.Min) * 0.01;
            ImVec2 labelScreenPos = ImPlot::PlotToPixels(labelX, labelY);
            
            // H5A format: plot with colored overlays based on state segments
            // Colors: 0=gray, 1=green, 2=blue, 3=orange
            ImVec4 segColors[4] = {
                ImVec4(0.7f, 0.7f, 0.7f, 1.0f),   // 0 = gray (none)
                ImVec4(0.0f, 0.5f, 0.0f, 1.0f),   // 1 = green (blood)
                ImVec4(0.2f, 0.4f, 1.0f, 1.0f),   // 2 = blue (wall)
                ImVec4(1.0f, 0.5f, 0.0f, 1.0f)    // 3 = orange (clot)
            };
            
            int samplesPerSeg = state.h5aData.sampleRate / 2;  // 0.5 second segments
            if (samplesPerSeg <= 0) samplesPerSeg = 15;  // default for 30Hz
            
            int numSegs = static_cast<int>(stateVec.size());
            
            // Gap line colors
            ImVec4 gapColorBright = ImVec4(0.5f, 0.5f, 0.5f, 1.0f);
            ImVec4 gapColorDark = ImVec4(0.25f, 0.25f, 0.25f, 1.0f);
            
            // First pass: draw gap lines
            for (int seg = 0; seg < numSegs - 1; ++seg) {
                int segEnd = (seg + 1) * samplesPerSeg - 1;
                int nextStart = (seg + 1) * samplesPerSeg;
                
                if (segEnd >= n || nextStart >= n) continue;
                
                int currentState = stateVec[seg];
                int nextState = stateVec[seg + 1];
                bool nearGray = (currentState == 0 || nextState == 0);
                
                ImVec4 lineColor = nearGray ? gapColorDark : gapColorBright;
                
                double gapX[2] = { timeS[segEnd], timeS[nextStart] };
                double gapY[2] = { magR[segEnd], magR[nextStart] };
                
                ImPlot::SetNextLineStyle(lineColor, LINE_THICKNESS);
                char label[32];
                snprintf(label, sizeof(label), "##gap%d", seg);
                ImPlot::PlotLine(label, gapX, gapY, 2);
            }
            
            // Second pass: draw segments
            for (int seg = 0; seg < numSegs; ++seg) {
                int sampleStart = seg * samplesPerSeg;
                int sampleEnd = std::min(sampleStart + samplesPerSeg, n);
                int segLen = sampleEnd - sampleStart;
                
                if (segLen <= 0) continue;
                
                int stateVal = stateVec[seg];
                if (stateVal < 0 || stateVal > 3) stateVal = 0;
                
                ImVec4 color = segColors[stateVal];
                
                ImPlot::SetNextLineStyle(color, LINE_THICKNESS);
                char label[32];
                snprintf(label, sizeof(label), "##seg%d", seg);
                ImPlot::PlotLine(label, &timeS[sampleStart], &magR[sampleStart], segLen);
            }
            
            // Dots when zoomed
            if (showDots) {
                for (int seg = 0; seg < numSegs; ++seg) {
                    int sampleStart = seg * samplesPerSeg;
                    int sampleEnd = std::min(sampleStart + samplesPerSeg, n);
                    int segLen = sampleEnd - sampleStart;
                    
                    if (segLen <= 0) continue;
                    
                    int stateVal = stateVec[seg];
                    if (stateVal < 0 || stateVal > 3) stateVal = 0;
                    
                    ImVec4 color = segColors[stateVal];
                    
                    ImPlot::SetNextMarkerStyle(ImPlotMarker_Circle, DOT_SIZE, color, IMPLOT_AUTO, color);
                    char label[32];
                    snprintf(label, sizeof(label), "##dots%d", seg);
                    ImPlot::PlotScatter(label, &timeS[sampleStart], &magR[sampleStart], segLen);
                }
            }
            
            // Draw selection lines (vertical)
            if (state.hasStartPoint) {
                double lineX[2] = { state.startTime, state.startTime };
                double lineY[2] = { limits.Y.Min, limits.Y.Max };
                ImPlot::SetNextLineStyle(ImVec4(1.0f, 1.0f, 0.0f, 1.0f), 2.0f);  // Yellow
                ImPlot::PlotLine("##startLine", lineX, lineY, 2);
            }
            
            if (state.hasEndPoint) {
                double lineX[2] = { state.endTime, state.endTime };
                double lineY[2] = { limits.Y.Min, limits.Y.Max };
                ImPlot::SetNextLineStyle(ImVec4(1.0f, 0.0f, 1.0f, 1.0f), 2.0f);  // Magenta
                ImPlot::PlotLine("##endLine", lineX, lineY, 2);
            }
            
            // Draw stateDet/stateTru label with larger font
            ImDrawList* drawList = ImPlot::GetPlotDrawList();
            ImFont* font = ImGui::GetFont();
            float fontSize = font->FontSize * 1.5f;  // 1.5x size
            
            ImVec2 textSize = font->CalcTextSizeA(fontSize, FLT_MAX, 0.0f, targetLabel);
            ImVec2 textPos = ImVec2(labelScreenPos.x - textSize.x - 10, labelScreenPos.y + 5);
            drawList->AddText(font, fontSize, textPos, IM_COL32(255, 255, 0, 255), targetLabel);
        }
        
        // Handle mouse clicks for editing
        if (hasData && state.editMode != EditMode::Inactive && !state.pendingUpdate) {
            if (ImPlot::IsPlotHovered() && ImGui::IsMouseClicked(ImGuiMouseButton_Left)) {
                ImPlotPoint mouse = ImPlot::GetPlotMousePos();
                
                if (!state.hasStartPoint) {
                    // First click - set start point
                    state.startTime = mouse.x;
                    state.hasStartPoint = true;
                } else if (!state.hasEndPoint) {
                    // Second click - set end point
                    state.endTime = mouse.x;
                    state.hasEndPoint = true;
                    
                    // Ensure start < end
                    if (state.startTime > state.endTime) {
                        std::swap(state.startTime, state.endTime);
                    }
                    
                    // Start pending update timer
                    state.pendingUpdate = true;
                    g_pendingStartTime = std::chrono::steady_clock::now();
                }
            }
            
            // Right-click to exit edit mode
            if (ImPlot::IsPlotHovered() && ImGui::IsMouseClicked(ImGuiMouseButton_Right)) {
                state.editMode = EditMode::Inactive;
                state.hasStartPoint = false;
                state.hasEndPoint = false;
                state.pendingUpdate = false;
            }
        }
        
        // Data tip
        if (state.dataTipEnabled && ImPlot::IsPlotHovered() && hasData) {
            ImPlotPoint mouse = ImPlot::GetPlotMousePos();
            
            const std::vector<double>& timeS = state.h5aData.time_S;
            const std::vector<double>& magR = state.h5aData.magR;
            
            // Find nearest sample
            int nearestIdx = 0;
            double minDist = std::abs(timeS[0] - mouse.x);
            for (size_t i = 1; i < timeS.size(); ++i) {
                double dist = std::abs(timeS[i] - mouse.x);
                if (dist < minDist) {
                    minDist = dist;
                    nearestIdx = static_cast<int>(i);
                }
            }
            
            // Get segment info
            int samplesPerSeg = state.h5aData.sampleRate / 2;
            if (samplesPerSeg <= 0) samplesPerSeg = 15;
            int segIdx = nearestIdx / samplesPerSeg;
            
            // Use correct state vector
            const std::vector<int>& tipStateVec = (state.editTarget == EditTarget::StateDet) 
                ? state.h5aData.stateDet 
                : state.h5aData.stateTru;
            
            const char* stateNames[4] = { "None", "Blood", "Wall", "Clot" };
            int stateVal = 0;
            if (segIdx >= 0 && segIdx < static_cast<int>(tipStateVec.size())) {
                stateVal = tipStateVec[segIdx];
                if (stateVal < 0 || stateVal > 3) stateVal = 0;
            }
            
            char tooltip[128];
            snprintf(tooltip, sizeof(tooltip), "t=%.3f s\nmagR=%.4f\nState=%s", 
                timeS[nearestIdx], magR[nearestIdx], stateNames[stateVal]);
            
            ImGui::BeginTooltip();
            ImGui::TextUnformatted(tooltip);
            ImGui::EndTooltip();
        }
        
        ImPlot::EndPlot();
    }
    
    // Info bar - add indent since window padding is 0
    ImGui::Spacing();
    ImGui::SetCursorPosX(8);  // Left margin for text
    if (state.h5aData.isLoaded) {
        // Show edit mode status
        const char* modeNames[] = { "Inactive", "None", "Blood", "Wall", "Clot" };
        int modeIdx = static_cast<int>(state.editMode);
        
        if (state.pendingUpdate) {
            ImGui::TextColored(ImVec4(1.0f, 1.0f, 0.0f, 1.0f), 
                "Applying edit... (%.1f-%.1f s)", state.startTime, state.endTime);
        } else if (state.editMode != EditMode::Inactive) {
            if (state.hasStartPoint && !state.hasEndPoint) {
                ImGui::TextColored(ImVec4(0.0f, 1.0f, 0.0f, 1.0f), 
                    "Edit Mode: %s | Start: %.3f s | Click to set end point", 
                    modeNames[modeIdx], state.startTime);
            } else {
                ImGui::TextColored(ImVec4(0.0f, 1.0f, 0.0f, 1.0f), 
                    "Edit Mode: %s | Click to set start point", modeNames[modeIdx]);
            }
        } else {
            ImGui::Text("H5A: %zu samples, %zu segments (0.5s each), %d Hz", 
                state.h5aData.Size(), state.h5aData.NumSegments(), state.h5aData.sampleRate);
        }
    } else {
        ImGui::TextDisabled("No data loaded. Use File > Open to load an h5a file.");
    }
    
    ImGui::End();
    ImGui::PopStyleVar();  // WindowPadding
}

//=============================================================================
// EDIT FUNCTIONS
//=============================================================================

void ApplyEdit(AppState& state) {
    if (!state.h5aData.isLoaded) return;
    if (!state.hasStartPoint || !state.hasEndPoint) return;
    
    // Determine value to set
    int newValue = 0;
    switch (state.editMode) {
        case EditMode::None:  newValue = 0; break;
        case EditMode::Blood: newValue = 1; break;
        case EditMode::Wall:  newValue = 2; break;
        case EditMode::Clot:  newValue = 3; break;
        default: return;
    }
    
    // Select target vector based on editTarget
    std::vector<int>& targetVec = (state.editTarget == EditTarget::StateDet) 
        ? state.h5aData.stateDet 
        : state.h5aData.stateTru;
    
    // Find segment range
    int samplesPerSeg = state.h5aData.sampleRate / 2;
    if (samplesPerSeg <= 0) samplesPerSeg = 15;
    
    double segDuration = 0.5;  // seconds
    double startTimeOffset = state.h5aData.time_S.empty() ? 0.0 : state.h5aData.time_S[0];
    
    int startSeg = static_cast<int>((state.startTime - startTimeOffset) / segDuration);
    int endSeg = static_cast<int>((state.endTime - startTimeOffset) / segDuration);
    
    // Clamp to valid range
    int numSegs = static_cast<int>(targetVec.size());
    startSeg = std::max(0, std::min(startSeg, numSegs - 1));
    endSeg = std::max(0, std::min(endSeg, numSegs - 1));
    
    // Apply the change
    for (int seg = startSeg; seg <= endSeg; ++seg) {
        targetVec[seg] = newValue;
    }
    
    state.hasUnsavedChanges = true;
}

//=============================================================================
// DIALOGS
//=============================================================================

void RenderAboutDialog(AppState& state) {
    ImGui::SetNextWindowSize(ImVec2(200, 100), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImGui::GetMainViewport()->GetCenter(), ImGuiCond_FirstUseEver, ImVec2(0.5f, 0.5f));
    
    if (ImGui::Begin("About", &state.showAboutDialog, 
                     ImGuiWindowFlags_NoResize | ImGuiWindowFlags_NoCollapse)) {
        ImGui::Text("iSignalEditTool");
        ImGui::Text("Version 1.0");
        ImGui::Spacing();
        
        if (ImGui::Button("Close", ImVec2(80, 0))) {
            state.showAboutDialog = false;
        }
    }
    ImGui::End();
}

void RenderHDF5Inspector(AppState& state) {
    ImGui::SetNextWindowSize(ImVec2(600, 400), ImGuiCond_FirstUseEver);
    ImGui::SetNextWindowPos(ImGui::GetMainViewport()->GetCenter(), ImGuiCond_FirstUseEver, ImVec2(0.5f, 0.5f));
    
    if (ImGui::Begin("HDF5 Structure", &state.showHDF5Inspector, ImGuiWindowFlags_NoCollapse)) {
        if (state.hdf5Info.isValid) {
            ImGui::Text("File: %s", state.hdf5Info.filepath.c_str());
            ImGui::Text("Datasets: %zu", state.hdf5Info.datasets.size());
            ImGui::Separator();
            
            if (ImGui::BeginTable("##DatasetTable", 4, 
                ImGuiTableFlags_Borders | ImGuiTableFlags_RowBg | ImGuiTableFlags_ScrollY,
                ImVec2(0, ImGui::GetContentRegionAvail().y - 35))) {
                
                ImGui::TableSetupScrollFreeze(0, 1);
                ImGui::TableSetupColumn("Path", ImGuiTableColumnFlags_WidthStretch);
                ImGui::TableSetupColumn("Type", ImGuiTableColumnFlags_WidthFixed, 80);
                ImGui::TableSetupColumn("Dimensions", ImGuiTableColumnFlags_WidthFixed, 120);
                ImGui::TableSetupColumn("Elements", ImGuiTableColumnFlags_WidthFixed, 80);
                ImGui::TableHeadersRow();
                
                for (const auto& ds : state.hdf5Info.datasets) {
                    ImGui::TableNextRow();
                    
                    ImGui::TableSetColumnIndex(0);
                    ImGui::TextUnformatted(ds.path.c_str());
                    
                    ImGui::TableSetColumnIndex(1);
                    ImGui::TextUnformatted(ds.dataType.c_str());
                    
                    ImGui::TableSetColumnIndex(2);
                    std::string dimStr;
                    for (size_t i = 0; i < ds.dimensions.size(); i++) {
                        if (i > 0) dimStr += " x ";
                        dimStr += std::to_string(ds.dimensions[i]);
                    }
                    ImGui::TextUnformatted(dimStr.c_str());
                    
                    ImGui::TableSetColumnIndex(3);
                    ImGui::Text("%zu", ds.totalElements);
                }
                
                ImGui::EndTable();
            }
        }
        
        ImGui::Spacing();
        if (ImGui::Button("Close", ImVec2(80, 0))) {
            state.showHDF5Inspector = false;
        }
    }
    ImGui::End();
}
