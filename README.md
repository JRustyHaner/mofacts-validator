# MoFaCTS Package Validator

A comprehensive validation script for MoFaCTS zip packages that validates structure, JSON syntax, keys, values, and cross-references based on the package uploader validation logic.

### Python Installation

**Windows:**
1. Download Python from [python.org](https://www.python.org/downloads/)
2. Run the installer and ensure "Add Python to PATH" is checked
3. Verify installation: `python --version`

**macOS:**
1. Install using Homebrew: `brew install python`
2. Or download from [python.org](https://www.python.org/downloads/)
3. Verify installation: `python3 --version`

**Linux:**
1. Ubuntu/Debian: `sudo apt update && sudo apt install python3 python3-pip`
2. CentOS/RHEL: `sudo yum install python3 python3-pip` or `sudo dnf install python3 python3-pip`
3. Verify installation: `python3 --version`

## Usage

```bash
python3 package_validator.py <zip_file_path> [-v|--verbose]
```

### Arguments

- `zip_file_path`: Path to the zip package to validate
- `-v, --verbose`: Enable verbose output during validation

### Examples

```bash
# Basic validation
python3 package_validator.py my_package.zip

# Verbose validation with detailed output
python3 package_validator.py my_package.zip -v
```

## What it validates

1. **Package Structure**: Ensures the zip contains at least one TDF-stimulus pair
2. **JSON Syntax**: Validates all JSON files can be parsed correctly
3. **Stimulus Files**: Comprehensive validation including:
   - Required `setspec.clusters` structure
   - Each cluster has `stims` array and optional `responseType`
   - Each stimulus has required fields and proper types
   - Parameter validation (format like "0,.7")
   - Optimal probability validation
   - Response validation with unicode character warnings
   - Display field validation
   - Media reference validation
4. **TDF Files**: Comprehensive validation including:
   - Required `tutor.setspec` structure
   - Unit and unitTemplate validation
   - Cluster index and assessmentsession validation
   - Lesson name and stimulus file references
5. **Cross-references**: Ensures TDF-referenced stimulus files exist and cluster indices are valid
6. **Media References**: Checks that media files referenced in stimuli exist in the package or are valid URLs

## Validation Rules

### Stimulus Files
- Must have `setspec` object with `clusters` array (at least one cluster)
- Each cluster must have `stims` array (at least one stimulus) and optional `responseType` (string)
- Each stimulus must have `response.correctResponse` (string)
- `response.incorrectResponses` (if present) must be a string or array of strings
- **Warning**: Stimuli with question-like display text but missing `incorrectResponses`
- **Warning**: Responses containing invisible unicode characters (\\u0080-\\u00FF) that will be removed
- `parameter` (if present) should be in format "number,number" (e.g., "0,.7")
- `optimalProb` (if present) must be a number
- Display fields (`text`, `audioSrc`, `imgSrc`, `videoSrc`, etc.) must be strings if present
- Optional fields like `speechHintExclusionList` (string), `alternateDisplays` (array), `tags` (array)

### TDF Files
- Must have `tutor.setspec` object
- Must have valid `lessonname` (non-empty string)
- Must have `stimulusfile` (string)
- May have `experimentTarget` (string, gets lowercased during processing)
- `tutor.unit` and `tutor.unitTemplate` (if present) must be arrays
- Units can have `clusterIndex` (number/string) and `assessmentsession` objects
- `assessmentsession.clusterlist` (if present) must be a valid cluster list format (e.g., "1,2,3-5")
- Should have proper structure to prevent runtime errors during processing

### Cross-validation
- Referenced stimulus files must exist in the package
- Cluster indices referenced in TDF units must exist in the stimulus file
- Media file references must either be HTTP URLs or exist in the package

## Exit Codes

- `0`: Validation successful
- `1`: Validation failed (errors found)

## Output
    
The script provides clear error and warning messages. In verbose mode, it shows progress during validation.

