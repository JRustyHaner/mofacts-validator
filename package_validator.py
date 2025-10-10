#!/usr/bin/env python3
"""
MoFaCTS Package Validator

Comprehensive validation script for MoFaCTS zip packages.
Validates structure, JSON syntax, keys, values, and cross-references
based on the package uploader validation logic.
"""

import json
import zipfile
import os
import sys
from typing import Dict, List, Any, Tuple, Optional
import argparse
import re


class PackageValidator:
    """Validates MoFaCTS zip packages with comprehensive checks."""

    def __init__(self, zip_path: str, verbose: bool = False):
        self.zip_path = zip_path
        self.verbose = verbose
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.files: Dict[str, Dict] = {}
        self.tdf_files: List[Dict] = []
        self.stim_files: List[Dict] = []
        self.media_files: List[Dict] = []

    def log(self, message: str):
        """Log message if verbose mode is enabled."""
        if self.verbose:
            print(message)

    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        print(f"ERROR: {message}")

    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
        print(f"WARNING: {message}")

    def validate_zip_exists(self) -> bool:
        """Check if the zip file exists."""
        if not os.path.exists(self.zip_path):
            self.add_error(f"Zip file does not exist: {self.zip_path}")
            return False
        return True

    def extract_and_categorize_files(self) -> bool:
        """Extract zip and categorize files."""
        try:
            with zipfile.ZipFile(self.zip_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    file_path = file_info.filename
                    file_name = os.path.basename(file_path)
                    file_ext = os.path.splitext(file_name)[1].lower()

                    # Read file contents
                    try:
                        with zip_ref.open(file_info) as f:
                            if file_ext == '.json':
                                content = json.loads(f.read().decode('utf-8'))
                                file_type = 'stim' if 'setspec' in content else 'tdf'
                            else:
                                content = f.read()
                                file_type = 'media'
                    except json.JSONDecodeError as e:
                        self.add_error(f"Invalid JSON in file {file_path}: {e}")
                        continue
                    except Exception as e:
                        self.add_error(f"Error reading file {file_path}: {e}")
                        continue

                    file_meta = {
                        'name': file_name,
                        'path': file_path,
                        'extension': file_ext,
                        'content': content,
                        'type': file_type
                    }

                    self.files[file_path] = file_meta

                    if file_type == 'tdf':
                        self.tdf_files.append(file_meta)
                    elif file_type == 'stim':
                        self.stim_files.append(file_meta)
                    elif file_type == 'media':
                        self.media_files.append(file_meta)

            self.log(f"Found {len(self.tdf_files)} TDF files, {len(self.stim_files)} stimulus files, {len(self.media_files)} media files")
            return True

        except zipfile.BadZipFile:
            self.add_error("Invalid zip file")
            return False
        except Exception as e:
            self.add_error(f"Error extracting zip: {e}")
            return False

    def validate_package_structure(self) -> bool:
        """Validate overall package structure."""
        if not self.tdf_files:
            self.add_error("No TDF files found in package")
            return False

        if not self.stim_files:
            self.add_error("No stimulus files found in package")
            return False

        # Check for at least one TDF-stim pair
        valid_pairs = 0
        for tdf in self.tdf_files:
            stim_file_name = self._get_stimulus_file_from_tdf(tdf['content'])
            if stim_file_name and any(stim['name'] == stim_file_name for stim in self.stim_files):
                valid_pairs += 1

        if valid_pairs == 0:
            self.add_error("No valid TDF-stimulus file pairs found")
            return False

        return True

    def validate_json_structure(self) -> bool:
        """Validate JSON structure and required fields."""
        valid = True

        # Validate stimulus files
        for stim_file in self.stim_files:
            if not self._validate_stimulus_file(stim_file):
                valid = False

        # Validate TDF files
        for tdf_file in self.tdf_files:
            if not self._validate_tdf_file(tdf_file):
                valid = False

        return valid

    def _validate_stimulus_file(self, stim_file: Dict) -> bool:
        """Validate a single stimulus file."""
        content = stim_file['content']
        file_name = stim_file['name']

        # Check setspec exists
        if 'setspec' not in content:
            self.add_error(f"Stimulus file '{file_name}' missing 'setspec' key")
            return False

        setspec = content['setspec']

        # Check clusters array
        if 'clusters' not in setspec:
            self.add_error(f"Stimulus file '{file_name}' missing 'clusters' in setspec")
            return False

        clusters = setspec['clusters']
        if not isinstance(clusters, list):
            self.add_error(f"Stimulus file '{file_name}' clusters is not an array")
            return False

        if not clusters:
            self.add_error(f"Stimulus file '{file_name}' has no clusters")
            return False

        # Validate each cluster
        for cluster_idx, cluster in enumerate(clusters):
            if not self._validate_cluster(cluster, cluster_idx, file_name):
                return False

        return True

    def _validate_cluster(self, cluster: Dict, cluster_idx: int, file_name: str) -> bool:
        """Validate a single cluster."""
        if not isinstance(cluster, dict):
            self.add_error(f"Cluster {cluster_idx} in '{file_name}' is not an object")
            return False

        if 'stims' not in cluster:
            self.add_error(f"Cluster {cluster_idx} in '{file_name}' missing 'stims' array")
            return False

        stims = cluster['stims']
        if not isinstance(stims, list) or not stims:
            self.add_error(f"Cluster {cluster_idx} in '{file_name}' has invalid or empty stims array")
            return False

        # Check for duplicate correctResponses
        correct_responses = []
        for stim in stims:
            if isinstance(stim, dict) and 'response' in stim and 'correctResponse' in stim['response']:
                correct_responses.append(stim['response']['correctResponse'])

        if len(correct_responses) != len(set(correct_responses)):
            self.add_error(f"Duplicate correctResponse values in cluster {cluster_idx} of '{file_name}'")
            return False

        # Validate each stimulus
        for stim_idx, stim in enumerate(stims):
            if not self._validate_stimulus(stim, stim_idx, cluster_idx, file_name):
                return False

        # Validate cluster-level fields
        if 'responseType' in cluster:
            response_type = cluster['responseType']
            if not isinstance(response_type, str):
                self.add_error(f"Cluster {cluster_idx} in '{file_name}' responseType must be a string")
                return False
            valid_response_types = ['text', 'audio', 'image', 'video', 'cloze']
            if response_type not in valid_response_types:
                self.add_warning(f"Cluster {cluster_idx} in '{file_name}' responseType '{response_type}' is not a standard type (expected: {', '.join(valid_response_types)})")

        return True

    def _validate_stimulus(self, stim: Dict, stim_idx: int, cluster_idx: int, file_name: str) -> bool:
        """Validate a single stimulus."""
        if not isinstance(stim, dict):
            self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' is not an object")
            return False

        # Validate response object more thoroughly
        if 'response' not in stim:
            self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' missing response object")
            return False

        response = stim['response']
        if not isinstance(response, dict):
            self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' response is not an object")
            return False

        if 'correctResponse' not in response:
            self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' missing correctResponse")
            return False

        # Check for invisible unicode characters that will be removed
        correct_response = str(response['correctResponse'])
        if re.search(r'[\u0080-\u00FF]', correct_response):
            self.add_warning(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' correctResponse contains invisible unicode characters that will be removed")

        # Check incorrectResponses if present
        if 'incorrectResponses' in response:
            incorrect_responses = response['incorrectResponses']
            if isinstance(incorrect_responses, str):
                # String format - should be comma-separated
                if re.search(r'[\u0080-\u00FF]', incorrect_responses):
                    self.add_warning(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' incorrectResponses string contains invisible unicode characters that will be removed")
                pass  # Valid
            elif isinstance(incorrect_responses, list):
                # Array format - check all elements are strings
                for i, ir in enumerate(incorrect_responses):
                    if not isinstance(ir, str):
                        self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' incorrectResponses[{i}] is not a string")
                        return False
                    if re.search(r'[\u0080-\u00FF]', str(ir)):
                        self.add_warning(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' incorrectResponses[{i}] contains invisible unicode characters that will be removed")
            else:
                self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' incorrectResponses must be a string or array")
                return False
        else:
            # Check if incorrectResponses should be present
            # For assessment-type questions, incorrectResponses are typically expected
            display_text = ""
            if 'display' in stim and 'text' in stim['display']:
                display_text = stim['display']['text']

            # Warn if this appears to be a multiple-choice question but lacks incorrectResponses
            if any(indicator in display_text.lower() for indicator in ['?', 'choose', 'select', 'which', 'what is']):
                self.add_warning(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' appears to be a question but missing incorrectResponses")

        # Validate display fields
        if 'display' in stim:
            display = stim['display']
            if not isinstance(display, dict):
                self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' display is not an object")
                return False

            # Check field types
            display_fields = ['text', 'audioSrc', 'imgSrc', 'videoSrc', 'clozeText', 'clozeStimulus', 'textStimulus', 'audioStimulus', 'imageStimulus', 'videoStimulus']
            for field in display_fields:
                if field in display and not isinstance(display[field], str):
                    self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' display.{field} is not a string")
                    return False

        # Validate response object more thoroughly
        if 'response' in stim:
            response = stim['response']
            if not isinstance(response, dict):
                self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' response is not an object")
                return False

            # Check incorrectResponses if present
            if 'incorrectResponses' in response:
                incorrect_responses = response['incorrectResponses']
                if isinstance(incorrect_responses, str):
                    # String format - should be comma-separated
                    pass  # Valid
                elif isinstance(incorrect_responses, list):
                    # Array format - check all elements are strings
                    for i, ir in enumerate(incorrect_responses):
                        if not isinstance(ir, str):
                            self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' incorrectResponses[{i}] is not a string")
                            return False
                else:
                    self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' incorrectResponses must be a string or array")
                    return False
        else:
            self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' missing response object")
            return False

        # Validate parameter field (used for probability calculations)
        if 'parameter' in stim:
            param = stim['parameter']
            if not isinstance(param, str):
                self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' parameter must be a string")
                return False
            # Should be in format like "0,.7"
            if not re.match(r'^\d+(\.\d+)?,\d+(\.\d+)?$', param):
                self.add_warning(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' parameter '{param}' does not match expected format 'number,number'")

        # Validate optimalProb field (required for some delivery methods)
        if 'optimalProb' in stim:
            optimal_prob = stim['optimalProb']
            if not isinstance(optimal_prob, (int, float)):
                self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' optimalProb must be a number")
                return False

        # Validate optional fields
        optional_string_fields = ['speechHintExclusionList']
        for field in optional_string_fields:
            if field in stim and not isinstance(stim[field], str):
                self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' {field} must be a string")
                return False

        optional_array_fields = ['alternateDisplays', 'tags']
        for field in optional_array_fields:
            if field in stim and not isinstance(stim[field], list):
                self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{file_name}' {field} must be an array")
                return False

        return True

    def _validate_tdf_file(self, tdf_file: Dict) -> bool:
        """Validate a single TDF file."""
        content = tdf_file['content']
        file_name = tdf_file['name']

        # Check tutor.setspec
        if 'tutor' not in content or 'setspec' not in content['tutor']:
            self.add_error(f"TDF '{file_name}' missing tutor.setspec")
            return False

        setspec = content['tutor']['setspec']

        # Check lessonname
        if 'lessonname' not in setspec or not isinstance(setspec['lessonname'], str) or not setspec['lessonname'].strip():
            self.add_error(f"TDF '{file_name}' missing or invalid lessonname")
            return False

        # Check stimulusfile
        if 'stimulusfile' not in setspec or not isinstance(setspec['stimulusfile'], str):
            self.add_error(f"TDF '{file_name}' missing or invalid stimulusfile")
            return False

        # Check for experimentTarget and ensure it's lowercase if present
        if 'experimentTarget' in setspec:
            if not isinstance(setspec['experimentTarget'], str):
                self.add_error(f"TDF '{file_name}' experimentTarget is not a string")
                return False
            # Note: In the JS code, experimentTarget gets lowercased during processing

        # Check for unit or unitTemplate
        tutor = content['tutor']
        if 'unit' not in tutor and 'unitTemplate' not in tutor:
            self.add_warning(f"TDF '{file_name}' has no unit or unitTemplate - this may be a root TDF")

        # Check for expected TDF structure to prevent runtime errors
        tutor = content.get('tutor')
        if not tutor:
            self.add_error(f"TDF '{file_name}' missing tutor object")
            return False

        if not isinstance(tutor, dict):
            self.add_error(f"TDF '{file_name}' tutor is not an object")
            return False

        # Validate units and unitTemplates
        units = []
        if 'unit' in tutor:
            unit_data = tutor['unit']
            if not isinstance(unit_data, list):
                self.add_error(f"TDF '{file_name}' tutor.unit must be an array")
                return False
            units.extend(unit_data)

        if 'unitTemplate' in tutor:
            unit_template_data = tutor['unitTemplate']
            if not isinstance(unit_template_data, list):
                self.add_error(f"TDF '{file_name}' tutor.unitTemplate must be an array")
                return False
            units.extend(unit_template_data)

        # Validate each unit
        for unit_idx, unit in enumerate(units):
            if not isinstance(unit, dict):
                self.add_error(f"TDF '{file_name}' unit {unit_idx} is not an object")
                return False

            # Check for clusterIndex if present
            if 'clusterIndex' in unit:
                cluster_index = unit['clusterIndex']
                if not isinstance(cluster_index, (int, str)):
                    self.add_error(f"TDF '{file_name}' unit {unit_idx} clusterIndex must be a number or string")
                    return False

            # Validate assessmentsession if present
            if 'assessmentsession' in unit:
                assess_session = unit['assessmentsession']
                if not isinstance(assess_session, dict):
                    self.add_error(f"TDF '{file_name}' unit {unit_idx} assessmentsession must be an object")
                    return False

                if 'clusterlist' in assess_session:
                    clusterlist = assess_session['clusterlist']
                    if not isinstance(clusterlist, str):
                        self.add_error(f"TDF '{file_name}' unit {unit_idx} assessmentsession.clusterlist must be a string")
                        return False
                    # Validate clusterlist format (comma-separated numbers/ranges)
                    if not self._validate_clusterlist_format(clusterlist):
                        self.add_error(f"TDF '{file_name}' unit {unit_idx} assessmentsession.clusterlist has invalid format")
                        return False

        return True

    def _validate_clusterlist_format(self, clusterlist: str) -> bool:
        """Validate clusterlist format (e.g., '1,2,3-5,7')"""
        parts = clusterlist.split(',')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    if start > end:
                        return False
                except ValueError:
                    return False
            else:
                try:
                    int(part)
                except ValueError:
                    return False
        return True

    def validate_cross_references(self) -> bool:
        """Validate cross-references between TDF and stimulus files."""
        valid = True

        for tdf_file in self.tdf_files:
            stim_file_name = self._get_stimulus_file_from_tdf(tdf_file['content'])
            if not stim_file_name:
                continue

            # Find corresponding stimulus file
            stim_file = next((f for f in self.stim_files if f['name'] == stim_file_name), None)
            if not stim_file:
                self.add_error(f"TDF '{tdf_file['name']}' references stimulus file '{stim_file_name}' which was not found")
                valid = False
                continue

            # Validate cluster references
            if not self._validate_cluster_references(tdf_file, stim_file):
                valid = False

        return valid

    def _get_stimulus_file_from_tdf(self, tdf_content: Dict) -> Optional[str]:
        """Extract stimulus file name from TDF content."""
        try:
            return tdf_content['tutor']['setspec']['stimulusfile']
        except KeyError:
            return None

    def _validate_cluster_references(self, tdf_file: Dict, stim_file: Dict) -> bool:
        """Validate that cluster indices referenced in TDF exist in stimulus file."""
        tdf_content = tdf_file['content']
        stim_content = stim_file['content']

        cluster_indices = self._extract_cluster_indices_from_tdf(tdf_content)
        num_clusters = len(stim_content['setspec']['clusters'])

        valid = True
        for idx in cluster_indices:
            if idx < 0 or idx >= num_clusters:
                self.add_error(f"TDF '{tdf_file['name']}' references cluster index {idx}, but stimulus file '{stim_file['name']}' only has {num_clusters} clusters")
                valid = False

        return valid

    def _extract_cluster_indices_from_tdf(self, tdf: Dict) -> List[int]:
        """Extract cluster indices referenced in TDF."""
        indices = set()

        units = []
        if 'unit' in tdf.get('tutor', {}):
            units.extend(tdf['tutor']['unit'])
        if 'unitTemplate' in tdf.get('tutor', {}):
            units.extend(tdf['tutor']['unitTemplate'])

        for unit in units:
            if 'clusterIndex' in unit:
                try:
                    indices.add(int(unit['clusterIndex']))
                except (ValueError, TypeError):
                    pass

            if 'assessmentsession' in unit and 'clusterlist' in unit['assessmentsession']:
                clusterlist = unit['assessmentsession']['clusterlist']
                if isinstance(clusterlist, str):
                    parts = clusterlist.split(',')
                    for part in parts:
                        part = part.strip()
                        if '-' in part:
                            try:
                                start, end = map(int, part.split('-'))
                                for i in range(start, end + 1):
                                    indices.add(i)
                            except (ValueError, TypeError):
                                pass
                        else:
                            try:
                                indices.add(int(part))
                            except (ValueError, TypeError):
                                pass

        return list(indices)

    def validate_media_references(self) -> bool:
        """Validate media file references in stimulus files."""
        valid = True
        media_names = {f['name'] for f in self.media_files}

        for stim_file in self.stim_files:
            for cluster_idx, cluster in enumerate(stim_file['content']['setspec']['clusters']):
                for stim_idx, stim in enumerate(cluster['stims']):
                    if 'display' in stim:
                        display = stim['display']
                        media_fields = ['audioSrc', 'imgSrc', 'videoSrc']

                        for field in media_fields:
                            if field in display:
                                src = display[field]
                                # Check if it's a URL or local file
                                if not src.startswith('http') and src not in media_names:
                                    self.add_error(f"Stim {stim_idx} in cluster {cluster_idx} of '{stim_file['name']}' references {field} '{src}' which was not found in package")
                                    valid = False

        return valid

    def validate(self) -> bool:
        """Run all validation checks."""
        print(f"Validating package: {self.zip_path}")

        if not self.validate_zip_exists():
            return False

        if not self.extract_and_categorize_files():
            return False

        if not self.validate_package_structure():
            return False

        if not self.validate_json_structure():
            return False

        if not self.validate_cross_references():
            return False

        if not self.validate_media_references():
            return False

        return True

    def get_summary(self) -> Dict:
        """Get validation summary."""
        return {
            'valid': len(self.errors) == 0,
            'errors': self.errors,
            'warnings': self.warnings,
            'file_counts': {
                'tdf': len(self.tdf_files),
                'stimulus': len(self.stim_files),
                'media': len(self.media_files)
            }
        }


def main():
    parser = argparse.ArgumentParser(description='Validate MoFaCTS zip packages')
    parser.add_argument('zip_path', help='Path to the zip package to validate')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    validator = PackageValidator(args.zip_path, args.verbose)

    if validator.validate():
        print("✓ Package validation successful!")
        summary = validator.get_summary()
        print(f"Files found: {summary['file_counts']}")
        if summary['warnings']:
            print(f"Warnings: {len(summary['warnings'])}")
            for warning in summary['warnings']:
                print(f"  - {warning}")
    else:
        print("✗ Package validation failed!")
        summary = validator.get_summary()
        print(f"Errors: {len(summary['errors'])}")
        for error in summary['errors']:
            print(f"  - {error}")
        sys.exit(1)


if __name__ == '__main__':
    main()