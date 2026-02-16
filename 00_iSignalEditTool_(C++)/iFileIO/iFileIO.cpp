// iFileIO.cpp - File I/O Library Implementation
// ivrbDetect Solution - Static Library

#include "iFileIO.h"
#include "H5Cpp.h"
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <Windows.h>
#include <commdlg.h>
#include <shlobj.h>
#include <algorithm>
#include <sstream>
#include <cmath>

using namespace H5;

//=============================================================================
// HELPER FUNCTIONS
//=============================================================================

// Helper to read a double dataset (handles both 1D and 2D Nx1 arrays)
static bool ReadDoubleDataset(H5File& file, const std::string& path, std::vector<double>& data) {
    try {
        if (!file.nameExists(path)) return false;
        
        DataSet dataset = file.openDataSet(path);
        DataSpace dataspace = dataset.getSpace();
        
        hsize_t dims[2];
        int ndims = dataspace.getSimpleExtentDims(dims, NULL);
        
        // Handle both 1D and 2D (Nx1) arrays
        size_t totalSize = dims[0];
        if (ndims > 1) totalSize *= dims[1];
        
        data.resize(totalSize);
        dataset.read(data.data(), PredType::NATIVE_DOUBLE);
        return true;
    }
    catch (...) {
        return false;
    }
}

// Helper to read an int dataset (handles both 1D and 2D Nx1 arrays)
static bool ReadIntDataset(H5File& file, const std::string& path, std::vector<int>& data) {
    try {
        if (!file.nameExists(path)) return false;
        
        DataSet dataset = file.openDataSet(path);
        DataSpace dataspace = dataset.getSpace();
        
        hsize_t dims[2];
        int ndims = dataspace.getSimpleExtentDims(dims, NULL);
        
        // Handle both 1D and 2D (Nx1) arrays
        size_t totalSize = dims[0];
        if (ndims > 1) totalSize *= dims[1];
        
        data.resize(totalSize);
        dataset.read(data.data(), PredType::NATIVE_INT32);
        return true;
    }
    catch (...) {
        return false;
    }
}

// Helper to write a double dataset
static bool WriteDoubleDataset(H5File& file, const std::string& path, const std::vector<double>& data) {
    try {
        if (data.empty()) return true;
        
        hsize_t dims[1] = { data.size() };
        DataSpace dataspace(1, dims);
        DataSet dataset = file.createDataSet(path, PredType::NATIVE_DOUBLE, dataspace);
        dataset.write(data.data(), PredType::NATIVE_DOUBLE);
        return true;
    }
    catch (...) {
        return false;
    }
}

// Helper to write an int dataset
static bool WriteIntDataset(H5File& file, const std::string& path, const std::vector<int>& data) {
    try {
        if (data.empty()) return true;
        
        hsize_t dims[1] = { data.size() };
        DataSpace dataspace(1, dims);
        DataSet dataset = file.createDataSet(path, PredType::NATIVE_INT, dataspace);
        dataset.write(data.data(), PredType::NATIVE_INT);
        return true;
    }
    catch (...) {
        return false;
    }
}

// Helper to find time index
static int FindTimeIndex(const std::vector<double>& time_S, double target) {
    auto it = std::lower_bound(time_S.begin(), time_S.end(), target);
    if (it == time_S.end()) return -1;
    return static_cast<int>(it - time_S.begin());
}

static int FindTimeIndexEnd(const std::vector<double>& time_S, double target) {
    auto it = std::upper_bound(time_S.begin(), time_S.end(), target);
    if (it == time_S.begin()) return -1;
    return static_cast<int>(it - time_S.begin()) - 1;
}

// HDF5 iteration callback data
struct IterData {
    H5File* file;
    std::vector<HDF5DatasetInfo>* datasets;
    std::string currentPath;
};

// Get HDF5 type name as string
static std::string GetTypeName(const DataType& dtype) {
    H5T_class_t typeClass = dtype.getClass();
    
    switch (typeClass) {
        case H5T_INTEGER: {
            IntType intType(dtype.getId());
            size_t size = intType.getSize();
            H5T_sign_t sign = intType.getSign();
            std::string signStr = (sign == H5T_SGN_NONE) ? "u" : "";
            return signStr + "int" + std::to_string(size * 8);
        }
        case H5T_FLOAT: {
            size_t size = dtype.getSize();
            return (size == 4) ? "float32" : "float64";
        }
        case H5T_STRING:
            return "string";
        case H5T_COMPOUND:
            return "compound";
        case H5T_ARRAY:
            return "array";
        default:
            return "unknown";
    }
}

// HDF5 iteration callback
static herr_t FileIterCallback(hid_t loc_id, const char* name, const H5L_info_t* info, void* opdata) {
    IterData* data = static_cast<IterData*>(opdata);
    
    std::string fullPath = data->currentPath.empty() ? 
        std::string("/") + name : data->currentPath + "/" + name;
    
    H5O_info_t objInfo;
    H5Oget_info_by_name(loc_id, name, &objInfo, H5O_INFO_BASIC, H5P_DEFAULT);
    
    if (objInfo.type == H5O_TYPE_DATASET) {
        try {
            DataSet dataset = data->file->openDataSet(fullPath);
            DataSpace dataspace = dataset.getSpace();
            DataType dtype = dataset.getDataType();
            
            HDF5DatasetInfo dsInfo;
            dsInfo.name = name;
            dsInfo.path = fullPath;
            dsInfo.dataType = GetTypeName(dtype);
            
            int ndims = dataspace.getSimpleExtentNdims();
            if (ndims > 0) {
                std::vector<hsize_t> dims(ndims);
                dataspace.getSimpleExtentDims(dims.data(), nullptr);
                dsInfo.totalElements = 1;
                for (int i = 0; i < ndims; i++) {
                    dsInfo.dimensions.push_back(static_cast<size_t>(dims[i]));
                    dsInfo.totalElements *= dims[i];
                }
            } else {
                dsInfo.totalElements = 1;
            }
            
            data->datasets->push_back(dsInfo);
        }
        catch (...) {}
    }
    else if (objInfo.type == H5O_TYPE_GROUP) {
        // Recurse into group
        IterData subData = *data;
        subData.currentPath = fullPath;
        H5Literate_by_name(loc_id, name, H5_INDEX_NAME, H5_ITER_NATIVE, nullptr, 
                          FileIterCallback, &subData, H5P_DEFAULT);
    }
    
    return 0;
}

//=============================================================================
// FILE I/O IMPLEMENTATION
//=============================================================================

bool LoadH5PFile(const std::string& filepath, ImportData& data) {
    data.Clear();
    
    try {
        H5File file(filepath, H5F_ACC_RDONLY);
        
        // Read magDat group
        bool hasTime = ReadDoubleDataset(file, "/magDat/Time_S", data.magDat.time_S);
        bool hasMagR = ReadDoubleDataset(file, "/magDat/magR", data.magDat.magR);
        
        if (!hasTime || !hasMagR) {
            return false;
        }
        
        ReadIntDataset(file, "/magDat/identified", data.magDat.identified);
        ReadIntDataset(file, "/magDat/truth", data.magDat.truth);
        
        // Initialize truth if not present
        if (data.magDat.truth.empty()) {
            data.magDat.truth.resize(data.magDat.time_S.size(), 0);
        }
        if (data.magDat.identified.empty()) {
            data.magDat.identified.resize(data.magDat.time_S.size(), 0);
        }
        
        // Read refDat group (optional)
        ReadDoubleDataset(file, "/refDat/Aspirate", data.refDat.Aspirate);
        ReadDoubleDataset(file, "/refDat/Clot", data.refDat.Clot);
        ReadDoubleDataset(file, "/refDat/bloodBeg", data.refDat.bloodBeg);
        ReadDoubleDataset(file, "/refDat/bloodEnd", data.refDat.bloodEnd);
        ReadDoubleDataset(file, "/refDat/wallBeg", data.refDat.wallBeg);
        ReadDoubleDataset(file, "/refDat/wallEnd", data.refDat.wallEnd);
        ReadDoubleDataset(file, "/refDat/clotBeg", data.refDat.clotBeg);
        ReadDoubleDataset(file, "/refDat/clotEnd", data.refDat.clotEnd);
        
        // Read original_filename (stored as uint8 array at root level)
        try {
            if (file.nameExists("original_filename")) {
                DataSet dataset = file.openDataSet("original_filename");
                DataSpace dataspace = dataset.getSpace();
                hsize_t dims[2];
                int ndims = dataspace.getSimpleExtentDims(dims, NULL);
                
                size_t totalSize = dims[0];
                if (ndims > 1) totalSize *= dims[1];
                
                std::vector<uint8_t> buffer(totalSize);
                dataset.read(buffer.data(), PredType::NATIVE_UINT8);
                data.originalFilename = std::string(buffer.begin(), buffer.end());
                
                // Remove any trailing null characters
                size_t pos = data.originalFilename.find('\0');
                if (pos != std::string::npos) {
                    data.originalFilename = data.originalFilename.substr(0, pos);
                }
            }
        }
        catch (...) {}
        
        data.currentFilePath = filepath;
        data.isLoaded = true;
        
        file.close();
        return true;
    }
    catch (const Exception&) {
        return false;
    }
}

bool SaveH5AFile(const std::string& filepath, const ExportData& data) {
    if (!data.isReady) return false;
    if (data.magDat.time_S.empty() || data.magDat.magR.empty()) return false;
    
    try {
        const int SAMPLE_RATE = 30;
        const double SEGMENT_DURATION = 0.5;  // seconds
        const int SAMPLES_PER_SEGMENT = static_cast<int>(SAMPLE_RATE * SEGMENT_DURATION);  // 15 samples
        
        // Step 1: Find nearest 0.5s boundary to the first sample
        double firstTime = data.magDat.time_S[0];
        double startTime = std::round(firstTime * 2.0) / 2.0;  // Round to nearest 0.5s
        
        // Step 2: Calculate how many complete 0.5s segments we can fit
        int totalInputSamples = static_cast<int>(data.magDat.time_S.size());
        int numSegments = totalInputSamples / SAMPLES_PER_SEGMENT;
        
        if (numSegments < 1) return false;  // Not enough data
        
        int totalSamples = numSegments * SAMPLES_PER_SEGMENT;
        
        // Step 3: Extract signal data with regenerated time values at exact 30Hz
        std::vector<double> signal_time_S(totalSamples);
        std::vector<double> signal_magR(totalSamples);
        
        for (int i = 0; i < totalSamples; ++i) {
            // Regenerate time at exact 30Hz intervals from the 0.5s boundary
            signal_time_S[i] = startTime + static_cast<double>(i) / SAMPLE_RATE;
            signal_magR[i] = data.magDat.magR[i];
        }
        
        // Step 4: Create stateDet - truth value at END of each 0.5s segment
        std::vector<int> stateDet(numSegments);
        for (int seg = 0; seg < numSegments; ++seg) {
            int endSampleIdx = (seg + 1) * SAMPLES_PER_SEGMENT - 1;
            if (endSampleIdx < static_cast<int>(data.magDat.truth.size())) {
                stateDet[seg] = data.magDat.truth[endSampleIdx];
            } else {
                stateDet[seg] = 0;
            }
        }
        
        // Step 5: Create stateTru - all zeros
        std::vector<int> stateTru(numSegments, 0);
        
        // Step 6: Extract base filename for CaseName
        std::string caseName = GetFilenameFromPath(filepath);
        // Remove extension
        size_t dotPos = caseName.rfind('.');
        if (dotPos != std::string::npos) {
            caseName = caseName.substr(0, dotPos);
        }
        
        // Now write the h5a file
        H5File file(filepath, H5F_ACC_TRUNC);
        
        // Create groups
        Group signalGroup = file.createGroup("/signal");
        Group metaGroup = file.createGroup("/meta");
        Group refInfoGroup = file.createGroup("/refInfo");
        
        // Write signal data
        WriteDoubleDataset(file, "/signal/magR", signal_magR);
        WriteDoubleDataset(file, "/signal/time_S", signal_time_S);
        
        // Write meta data
        WriteIntDataset(file, "/meta/stateDet", stateDet);
        WriteIntDataset(file, "/meta/stateTru", stateTru);
        
        // Write refInfo/SampleRate (scalar int)
        {
            hsize_t dims[1] = { 1 };
            DataSpace dataspace(1, dims);
            DataSet dataset = file.createDataSet("/refInfo/SampleRate", PredType::NATIVE_INT, dataspace);
            int sampleRate = SAMPLE_RATE;
            dataset.write(&sampleRate, PredType::NATIVE_INT);
        }
        
        // Write refInfo/FileFormatVersion (scalar int)
        {
            hsize_t dims[1] = { 1 };
            DataSpace dataspace(1, dims);
            DataSet dataset = file.createDataSet("/refInfo/FileFormatVersion", PredType::NATIVE_INT, dataspace);
            int version = 1;
            dataset.write(&version, PredType::NATIVE_INT);
        }
        
        // Write refInfo/CaseName (string as uint8 array)
        if (!caseName.empty()) {
            hsize_t dims[1] = { caseName.size() };
            DataSpace dataspace(1, dims);
            DataSet dataset = file.createDataSet("/refInfo/CaseName", PredType::NATIVE_UINT8, dataspace);
            dataset.write(caseName.data(), PredType::NATIVE_UINT8);
        }
        
        file.close();
        return true;
    }
    catch (const Exception&) {
        return false;
    }
}

bool LoadH5AFile(const std::string& filepath, H5AData& data) {
    data.Clear();
    
    try {
        H5File file(filepath, H5F_ACC_RDONLY);
        
        // Read signal group
        bool hasTime = ReadDoubleDataset(file, "/signal/time_S", data.time_S);
        bool hasMagR = ReadDoubleDataset(file, "/signal/magR", data.magR);
        
        if (!hasTime || !hasMagR) {
            return false;
        }
        
        // Read meta group
        ReadIntDataset(file, "/meta/stateDet", data.stateDet);
        ReadIntDataset(file, "/meta/stateTru", data.stateTru);
        
        // Read refInfo group
        // SampleRate
        try {
            if (file.nameExists("/refInfo/SampleRate")) {
                DataSet dataset = file.openDataSet("/refInfo/SampleRate");
                dataset.read(&data.sampleRate, PredType::NATIVE_INT);
            }
        } catch (...) {}
        
        // FileFormatVersion
        try {
            if (file.nameExists("/refInfo/FileFormatVersion")) {
                DataSet dataset = file.openDataSet("/refInfo/FileFormatVersion");
                dataset.read(&data.fileFormatVersion, PredType::NATIVE_INT);
            }
        } catch (...) {}
        
        // CaseName (stored as uint8 array)
        try {
            if (file.nameExists("/refInfo/CaseName")) {
                DataSet dataset = file.openDataSet("/refInfo/CaseName");
                DataSpace dataspace = dataset.getSpace();
                hsize_t dims[2];
                int ndims = dataspace.getSimpleExtentDims(dims, NULL);
                
                size_t totalSize = dims[0];
                if (ndims > 1) totalSize *= dims[1];
                
                std::vector<uint8_t> buffer(totalSize);
                dataset.read(buffer.data(), PredType::NATIVE_UINT8);
                data.caseName = std::string(buffer.begin(), buffer.end());
                
                // Remove any trailing null characters
                size_t pos = data.caseName.find('\0');
                if (pos != std::string::npos) {
                    data.caseName = data.caseName.substr(0, pos);
                }
            }
        } catch (...) {}
        
        data.currentFilePath = filepath;
        data.isLoaded = true;
        
        file.close();
        return true;
    }
    catch (const Exception&) {
        return false;
    }
}

bool SaveH5AFileAndLoad(const std::string& filepath, const ExportData& data, H5AData& outData) {
    outData.Clear();
    
    if (!data.isReady) return false;
    if (data.magDat.time_S.empty() || data.magDat.magR.empty()) return false;
    
    try {
        const int SAMPLE_RATE = 30;
        const double SEGMENT_DURATION = 0.5;  // seconds
        const int SAMPLES_PER_SEGMENT = static_cast<int>(SAMPLE_RATE * SEGMENT_DURATION);  // 15 samples
        
        // Step 1: Find nearest 0.5s boundary to the first sample
        double firstTime = data.magDat.time_S[0];
        double startTime = std::round(firstTime * 2.0) / 2.0;  // Round to nearest 0.5s
        
        // Step 2: Calculate how many complete 0.5s segments we can fit
        int totalInputSamples = static_cast<int>(data.magDat.time_S.size());
        int numSegments = totalInputSamples / SAMPLES_PER_SEGMENT;
        
        if (numSegments < 1) return false;  // Not enough data
        
        int totalSamples = numSegments * SAMPLES_PER_SEGMENT;
        
        // Step 3: Extract signal data with regenerated time values at exact 30Hz
        outData.time_S.resize(totalSamples);
        outData.magR.resize(totalSamples);
        
        for (int i = 0; i < totalSamples; ++i) {
            // Regenerate time at exact 30Hz intervals from the 0.5s boundary
            outData.time_S[i] = startTime + static_cast<double>(i) / SAMPLE_RATE;
            outData.magR[i] = data.magDat.magR[i];
        }
        
        // Step 4: Create stateDet - truth value at END of each 0.5s segment
        outData.stateDet.resize(numSegments);
        for (int seg = 0; seg < numSegments; ++seg) {
            int endSampleIdx = (seg + 1) * SAMPLES_PER_SEGMENT - 1;
            if (endSampleIdx < static_cast<int>(data.magDat.truth.size())) {
                outData.stateDet[seg] = data.magDat.truth[endSampleIdx];
            } else {
                outData.stateDet[seg] = 0;
            }
        }
        
        // Step 5: Create stateTru - all zeros
        outData.stateTru.resize(numSegments, 0);
        
        // Step 6: Extract base filename for CaseName
        outData.caseName = GetFilenameFromPath(filepath);
        size_t dotPos = outData.caseName.rfind('.');
        if (dotPos != std::string::npos) {
            outData.caseName = outData.caseName.substr(0, dotPos);
        }
        
        outData.sampleRate = SAMPLE_RATE;
        outData.fileFormatVersion = 1;
        outData.currentFilePath = filepath;
        outData.isLoaded = true;
        
        // Now write the h5a file
        H5File file(filepath, H5F_ACC_TRUNC);
        
        // Create groups
        Group signalGroup = file.createGroup("/signal");
        Group metaGroup = file.createGroup("/meta");
        Group refInfoGroup = file.createGroup("/refInfo");
        
        // Write signal data
        WriteDoubleDataset(file, "/signal/magR", outData.magR);
        WriteDoubleDataset(file, "/signal/time_S", outData.time_S);
        
        // Write meta data
        WriteIntDataset(file, "/meta/stateDet", outData.stateDet);
        WriteIntDataset(file, "/meta/stateTru", outData.stateTru);
        
        // Write refInfo/SampleRate
        {
            hsize_t dims[1] = { 1 };
            DataSpace dataspace(1, dims);
            DataSet dataset = file.createDataSet("/refInfo/SampleRate", PredType::NATIVE_INT, dataspace);
            dataset.write(&outData.sampleRate, PredType::NATIVE_INT);
        }
        
        // Write refInfo/FileFormatVersion
        {
            hsize_t dims[1] = { 1 };
            DataSpace dataspace(1, dims);
            DataSet dataset = file.createDataSet("/refInfo/FileFormatVersion", PredType::NATIVE_INT, dataspace);
            dataset.write(&outData.fileFormatVersion, PredType::NATIVE_INT);
        }
        
        // Write refInfo/CaseName
        if (!outData.caseName.empty()) {
            hsize_t dims[1] = { outData.caseName.size() };
            DataSpace dataspace(1, dims);
            DataSet dataset = file.createDataSet("/refInfo/CaseName", PredType::NATIVE_UINT8, dataspace);
            dataset.write(outData.caseName.data(), PredType::NATIVE_UINT8);
        }
        
        file.close();
        return true;
    }
    catch (const Exception&) {
        outData.Clear();
        return false;
    }
}

bool InspectHDF5File(const std::string& filepath, HDF5FileInfo& info) {
    info.datasets.clear();
    info.filepath = filepath;
    info.isValid = false;
    
    try {
        H5File file(filepath, H5F_ACC_RDONLY);
        
        IterData iterData;
        iterData.file = &file;
        iterData.datasets = &info.datasets;
        iterData.currentPath = "";
        
        H5Literate(file.getId(), H5_INDEX_NAME, H5_ITER_NATIVE, nullptr, 
                   FileIterCallback, &iterData);
        
        file.close();
        info.isValid = true;
        return true;
    }
    catch (...) {
        return false;
    }
}

bool SaveH5AFileFromData(const std::string& filepath, const H5AData& data) {
    if (!data.isLoaded) return false;
    if (data.time_S.empty() || data.magR.empty()) return false;
    
    try {
        H5File file(filepath, H5F_ACC_TRUNC);
        
        // Create groups
        Group signalGroup = file.createGroup("/signal");
        Group metaGroup = file.createGroup("/meta");
        Group refInfoGroup = file.createGroup("/refInfo");
        
        // Write signal/time_S
        {
            hsize_t dims[1] = { data.time_S.size() };
            DataSpace dataspace(1, dims);
            DataSet dataset = signalGroup.createDataSet("time_S", 
                PredType::NATIVE_DOUBLE, dataspace);
            dataset.write(data.time_S.data(), PredType::NATIVE_DOUBLE);
        }
        
        // Write signal/magR
        {
            hsize_t dims[1] = { data.magR.size() };
            DataSpace dataspace(1, dims);
            DataSet dataset = signalGroup.createDataSet("magR", 
                PredType::NATIVE_DOUBLE, dataspace);
            dataset.write(data.magR.data(), PredType::NATIVE_DOUBLE);
        }
        
        // Write meta/stateDet
        {
            hsize_t dims[1] = { data.stateDet.size() };
            DataSpace dataspace(1, dims);
            DataSet dataset = metaGroup.createDataSet("stateDet", 
                PredType::NATIVE_INT, dataspace);
            dataset.write(data.stateDet.data(), PredType::NATIVE_INT);
        }
        
        // Write meta/stateTru
        {
            hsize_t dims[1] = { data.stateTru.size() };
            DataSpace dataspace(1, dims);
            DataSet dataset = metaGroup.createDataSet("stateTru", 
                PredType::NATIVE_INT, dataspace);
            dataset.write(data.stateTru.data(), PredType::NATIVE_INT);
        }
        
        // Write refInfo/SampleRate
        {
            hsize_t dims[1] = { 1 };
            DataSpace dataspace(1, dims);
            DataSet dataset = refInfoGroup.createDataSet("SampleRate", 
                PredType::NATIVE_INT, dataspace);
            int sampleRate = data.sampleRate;
            dataset.write(&sampleRate, PredType::NATIVE_INT);
        }
        
        // Write refInfo/FileFormatVersion
        {
            hsize_t dims[1] = { 1 };
            DataSpace dataspace(1, dims);
            DataSet dataset = refInfoGroup.createDataSet("FileFormatVersion", 
                PredType::NATIVE_INT, dataspace);
            int version = data.fileFormatVersion;
            dataset.write(&version, PredType::NATIVE_INT);
        }
        
        // Write refInfo/CaseName as uint8 array
        {
            std::string caseName = data.caseName;
            if (caseName.empty()) {
                caseName = GetFilenameFromPath(filepath);
                size_t dotPos = caseName.rfind('.');
                if (dotPos != std::string::npos) {
                    caseName = caseName.substr(0, dotPos);
                }
            }
            
            hsize_t dims[1] = { caseName.size() };
            DataSpace dataspace(1, dims);
            DataSet dataset = refInfoGroup.createDataSet("CaseName", 
                PredType::NATIVE_UINT8, dataspace);
            dataset.write(caseName.data(), PredType::NATIVE_UINT8);
        }
        
        file.close();
        return true;
    }
    catch (...) {
        return false;
    }
}

//=============================================================================
// DIALOG IMPLEMENTATION
//=============================================================================

std::string ShowOpenFileDialog(const char* filter) {
    char filename[MAX_PATH] = "";
    
    OPENFILENAMEA ofn = {};
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = GetActiveWindow();
    ofn.lpstrFilter = filter;
    ofn.lpstrFile = filename;
    ofn.nMaxFile = MAX_PATH;
    ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR;
    
    if (GetOpenFileNameA(&ofn)) {
        return std::string(filename);
    }
    return "";
}

std::string ShowSaveFileDialog(const char* filter, const std::string& defaultFilename) {
    char filename[MAX_PATH] = "";
    
    if (!defaultFilename.empty()) {
        strncpy_s(filename, defaultFilename.c_str(), MAX_PATH - 1);
    }
    
    OPENFILENAMEA ofn = {};
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = GetActiveWindow();
    ofn.lpstrFilter = filter;
    ofn.lpstrFile = filename;
    ofn.nMaxFile = MAX_PATH;
    ofn.Flags = OFN_OVERWRITEPROMPT | OFN_NOCHANGEDIR;
    ofn.lpstrDefExt = "h5a";
    
    if (GetSaveFileNameA(&ofn)) {
        return std::string(filename);
    }
    return "";
}

std::vector<std::string> ShowOpenMultiFileDialog(const char* filter) {
    std::vector<std::string> result;
    
    // Use larger buffer for multiple files
    const int BUFFER_SIZE = 32768;
    char* buffer = new char[BUFFER_SIZE];
    memset(buffer, 0, BUFFER_SIZE);
    
    OPENFILENAMEA ofn = {};
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = GetActiveWindow();
    ofn.lpstrFilter = filter;
    ofn.lpstrFile = buffer;
    ofn.nMaxFile = BUFFER_SIZE;
    ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_NOCHANGEDIR | OFN_ALLOWMULTISELECT | OFN_EXPLORER;
    
    if (GetOpenFileNameA(&ofn)) {
        // Check if multiple files selected
        // Format: "directory\0file1\0file2\0...\0\0" or "fullpath\0\0" for single file
        char* p = buffer;
        std::string directory = p;
        p += strlen(p) + 1;
        
        if (*p == '\0') {
            // Single file selected - directory contains full path
            result.push_back(directory);
        } else {
            // Multiple files - directory is first, then filenames
            while (*p != '\0') {
                std::string filepath = directory + "\\" + p;
                result.push_back(filepath);
                p += strlen(p) + 1;
            }
        }
    }
    
    delete[] buffer;
    return result;
}

std::string ShowSelectFolderDialog(const std::string& title) {
    char path[MAX_PATH] = "";
    
    BROWSEINFOA bi = {};
    bi.hwndOwner = GetActiveWindow();
    bi.lpszTitle = title.c_str();
    bi.ulFlags = BIF_RETURNONLYFSDIRS | BIF_NEWDIALOGSTYLE;
    
    LPITEMIDLIST pidl = SHBrowseForFolderA(&bi);
    if (pidl != nullptr) {
        if (SHGetPathFromIDListA(pidl, path)) {
            CoTaskMemFree(pidl);
            return std::string(path);
        }
        CoTaskMemFree(pidl);
    }
    return "";
}

//=============================================================================
// UTILITY IMPLEMENTATION
//=============================================================================

void ResetTruth(ImportData& data) {
    if (!data.isLoaded || data.magDat.time_S.empty()) return;
    
    MagData& magDat = data.magDat;
    const RefData& refDat = data.refDat;
    const std::vector<double>& time_S = magDat.time_S;
    
    // Set all truth to 0
    std::fill(magDat.truth.begin(), magDat.truth.end(), 0);
    
    // Set blood regions (truth = 1)
    size_t numBlood = std::min(refDat.bloodBeg.size(), refDat.bloodEnd.size());
    for (size_t i = 0; i < numBlood; ++i) {
        int startIdx = FindTimeIndex(time_S, refDat.bloodBeg[i]);
        int endIdx = FindTimeIndexEnd(time_S, refDat.bloodEnd[i]);
        if (startIdx >= 0 && endIdx >= startIdx) {
            for (int j = startIdx; j <= endIdx; ++j) {
                magDat.truth[j] = 1;
            }
        }
    }
    
    // Set wall regions (truth = 2)
    size_t numWall = std::min(refDat.wallBeg.size(), refDat.wallEnd.size());
    for (size_t i = 0; i < numWall; ++i) {
        int startIdx = FindTimeIndex(time_S, refDat.wallBeg[i]);
        int endIdx = FindTimeIndexEnd(time_S, refDat.wallEnd[i]);
        if (startIdx >= 0 && endIdx >= startIdx) {
            for (int j = startIdx; j <= endIdx; ++j) {
                magDat.truth[j] = 2;
            }
        }
    }
    
    // Set clot regions (truth = 3)
    size_t numClot = std::min(refDat.clotBeg.size(), refDat.clotEnd.size());
    for (size_t i = 0; i < numClot; ++i) {
        int startIdx = FindTimeIndex(time_S, refDat.clotBeg[i]);
        int endIdx = FindTimeIndexEnd(time_S, refDat.clotEnd[i]);
        if (startIdx >= 0 && endIdx >= startIdx) {
            for (int j = startIdx; j <= endIdx; ++j) {
                magDat.truth[j] = 3;
            }
        }
    }
}

std::string GetFilenameFromPath(const std::string& filepath) {
    size_t lastSlash = filepath.find_last_of("/\\");
    if (lastSlash != std::string::npos) {
        return filepath.substr(lastSlash + 1);
    }
    return filepath;
}
