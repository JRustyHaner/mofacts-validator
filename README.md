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
python3 package_validator.py <zip_file_path> [options]
```

### Options

| Option | Description |
|--------|-------------|
| `zip_file_path` | Path to the zip package to validate (required) |
| `-v, --verbose` | Enable verbose output showing validation progress |
| `--timeline` | Generate a unit execution timeline report after validation |
| `-o, --output <file>` | Specify output file for timeline report (default: `<package>_timeline.txt`) |
| `-h, --help` | Show help message and exit |

### Examples

#### Basic Usage

```bash
# Simple validation - shows only errors and warnings
python3 package_validator.py my_package.zip
```

#### Verbose Mode

```bash
# Detailed validation with progress messages
python3 package_validator.py my_package.zip -v
```

This shows:
- File discovery progress
- Which files are being validated
- Cross-reference checks
- Media file validation

#### Timeline Reports

```bash
# Generate timeline report (default output: my_package_timeline.txt)
python3 package_validator.py my_package.zip --timeline

# Generate timeline with custom output file
python3 package_validator.py my_package.zip --timeline -o report.txt

# Verbose validation with timeline
python3 package_validator.py my_package.zip -v --timeline
```

Timeline reports show:
- Unit execution order and duration
- Cluster assignments per unit
- Assessment session details
- Complete execution flow visualization

#### Batch Validation

```bash
# Validate multiple packages
for package in *.zip; do
    echo "Validating $package"
    python3 package_validator.py "$package"
done

# Validate and generate reports for all packages
for package in *.zip; do
    python3 package_validator.py "$package" --timeline -o "${package%.zip}_report.txt"
done
```

#### CI/CD Integration

```bash
# Exit code is 0 on success, 1 on failure
if python3 package_validator.py package.zip; then
    echo "Package is valid, proceeding with deployment"
else
    echo "Package validation failed" >&2
    exit 1
fi
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

## Output Examples

### Successful Validation
```
✓ Package validation successful!
Files found: {'tdf': 2, 'stim': 2, 'media': 5}
```

### Validation with Warnings
```
WARNING: Stimulus file 'stims.json' cluster 0 stimulus 3: Display text appears to be a question but missing incorrectResponses
✓ Package validation successful!
Files found: {'tdf': 1, 'stim': 1, 'media': 0}
Warnings: 1
  - Stimulus file 'stims.json' cluster 0 stimulus 3: Display text appears to be a question but missing incorrectResponses
```

### Failed Validation
```
ERROR: Stimulus file 'myStims.json' missing 'setspec' key
ERROR: TDF file 'myTDF.json' references non-existent stimulus file 'wrongFile.json'
✗ Package validation failed!
Errors: 2
  - Stimulus file 'myStims.json' missing 'setspec' key
  - TDF file 'myTDF.json' references non-existent stimulus file 'wrongFile.json'
```

### Verbose Mode Output
```
Found 1 TDF files, 1 stimulus files, 3 media files
Validating package structure...
Validating JSON structure...
Validating stimulus file: stims.json
Validating TDF file: lesson.json
Validating cross-references...
Validating media references...
✓ Package validation successful!
Files found: {'tdf': 1, 'stim': 1, 'media': 3}
```

## Troubleshooting

### Common Issues

**"No valid TDF-stimulus file pairs found"**
- Ensure TDF's `stimulusfile` field matches the actual stimulus filename in the package
- Check that both files are in the zip archive

**"Invalid JSON in file"**
- Validate your JSON syntax using a JSON validator
- Check for missing commas, brackets, or quotes
- Ensure proper UTF-8 encoding

**"Cluster X in TDF references non-existent cluster index"**
- Verify cluster indices in TDF match those in the stimulus file
- Remember: cluster indices are 0-based

**"Media file referenced but not found"**
- Ensure media files referenced in stimuli are included in the zip
- Or use HTTP/HTTPS URLs for external media
- Check filename spelling and case sensitivity

**Unicode Warning Messages**
- Some responses contain invisible characters that will be stripped
- Review the responses and remove any special characters
- Use standard ASCII characters when possible

## Quick Start

1. **Install Python** (see Python Installation section above)
2. **Download the validator script**
3. **Run validation:**
   ```bash
   python3 package_validator.py your_package.zip
   ```
4. **Fix any errors** reported by the validator
5. **Re-run** until validation succeeds

## Advanced Features

### Timeline Report

The timeline feature generates a detailed execution flow report showing:

- **Unit Order**: Visual representation of unit execution sequence
- **Duration**: Time allocation for each unit
- **Cluster Mapping**: Which clusters are practiced in each unit
- **Assessment Sessions**: Special assessment unit details

Example timeline output:
```
Unit Execution Timeline
=======================
Total Estimated Time: 45 minutes

Unit 1 (Practice) - 10 minutes
  Clusters: 0, 1, 2
  
Unit 2 (Practice) - 10 minutes
  Clusters: 3, 4
  
Unit 3 (Assessment)
  Assessment Clusters: 0-4
```

This helps instructors and content creators understand the learning flow and pacing.

## Tips for Content Creators

1. **Start with verbose mode** during development to see detailed feedback
2. **Use timeline reports** to visualize and verify learning progression
3. **Test incrementally** - validate after adding each new unit or cluster
4. **Check warnings carefully** - they often indicate potential student confusion
5. **Validate media files** - missing media breaks the learning experience
6. **Use descriptive filenames** - makes debugging easier

## Integration with Build Systems

### Makefile Example
```makefile
validate:
	python3 package_validator.py package.zip

validate-verbose:
	python3 package_validator.py package.zip -v

report:
	python3 package_validator.py package.zip --timeline

all: validate report
```

### GitHub Actions Example
```yaml
- name: Validate MoFaCTS Package
  run: python3 package_validator.py dist/package.zip -v --timeline
  
- name: Upload Timeline Report
  uses: actions/upload-artifact@v3
  with:
    name: timeline-report
    path: dist/package_timeline.txt
```

