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
            
            # Validate video session question references
            if not self._validate_video_session_questions(tdf_file, stim_file):
                valid = False
            
            # Validate learning session clusterlist
            if not self._validate_learning_session_clusterlist(tdf_file, stim_file):
                valid = False
            
            # Validate assessment session clusterlist
            if not self._validate_assessment_session_clusterlist(tdf_file, stim_file):
                valid = False
            
            # Validate adaptive logic
            if not self._validate_adaptive_logic(tdf_file, stim_file):
                valid = False
            
            # Check for architectural mismatches (nested structure issues)
            self._check_architectural_issues(tdf_file, stim_file)

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

    def _validate_video_session_questions(self, tdf_file: Dict, stim_file: Dict) -> bool:
        """Validate video session questions exist in stimulus file and have proper structure."""
        tdf_content = tdf_file['content']
        stim_content = stim_file['content']
        tdf_name = tdf_file['name']
        valid = True

        # Check all units for video sessions
        units = []
        if 'unit' in tdf_content.get('tutor', {}):
            unit_data = tdf_content['tutor']['unit']
            if isinstance(unit_data, list):
                units = unit_data
            else:
                units = [unit_data]

        for unit_idx, unit in enumerate(units):
            if 'videosession' not in unit:
                continue

            videosession = unit['videosession']
            
            # Check if questions field exists
            if 'questions' not in videosession:
                self.add_warning(f"TDF '{tdf_name}' unit {unit_idx} has videosession but no 'questions' array")
                continue

            questions = videosession['questions']
            
            # Validate questions is an array
            if not isinstance(questions, list):
                self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: videosession.questions must be an array, got {type(questions).__name__}")
                valid = False
                continue

            # Validate questiontimes if present
            if 'questiontimes' in videosession:
                question_times = videosession['questiontimes']
                if not isinstance(question_times, list):
                    self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: videosession.questiontimes must be an array")
                    valid = False
                elif len(question_times) != len(questions):
                    self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: videosession.questiontimes length ({len(question_times)}) doesn't match questions length ({len(questions)})")
                    valid = False

            num_clusters = len(stim_content['setspec']['clusters'])
            
            # Validate each question cluster exists
            for q_idx, cluster_id in enumerate(questions):
                if not isinstance(cluster_id, int):
                    self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: question[{q_idx}] is not an integer (got {cluster_id})")
                    valid = False
                    continue

                if cluster_id < 0 or cluster_id >= num_clusters:
                    error_msg = f"TDF '{tdf_name}' unit {unit_idx}: question cluster {cluster_id} does not exist in stimulus file (has {num_clusters} clusters: 0-{num_clusters-1})"
                    self.add_error(error_msg)
                    print(f"  ⚠️  Video Question Issue: {error_msg}")
                    valid = False
                    continue

                # Validate the cluster structure for video questions
                cluster = stim_content['setspec']['clusters'][cluster_id]
                if not self._validate_video_question_cluster(cluster, cluster_id, tdf_name, unit_idx):
                    valid = False

            # Validate checkpoint behavior
            if 'checkpointBehavior' in videosession:
                behavior = videosession['checkpointBehavior']
                valid_behaviors = ['none', 'all', 'some', 'adaptive']
                if behavior not in valid_behaviors:
                    self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: invalid checkpointBehavior '{behavior}', must be one of {valid_behaviors}")
                    valid = False

                # Validate adaptive checkpoints
                if behavior == 'adaptive':
                    if 'checkpoints' not in videosession:
                        self.add_warning(f"TDF '{tdf_name}' unit {unit_idx}: checkpointBehavior is 'adaptive' but no 'checkpoints' array defined")
                    elif not isinstance(videosession['checkpoints'], list):
                        self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: videosession.checkpoints must be an array")
                        valid = False

                # Validate 'some' checkpoint behavior
                if behavior == 'some':
                    if 'checkpointQuestions' in videosession:
                        if not isinstance(videosession['checkpointQuestions'], list):
                            self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: videosession.checkpointQuestions must be an array")
                            valid = False
                    else:
                        # Check if stims have checkpoint property
                        has_checkpoint_prop = False
                        for cluster_id in questions:
                            if cluster_id < num_clusters:
                                cluster = stim_content['setspec']['clusters'][cluster_id]
                                for stim in cluster.get('stims', []):
                                    if 'checkpoint' in stim:
                                        has_checkpoint_prop = True
                                        break
                        if not has_checkpoint_prop:
                            self.add_warning(f"TDF '{tdf_name}' unit {unit_idx}: checkpointBehavior is 'some' but no checkpointQuestions array and no stims have 'checkpoint' property")

        return valid

    def _validate_video_question_cluster(self, cluster: Dict, cluster_id: int, tdf_name: str, unit_idx: int) -> bool:
        """Validate a cluster intended for video questions has appropriate structure."""
        valid = True

        if 'stims' not in cluster or not cluster['stims']:
            self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: video question cluster {cluster_id} has no stims")
            return False

        has_multiple_choice = False
        has_text_response = False

        for stim_idx, stim in enumerate(cluster['stims']):
            # Check if it's a multiple-choice question
            if 'response' in stim:
                response = stim['response']
                if isinstance(response, dict):
                    response_type = response.get('type', 'text')
                    
                    # For video questions, multiple choice is recommended
                    if response_type in ['selectone', 'selectmultiple']:
                        has_multiple_choice = True
                        # Validate options exist
                        if 'options' not in response:
                            self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: video question cluster {cluster_id}, stim {stim_idx} has type '{response_type}' but no options array")
                            valid = False
                        elif not isinstance(response['options'], list) or len(response['options']) < 2:
                            self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: video question cluster {cluster_id}, stim {stim_idx} needs at least 2 options for type '{response_type}'")
                            valid = False
                    elif response_type == 'text' or 'correctResponse' in response:
                        # This is a text-based response (like flashcards)
                        has_text_response = True

        # No warnings - timeline report will show response types

        return valid

    def _validate_learning_session_clusterlist(self, tdf_file: Dict, stim_file: Dict) -> bool:
        """Validate learning session clusterlist format and references."""
        tdf_content = tdf_file['content']
        stim_content = stim_file['content']
        tdf_name = tdf_file['name']
        valid = True

        units = []
        if 'unit' in tdf_content.get('tutor', {}):
            unit_data = tdf_content['tutor']['unit']
            if isinstance(unit_data, list):
                units = unit_data
            else:
                units = [unit_data]

        for unit_idx, unit in enumerate(units):
            if 'learningsession' not in unit:
                continue

            learningsession = unit['learningsession']
            
            if 'clusterlist' not in learningsession:
                self.add_warning(f"TDF '{tdf_name}' unit {unit_idx} has learningsession but no 'clusterlist'")
                continue

            clusterlist = learningsession['clusterlist']
            
            # Must be a string
            if not isinstance(clusterlist, str):
                self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: learningsession.clusterlist must be a string, got {type(clusterlist).__name__}")
                valid = False
                continue

            # Validate format (space-separated, ranges allowed like "0-60")
            if not self._validate_clusterlist_format(clusterlist):
                self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: learningsession.clusterlist has invalid format: '{clusterlist}'")
                valid = False
                continue

            # Validate cluster indices exist
            cluster_indices = self._extract_cluster_indices_from_clusterlist(clusterlist)
            num_clusters = len(stim_content['setspec']['clusters'])
            
            for idx in cluster_indices:
                if idx < 0 or idx >= num_clusters:
                    error_msg = f"TDF '{tdf_name}' unit {unit_idx}: clusterlist references cluster {idx} which doesn't exist (valid range: 0-{num_clusters-1})"
                    self.add_error(error_msg)
                    print(f"  ⚠️  Learning Session Issue: {error_msg}")
                    valid = False

        return valid

    def _extract_cluster_indices_from_clusterlist(self, clusterlist: str) -> List[int]:
        """Extract cluster indices from space-separated clusterlist string (supports ranges like '0-60')."""
        indices = set()
        parts = clusterlist.strip().split()
        
        for part in parts:
            part = part.strip()
            if not part:
                continue
                
            if '-' in part:
                # Handle range like "0-60"
                try:
                    start, end = part.split('-', 1)
                    start_idx = int(start)
                    end_idx = int(end)
                    for i in range(start_idx, end_idx + 1):
                        indices.add(i)
                except (ValueError, TypeError):
                    pass
            else:
                # Single number
                try:
                    indices.add(int(part))
                except (ValueError, TypeError):
                    pass

        return sorted(list(indices))

    def _validate_assessment_session_clusterlist(self, tdf_file: Dict, stim_file: Dict) -> bool:
        """Validate assessment session clusterlist format and references."""
        tdf_content = tdf_file['content']
        stim_content = stim_file['content']
        tdf_name = tdf_file['name']
        valid = True

        units = []
        if 'unit' in tdf_content.get('tutor', {}):
            unit_data = tdf_content['tutor']['unit']
            if isinstance(unit_data, list):
                units = unit_data
            else:
                units = [unit_data]

        for unit_idx, unit in enumerate(units):
            if 'assessmentsession' not in unit:
                continue

            assessmentsession = unit['assessmentsession']
            
            if 'clusterlist' not in assessmentsession:
                self.add_warning(f"TDF '{tdf_name}' unit {unit_idx} has assessmentsession but no 'clusterlist'")
                continue

            clusterlist = assessmentsession['clusterlist']
            
            # Must be a string
            if not isinstance(clusterlist, str):
                self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: assessmentsession.clusterlist must be a string, got {type(clusterlist).__name__}")
                valid = False
                continue

            # Validate format
            if not self._validate_clusterlist_format(clusterlist):
                self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: assessmentsession.clusterlist has invalid format: '{clusterlist}'")
                valid = False
                continue

            # Validate cluster indices exist
            cluster_indices = self._extract_cluster_indices_from_clusterlist(clusterlist)
            num_clusters = len(stim_content['setspec']['clusters'])
            
            for idx in cluster_indices:
                if idx < 0 or idx >= num_clusters:
                    error_msg = f"TDF '{tdf_name}' unit {unit_idx}: assessmentsession clusterlist references cluster {idx} which doesn't exist (valid range: 0-{num_clusters-1})"
                    self.add_error(error_msg)
                    print(f"  ⚠️  Assessment Session Issue: {error_msg}")
                    valid = False

        return valid

    def _validate_adaptive_logic(self, tdf_file: Dict, stim_file: Dict) -> bool:
        """Validate adaptive logic syntax and cluster references."""
        tdf_content = tdf_file['content']
        stim_content = stim_file['content']
        tdf_name = tdf_file['name']
        valid = True

        units = []
        if 'unit' in tdf_content.get('tutor', {}):
            unit_data = tdf_content['tutor']['unit']
            if isinstance(unit_data, list):
                units = unit_data
            else:
                units = [unit_data]

        for unit_idx, unit in enumerate(units):
            if 'adaptive' not in unit:
                continue

            adaptive_logic = unit['adaptive']
            
            if not isinstance(adaptive_logic, list):
                self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: 'adaptive' must be an array of logic strings")
                valid = False
                continue

            num_clusters = len(stim_content['setspec']['clusters'])

            for logic_idx, logic_string in enumerate(adaptive_logic):
                if not isinstance(logic_string, str):
                    self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: adaptive[{logic_idx}] must be a string")
                    valid = False
                    continue

                # Basic syntax validation
                if not logic_string.startswith('IF'):
                    self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: adaptive[{logic_idx}] must start with 'IF': '{logic_string}'")
                    valid = False
                    continue

                if 'THEN' not in logic_string:
                    self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: adaptive[{logic_idx}] must contain 'THEN': '{logic_string}'")
                    valid = False
                    continue

                # Extract action part (after THEN)
                parts = logic_string.split('THEN')
                if len(parts) < 2:
                    continue
                    
                action = parts[1].strip()
                
                # Extract cluster references from action (format: C<cluster>S<stim>)
                import re
                cluster_refs = re.findall(r'C(\d+)S(\d+)', action)
                
                for cluster_str, stim_str in cluster_refs:
                    cluster_id = int(cluster_str)
                    stim_id = int(stim_str)
                    
                    # Validate cluster exists
                    if cluster_id < 0 or cluster_id >= num_clusters:
                        error_msg = f"TDF '{tdf_name}' unit {unit_idx}: adaptive[{logic_idx}] references non-existent cluster C{cluster_id} (valid: 0-{num_clusters-1})"
                        self.add_error(error_msg)
                        print(f"  ⚠️  Adaptive Logic Issue: {error_msg}")
                        valid = False
                        continue
                    
                    # Validate stim exists in cluster
                    cluster = stim_content['setspec']['clusters'][cluster_id]
                    num_stims = len(cluster.get('stims', []))
                    if stim_id < 0 or stim_id >= num_stims:
                        error_msg = f"TDF '{tdf_name}' unit {unit_idx}: adaptive[{logic_idx}] references C{cluster_id}S{stim_id} but cluster {cluster_id} only has {num_stims} stims (0-{num_stims-1})"
                        self.add_error(error_msg)
                        print(f"  ⚠️  Adaptive Logic Issue: {error_msg}")
                        valid = False

                # Check for CHECKPOINT keyword with AT time specification
                if 'CHECKPOINT' in logic_string and 'AT' not in logic_string:
                    self.add_warning(f"TDF '{tdf_name}' unit {unit_idx}: adaptive[{logic_idx}] has CHECKPOINT but no AT time specification")

        return valid

    def _check_architectural_issues(self, tdf_file: Dict, stim_file: Dict):
        """Check for architectural mismatches between stimulus structure and MoFaCTS expectations."""
        stim_content = stim_file['content']
        stim_name = stim_file['name']
        
        clusters = stim_content['setspec']['clusters']
        
        for cluster_idx, cluster in enumerate(clusters):
            stims = cluster.get('stims', [])
            if not stims:
                continue
            
            for stim_idx, stim in enumerate(stims):
                # Check for nested incorrectResponses that should be at root level
                if 'response' in stim and isinstance(stim['response'], dict):
                    response_obj = stim['response']
                    if 'incorrectResponses' in response_obj and response_obj['incorrectResponses']:
                        # Check if it's also at root (which would be correct)
                        if 'incorrectResponses' not in stim:
                            warning_msg = (
                                f"Stimulus '{stim_name}' cluster {cluster_idx} stim {stim_idx}: "
                                f"ARCHITECTURAL MISMATCH - incorrectResponses is nested in 'response' object. "
                                f"MoFaCTS expects it at stim root level. Multiple-choice will display as text input!"
                            )
                            self.add_warning(warning_msg)
                            print(f"  ⚠️  Architectural Issue: {warning_msg}")

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

    def validate_session_consistency(self) -> bool:
        """Validate consistency between session types and their requirements."""
        valid = True

        for tdf_file in self.tdf_files:
            tdf_content = tdf_file['content']
            tdf_name = tdf_file['name']

            units = []
            if 'unit' in tdf_content.get('tutor', {}):
                unit_data = tdf_content['tutor']['unit']
                if isinstance(unit_data, list):
                    units = unit_data
                else:
                    units = [unit_data]

            for unit_idx, unit in enumerate(units):
                session_types = []
                
                if 'videosession' in unit:
                    session_types.append('videosession')
                if 'learningsession' in unit:
                    session_types.append('learningsession')
                if 'assessmentsession' in unit:
                    session_types.append('assessmentsession')

                # Warn if multiple session types in one unit
                if len(session_types) > 1:
                    self.add_warning(f"TDF '{tdf_name}' unit {unit_idx} has multiple session types: {', '.join(session_types)}")

                # Check for video session requirements
                if 'videosession' in unit:
                    videosession = unit['videosession']
                    
                    if 'videosource' not in videosession:
                        self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: videosession missing required 'videosource'")
                        valid = False
                    
                    if 'questions' not in videosession:
                        self.add_warning(f"TDF '{tdf_name}' unit {unit_idx}: videosession has no 'questions' array")
                    elif 'questiontimes' not in videosession:
                        self.add_warning(f"TDF '{tdf_name}' unit {unit_idx}: videosession has 'questions' but no 'questiontimes'")
                    
                    # Check for preventScrubbing without appropriate checkpoint settings
                    if videosession.get('preventScrubbing') and not videosession.get('checkpointBehavior'):
                        self.add_warning(f"TDF '{tdf_name}' unit {unit_idx}: preventScrubbing is true but checkpointBehavior is not set")

                # Check for learning session requirements
                if 'learningsession' in unit:
                    learningsession = unit['learningsession']
                    
                    if 'clusterlist' not in learningsession:
                        self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: learningsession missing required 'clusterlist'")
                        valid = False

                # Check for assessment session requirements
                if 'assessmentsession' in unit:
                    assessmentsession = unit['assessmentsession']
                    
                    if 'clusterlist' not in assessmentsession:
                        self.add_error(f"TDF '{tdf_name}' unit {unit_idx}: assessmentsession missing required 'clusterlist'")
                        valid = False

        return valid

    def generate_unit_timelines(self) -> Dict[str, List[Dict]]:
        """Generate execution timelines for all units in all TDF files."""
        timelines = {}
        
        for tdf_file in self.tdf_files:
            tdf_content = tdf_file['content']
            tdf_name = tdf_file['name']
            
            # Find the corresponding stimulus file
            stim_file_name = self._get_stimulus_file_from_tdf(tdf_content)
            stim_file = None
            if stim_file_name:
                stim_file = next((f for f in self.stim_files if f['name'] == stim_file_name), None)
            
            units = []
            if 'unit' in tdf_content.get('tutor', {}):
                unit_data = tdf_content['tutor']['unit']
                if isinstance(unit_data, list):
                    units = unit_data
                else:
                    units = [unit_data]
            
            tdf_timeline = []
            
            for unit_idx, unit in enumerate(units):
                unit_timeline = self._generate_unit_timeline(unit, unit_idx, stim_file, tdf_name)
                tdf_timeline.append(unit_timeline)
            
            timelines[tdf_name] = tdf_timeline
        
        return timelines

    def _generate_unit_timeline(self, unit: Dict, unit_idx: int, stim_file: Optional[Dict], tdf_name: str) -> Dict:
        """Generate timeline for a single unit."""
        timeline = {
            'unit_index': unit_idx,
            'unit_name': unit.get('unitname', f'Unit {unit_idx}'),
            'session_type': None,
            'events': []
        }
        
        # Determine session type
        if 'videosession' in unit:
            timeline['session_type'] = 'video'
            self._add_video_timeline_events(unit, timeline, stim_file, tdf_name)
        elif 'learningsession' in unit:
            timeline['session_type'] = 'learning'
            self._add_learning_timeline_events(unit, timeline, stim_file, tdf_name)
        elif 'assessmentsession' in unit:
            timeline['session_type'] = 'assessment'
            self._add_assessment_timeline_events(unit, timeline, stim_file, tdf_name)
        else:
            # Instruction-only unit
            timeline['session_type'] = 'instruction'
            if 'unitinstructions' in unit:
                timeline['events'].append({
                    'type': 'instruction',
                    'description': 'Display unit instructions',
                    'details': {
                        'has_instructions': True,
                        'has_timer': 'timer' in unit
                    }
                })
        
        # Check for lockout
        if 'deliveryparams' in unit:
            dp = unit['deliveryparams']
            if isinstance(dp, list) and len(dp) > 0:
                dp = dp[0]
            if isinstance(dp, dict) and 'lockoutminutes' in dp:
                timeline['events'].insert(0, {
                    'type': 'lockout',
                    'description': f"Lockout period: {dp['lockoutminutes']} minutes",
                    'details': {'duration_minutes': dp['lockoutminutes']}
                })
        
        # Adaptive logic diagram (unit-level 'adaptive' rules)
        if 'adaptive' in unit and isinstance(unit['adaptive'], list) and unit['adaptive']:
            adaptive_rules = unit['adaptive']
            parsed_rules = []
            import re
            for idx, rule in enumerate(adaptive_rules, 1):
                if not isinstance(rule, str) or 'THEN' not in rule:
                    parsed_rules.append({'index': idx, 'raw': rule, 'condition': None, 'actions': [], 'warning': 'Malformed rule (missing THEN or not a string)'});
                    continue
                parts = rule.split('THEN', 1)
                condition = parts[0].strip()
                action = parts[1].strip()
                refs = re.findall(r'C(\d+)S(\d+)', action)
                actions = []
                for c_str, s_str in refs:
                    try:
                        c_id = int(c_str); s_id = int(s_str)
                        actions.append({'cluster': c_id, 'stim': s_id})
                    except ValueError:
                        pass
                parsed_rules.append({'index': idx, 'raw': rule, 'condition': condition, 'actions': actions})

            # Build ASCII diagram lines
            diagram_lines = []
            for entry in parsed_rules:
                idx = entry['index']
                if entry.get('warning'):
                    diagram_lines.append(f"Rule {idx}: [WARNING] {entry['warning']} :: {entry['raw']}")
                    continue
                cond = entry['condition'] or 'UNKNOWN'
                diagram_lines.append(f"Rule {idx}: {cond}")
                if entry['actions']:
                    for act in entry['actions']:
                        diagram_lines.append(f"  └─ C{act['cluster']}S{act['stim']}")
                else:
                    diagram_lines.append("  └─ (no cluster actions parsed)")

            timeline['events'].append({
                'type': 'adaptive_logic_diagram',
                'description': 'Adaptive branching diagram',
                'details': {
                    'logic_rule_count': len(parsed_rules),
                    'diagram_lines': diagram_lines,
                    'raw_rules': adaptive_rules
                }
            })
        
        return timeline

    def _add_video_timeline_events(self, unit: Dict, timeline: Dict, stim_file: Optional[Dict], tdf_name: str):
        """Add timeline events for video session."""
        videosession = unit['videosession']
        
        timeline['events'].append({
            'type': 'video_start',
            'description': 'Video playback begins',
            'details': {
                'video_source': videosession.get('videosource', 'N/A'),
                'prevent_scrubbing': videosession.get('preventScrubbing', False),
                'checkpoint_behavior': videosession.get('checkpointBehavior', 'none'),
                'rewind_on_incorrect': videosession.get('rewindOnIncorrect', False)
            }
        })
        
        questions = videosession.get('questions', [])
        question_times = videosession.get('questiontimes', [])
        
        # Pair questions with times
        for idx, cluster_id in enumerate(questions):
            time = question_times[idx] if idx < len(question_times) else None
            
            # Get question details from stim file
            question_details = self._get_question_details(cluster_id, stim_file)
            
            timeline['events'].append({
                'type': 'video_question',
                'time_seconds': time,
                'description': f"Video pauses for question at {time}s" if time else "Video pauses for question",
                'details': {
                    'cluster_index': cluster_id,
                    'question_number': idx + 1,
                    'total_questions': len(questions),
                    **question_details
                }
            })
        
        # Check for adaptive logic
        if 'adaptiveLogic' in videosession:
            timeline['events'].append({
                'type': 'adaptive_processing',
                'description': 'Adaptive logic may add additional questions dynamically',
                'details': {
                    'logic_count': len(videosession['adaptiveLogic']),
                    'logic_rules': videosession['adaptiveLogic']
                }
            })
        
        timeline['events'].append({
            'type': 'video_end',
            'description': 'Video playback completes',
            'details': {}
        })

    def _add_learning_timeline_events(self, unit: Dict, timeline: Dict, stim_file: Optional[Dict], tdf_name: str):
        """Add timeline events for learning session."""
        learningsession = unit['learningsession']
        
        clusterlist = learningsession.get('clusterlist', '')
        cluster_indices = self._extract_cluster_indices_from_clusterlist(clusterlist)
        
        timeline['events'].append({
            'type': 'learning_start',
            'description': 'Learning session begins',
            'details': {
                'cluster_count': len(cluster_indices),
                'cluster_range': clusterlist,
                'unit_mode': learningsession.get('unitMode', 'default'),
                'practice_time': unit.get('deliveryparams', {}).get('practiceseconds', 'N/A')
            }
        })
        
        # List ALL clusters as questions
        total_q = len(cluster_indices)
        for i, cluster_id in enumerate(cluster_indices):
            question_details = self._get_question_details(cluster_id, stim_file)
            timeline['events'].append({
                'type': 'learning_question',
                'description': f"Question {i+1}/{total_q} (cluster {cluster_id})",
                'details': {
                    'cluster_index': cluster_id,
                    'question_number': i+1,
                    'total_questions': total_q,
                    **question_details
                }
            })
        
        timeline['events'].append({
            'type': 'learning_end',
            'description': 'Learning session completes',
            'details': {}
        })

    def _add_assessment_timeline_events(self, unit: Dict, timeline: Dict, stim_file: Optional[Dict], tdf_name: str):
        """Add timeline events for assessment session."""
        assessmentsession = unit['assessmentsession']
        
        clusterlist = assessmentsession.get('clusterlist', '')
        cluster_indices = self._extract_cluster_indices_from_clusterlist(clusterlist)
        
        timeline['events'].append({
            'type': 'assessment_start',
            'description': 'Assessment session begins',
            'details': {
                'cluster_count': len(cluster_indices),
                'cluster_range': clusterlist,
                'randomize_groups': assessmentsession.get('randomizegroups', 'false')
            }
        })
        
        # List ALL clusters as questions
        total_q = len(cluster_indices)
        for i, cluster_id in enumerate(cluster_indices):
            question_details = self._get_question_details(cluster_id, stim_file)
            timeline['events'].append({
                'type': 'assessment_question',
                'description': f"Question {i+1}/{total_q} (cluster {cluster_id})",
                'details': {
                    'cluster_index': cluster_id,
                    'question_number': i+1,
                    'total_questions': total_q,
                    **question_details
                }
            })
        
        timeline['events'].append({
            'type': 'assessment_end',
            'description': 'Assessment session completes',
            'details': {}
        })

    def _get_question_details(self, cluster_id: int, stim_file: Optional[Dict]) -> Dict:
        """Extract question type and answer type details from cluster."""
        details = {
            'response_type': 'unknown',
            'answer_type': 'unknown',
            'has_options': False,
            'num_options': 0,
            'has_media': False,
            'media_types': [],
            'warnings': []
        }
        
        if not stim_file:
            details['warnings'].append('⚠ Stimulus file not found')
            return details
        
        try:
            clusters = stim_file['content']['setspec']['clusters']
            if cluster_id >= len(clusters):
                details['warnings'].append(f'⚠ Cluster {cluster_id} does not exist (max: {len(clusters)-1})')
                return details
            
            cluster = clusters[cluster_id]
            stims = cluster.get('stims', [])
            
            if not stims:
                details['warnings'].append(f'⚠ Cluster {cluster_id} has no stimuli')
                return details
            
            # Analyze first stim
            stim = stims[0]
            
            # Check for nested response structure issue (MoFaCTS architectural mismatch)
            # MoFaCTS expects incorrectResponses at stim root, not nested in response object
            if 'response' in stim and isinstance(stim['response'], dict):
                response_obj = stim['response']
                if 'incorrectResponses' in response_obj and response_obj['incorrectResponses']:
                    # This is nested - check if it's also at root (which would be correct)
                    if 'incorrectResponses' not in stim:
                        details['warnings'].append(
                            f"⚠ ARCHITECTURAL MISMATCH: Cluster {cluster_id} has incorrectResponses nested in 'response' object. "
                            f"MoFaCTS expects incorrectResponses at stim root level (stim.incorrectResponses, not stim.response.incorrectResponses). "
                            f"This will cause multiple-choice questions to display as text-input flashcards instead of showing button options."
                        )
            
            # Get question text from display
            if 'display' in stim:
                display = stim['display']
                
                # Get question text
                if 'text' in display:
                    question_text = display['text']
                    # Strip HTML tags for cleaner output
                    import re
                    question_text = re.sub('<[^<]+?>', '', question_text)
                    # Truncate if too long
                    if len(question_text) > 200:
                        question_text = question_text[:200] + '...'
                    details['question_text'] = question_text
                
                # Check for media
                media_types = []
                if 'audioSrc' in display:
                    media_types.append('audio')
                    details['audio_file'] = display['audioSrc']
                if 'imgSrc' in display:
                    media_types.append('image')
                    details['image_file'] = display['imgSrc']
                if 'videoSrc' in display:
                    media_types.append('video')
                    details['video_file'] = display['videoSrc']
                
                details['has_media'] = len(media_types) > 0
                details['media_types'] = media_types
            
            # Check response type
            if 'response' in stim:
                response = stim['response']
                if isinstance(response, dict):
                    response_type = response.get('type', 'text')
                    details['response_type'] = response_type
                    
                    if response_type in ['selectone', 'selectmultiple']:
                        details['answer_type'] = 'multiple_choice'
                        options = response.get('options', [])
                        details['has_options'] = len(options) > 0
                        details['num_options'] = len(options)
                        
                        if not options:
                            details['warnings'].append(f'⚠ Multiple-choice question has no options')
                        elif len(options) < 2:
                            details['warnings'].append(f'⚠ Multiple-choice question needs at least 2 options (has {len(options)})')
                        
                        # Extract choice text
                        if options:
                            choices = []
                            has_correct = False
                            for opt in options:
                                if isinstance(opt, dict):
                                    choice_text = opt.get('text', opt.get('id', 'N/A'))
                                    choice_id = opt.get('id', '')
                                    is_correct = (choice_id == response.get('correctResponse'))
                                    if is_correct:
                                        has_correct = True
                                    choices.append({
                                        'id': choice_id,
                                        'text': choice_text,
                                        'correct': is_correct
                                    })
                                else:
                                    choices.append({'text': str(opt), 'correct': False})
                            details['choices'] = choices
                            
                            if not has_correct:
                                details['warnings'].append(f'⚠ No option marked as correct answer')
                    # Inferred multiple choice: text response with correctResponse + incorrectResponses
                    elif 'correctResponse' in response:
                        incorrect_list = response.get('incorrectResponses')
                        if isinstance(incorrect_list, list) and len(incorrect_list) > 0:
                            # Treat as multiple choice even though type says text
                            details['answer_type'] = 'multiple_choice'
                            details['has_options'] = True
                            # Build choices: correct first, then incorrect
                            choices = []
                            correct_val = str(response['correctResponse'])
                            choices.append({'id': 'correct', 'text': correct_val, 'correct': True})
                            for idx, inc in enumerate(incorrect_list):
                                choices.append({'id': f'inc{idx}', 'text': str(inc), 'correct': False})
                            details['choices'] = choices
                            details['num_options'] = len(choices)
                            details['warnings'].append("⚠ Inferred multiple-choice (correctResponse + incorrectResponses) but response.type='text'")
                        else:
                            # Plain text input
                            details['answer_type'] = 'text_input'
                            details['correct_answer'] = str(response['correctResponse'])
                    
                    # Get incorrect responses if present
                    if 'incorrectResponses' in response:
                        incorrect = response['incorrectResponses']
                        if isinstance(incorrect, list):
                            details['incorrect_answers'] = incorrect[:5]  # Limit to first 5
            
        except (KeyError, IndexError, TypeError):
            pass
        
        return details

    def write_timeline_report(self, output_file: str):
        """Write timeline report to file."""
        timelines = self.generate_unit_timelines()
        
        with open(output_file, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("MoFaCTS PACKAGE EXECUTION TIMELINE REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            for tdf_name, tdf_timeline in timelines.items():
                f.write(f"\n{'=' * 80}\n")
                f.write(f"TDF: {tdf_name}\n")
                f.write(f"{'=' * 80}\n\n")
                
                for unit_timeline in tdf_timeline:
                    f.write(f"  Unit {unit_timeline['unit_index']}: {unit_timeline['unit_name']}\n")
                    f.write(f"  Session Type: {unit_timeline['session_type']}\n")
                    f.write(f"  {'-' * 76}\n\n")
                    
                    for event_idx, event in enumerate(unit_timeline['events'], 1):
                        f.write(f"    [{event_idx}] {event['type'].upper()}\n")
                        if 'time_seconds' in event and event['time_seconds'] is not None:
                            f.write(f"        Time: {event['time_seconds']}s\n")
                        f.write(f"        {event['description']}\n")
                        
                        # Write details
                        if event['details']:
                            details = event['details']
                            
                            # Display warnings prominently FIRST
                            if 'warnings' in details and details['warnings']:
                                f.write(f"\n        ⚠️  WARNINGS:\n")
                                for warning in details['warnings']:
                                    f.write(f"            {warning}\n")
                                f.write("\n")
                            
                            # Handle question text specially
                            if 'question_text' in details:
                                f.write(f"        Question: {details['question_text']}\n")
                            
                            # Handle choices specially for multiple choice
                            if 'choices' in details:
                                f.write(f"\n        Choices:\n")
                                for choice in details['choices']:
                                    marker = "✓" if choice.get('correct') else " "
                                    choice_id = choice.get('id', '')
                                    choice_text = choice.get('text', '')
                                    f.write(f"          [{marker}] {choice_id}: {choice_text}\n")
                            # Adaptive logic diagram lines
                            if 'diagram_lines' in details:
                                f.write("\n        Adaptive Branching Diagram:\n")
                                for line in details['diagram_lines']:
                                    f.write(f"          {line}\n")
                            
                            # Handle correct answer for text input
                            elif 'correct_answer' in details:
                                f.write(f"\n        Expected Answer: {details['correct_answer']}\n")
                                if 'incorrect_answers' in details:
                                    f.write(f"        Wrong Answers: {', '.join(details['incorrect_answers'])}\n")
                            
                            # Write other details
                            f.write(f"\n        Details:\n")
                            for key, value in details.items():
                                # Skip items we've already displayed
                                if key in ['logic_rules', 'choices', 'question_text', 'correct_answer', 'incorrect_answers', 'warnings']:
                                    continue
                                
                                if isinstance(value, list) and len(value) > 5:
                                    f.write(f"          {key}: [{len(value)} items]\n")
                                elif isinstance(value, str) and len(value) > 100:
                                    f.write(f"          {key}: {value[:100]}...\n")
                                else:
                                    f.write(f"          {key}: {value}\n")
                        f.write("\n")
                    
                    f.write("\n")
        
        print(f"\n✓ Timeline report written to: {output_file}")

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
        
        if not self.validate_session_consistency():
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
    parser.add_argument('--timeline', action='store_true', help='Generate unit execution timeline report')
    parser.add_argument('-o', '--output', help='Output file for timeline report (default: <package>_timeline.txt)')
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
        
        # Generate timeline if requested
        if args.timeline:
            output_file = args.output
            if not output_file:
                base_name = os.path.splitext(os.path.basename(args.zip_path))[0]
                output_file = f"{base_name}_timeline.txt"
            validator.write_timeline_report(output_file)
        
    else:
        print("✗ Package validation failed!")
        summary = validator.get_summary()
        print(f"Errors: {len(summary['errors'])}")
        for error in summary['errors']:
            print(f"  - {error}")
        
        # Still generate timeline even on validation failure if requested
        if args.timeline:
            output_file = args.output
            if not output_file:
                base_name = os.path.splitext(os.path.basename(args.zip_path))[0]
                output_file = f"{base_name}_timeline.txt"
            try:
                validator.write_timeline_report(output_file)
            except Exception as e:
                print(f"Warning: Could not generate timeline: {e}")
        
        sys.exit(1)


if __name__ == '__main__':
    main()