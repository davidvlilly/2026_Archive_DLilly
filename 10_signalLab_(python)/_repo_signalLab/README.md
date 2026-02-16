# SignalLab

## Overview
SignalLab is a Python-based software tool Viewing, Editing, the Intravenous RF Blood (IVRB) system signal, that is used to detect blood clot formations

## Key Features
- Signal visualization with state-coded markers
- File input support for HDF5 (.f5b) format
- Interactive state selection and editing
- Statistical analysis tools
- Higuchi Fractal Dimension calculation

## System Assumptions
- Signal data sampled at 30 Hz
- Analysis segment interval of 1 second

## Folder Structure
```
signalLab/
├── signalLab.py
├── siglab_lib/
│   ├── __init__.py
│   ├── fileIO.py
│   ├── mainWinSupport.py
│   ├── statsCalc.py
│   ├── higuchiCalc.py
│   ├── extWinStats.py
│   ├── extWinHiguchi.py
│   └── extWinScatter.py
└── notes/
    ├── signalLab_Notes.txt
    └── README.md
```

## State Enumeration Codes
| Value | State   | Color    |
|-------|---------|----------|
| 0     | Unknown | Gray     |
| 1     | Blood1  | Green    |
| 2     | Blood2  | Cyan     |
| 3     | Step    | Black    |
| 4     | Wall    | Blue     |
| 5     | Clot    | Orange   |

## Input File Format
HDF5 File (.f5b) with following datasets:
- `signal/magR`: Signal magnitude (float32)
- `signal/sample_rate_Hz`: Sampling rate
- `signal/time_S`: Time series
- `tag/state`: State information

## Main Data Structures
- `sigStateTru`: Original signal data
- `statsCalc`: Signal statistics
- `higuchiPrm`: Higuchi Complexity Dimension parameters
- `sigStateEst`: Estimated states

## Dependencies
- Python 3.x
- NumPy
- Matplotlib
- h5py
- Tkinter

## License
None

## Contributors
David Lilly