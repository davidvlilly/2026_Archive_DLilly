// iFileIO.h - File I/O Library for HDF5 Data
// ivrbDetect Solution - Static Library
#pragma once

#include <vector>
#include <string>

//=============================================================================
// ENUMERATIONS
//=============================================================================

// Data source type - tracks which format was last loaded/exported
enum class DataSourceType {
    None = 0,
    H5P,        // Original h5p format (magDat/refDat)
    H5A         // Processed h5a format (signal/meta/refInfo)
};

//=============================================================================
// DATA STRUCTURES
//=============================================================================

// Main data vectors (from /magDat group) - all same length
struct MagData {
    std::vector<double> time_S;
    std::vector<double> magR;
    std::vector<int> identified;
    std::vector<int> truth;
    
    void Clear() {
        time_S.clear();
        magR.clear();
        identified.clear();
        truth.clear();
    }
    
    size_t Size() const { return time_S.size(); }
};

// Reference data vectors (from /refDat group) - variable lengths
struct RefData {
    std::vector<double> Aspirate;
    std::vector<double> Clot;
    std::vector<double> bloodBeg;
    std::vector<double> bloodEnd;
    std::vector<double> wallBeg;
    std::vector<double> wallEnd;
    std::vector<double> clotBeg;
    std::vector<double> clotEnd;
    
    void Clear() {
        Aspirate.clear();
        Clot.clear();
        bloodBeg.clear();
        bloodEnd.clear();
        wallBeg.clear();
        wallEnd.clear();
        clotBeg.clear();
        clotEnd.clear();
    }
};

// Import data container (h5p format)
struct ImportData {
    std::string originalFilename;
    std::string currentFilePath;
    MagData magDat;
    RefData refDat;
    bool isLoaded = false;
    
    void Clear() {
        originalFilename.clear();
        currentFilePath.clear();
        magDat.Clear();
        refDat.Clear();
        isLoaded = false;
    }
};

// H5A format data container (signal/meta/refInfo structure)
struct H5AData {
    // Signal data (same sample rate as original)
    std::vector<double> time_S;
    std::vector<double> magR;
    
    // Meta data (at 0.5s segment rate - fewer samples)
    std::vector<int> stateDet;      // Detected state at segment end
    std::vector<int> stateTru;      // True state at segment end
    
    // Reference info
    int sampleRate = 30;
    int fileFormatVersion = 1;
    std::string caseName;
    std::string currentFilePath;
    
    bool isLoaded = false;
    
    void Clear() {
        time_S.clear();
        magR.clear();
        stateDet.clear();
        stateTru.clear();
        sampleRate = 30;
        fileFormatVersion = 1;
        caseName.clear();
        currentFilePath.clear();
        isLoaded = false;
    }
    
    size_t Size() const { return time_S.size(); }
    size_t NumSegments() const { return stateDet.size(); }
};

// Export data container (h5a format) - for future use
struct ExportData {
    MagData magDat;
    RefData refDat;
    bool isReady = false;
    
    void Clear() {
        magDat.Clear();
        refDat.Clear();
        isReady = false;
    }
    
    // Copy from import data
    void CopyFrom(const ImportData& src) {
        magDat = src.magDat;
        refDat = src.refDat;
        isReady = src.isLoaded;
    }
};

// HDF5 dataset info for Show_HDF5 feature
struct HDF5DatasetInfo {
    std::string name;
    std::string path;
    std::string dataType;
    std::vector<size_t> dimensions;
    size_t totalElements;
};

struct HDF5FileInfo {
    std::string filepath;
    std::vector<HDF5DatasetInfo> datasets;
    bool isValid = false;
};

//=============================================================================
// FILE I/O FUNCTIONS
//=============================================================================

// Load h5p format file (import)
bool LoadH5PFile(const std::string& filepath, ImportData& data);

// Load h5a format file (import)
bool LoadH5AFile(const std::string& filepath, H5AData& data);

// Save h5a format file (export)
// Converts h5p data to h5a format:
//   - signal/magR, signal/time_S from magDat (truncated to 0.5s segments)
//   - meta/stateDet from truth values at segment ends
//   - meta/stateTru filled with zeros
//   - refInfo/SampleRate = 30, refInfo/FileFormatVersion = 1
//   - refInfo/CaseName = base filename
// Time is adjusted to start at second boundary, data truncated to complete segments
bool SaveH5AFile(const std::string& filepath, const ExportData& data);

// Save h5a format and populate H5AData structure for immediate display
bool SaveH5AFileAndLoad(const std::string& filepath, const ExportData& data, H5AData& outData);

// Save h5a format directly from H5AData (for saving edited data)
bool SaveH5AFileFromData(const std::string& filepath, const H5AData& data);

// Inspect any HDF5 file structure
bool InspectHDF5File(const std::string& filepath, HDF5FileInfo& info);

//=============================================================================
// DIALOG FUNCTIONS
//=============================================================================

// Show native Windows Open File Dialog (single file)
std::string ShowOpenFileDialog(const char* filter = "HDF5 Files (*.h5p;*.h5a;*.h5)\0*.h5p;*.h5a;*.h5\0All Files\0*.*\0");

// Show native Windows Open File Dialog (multiple files)
std::vector<std::string> ShowOpenMultiFileDialog(const char* filter = "HDF5 Files (*.h5p;*.h5a;*.h5)\0*.h5p;*.h5a;*.h5\0All Files\0*.*\0");

// Show native Windows Save File Dialog
std::string ShowSaveFileDialog(const char* filter = "HDF5 Files (*.h5a)\0*.h5a\0All Files\0*.*\0",
                                const std::string& defaultFilename = "");

// Show native Windows Folder Selection Dialog
std::string ShowSelectFolderDialog(const std::string& title = "Select Output Folder");

//=============================================================================
// UTILITY FUNCTIONS
//=============================================================================

// Reset truth vector based on refDat markers (0=none, 1=blood, 2=wall, 3=clot)
void ResetTruth(ImportData& data);

// Extract filename from path
std::string GetFilenameFromPath(const std::string& filepath);
