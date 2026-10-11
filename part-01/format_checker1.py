import json
import os
from glob import glob
import argparse

FORMAT_CHECKER = 'format_checker.py'

ACCEPTED_REQUIREMENTS_FILENAME = 'requirements.txt'
ACCEPTED_SITE_LIST_FILENAMES = ['deonlinedrogist.nl', 'koopjesdrogisterij.nl', 'trekpleister.nl', 'kruidvat.nl', 'pharmamarket.nl']
ACCEPTED_VERSIONS = ['accept', 'reject', 'ublock', 'adguard']

VARIABLES = {
    'num_requests': [int],
    'num_cross_domain_redirections': [int],
    'num_requests_w_cookies': [int],
    'num_responses_w_cookies': [int],
    'third_party_domains': [list, [str]],
    'server_ips': [list, [str]],
    'potential_tracking_cookies': [list, [tuple, list]],
    'third_party_entities': [list, [str]],
    'post_request_origins': [list, [str]]
}

HAR_JSON_FILE_REQUIREMENT = 4

def check_har_or_json_files(subm_files):
    print('🔍 Checking for HAR and JSON files')
    found_har_count = 0
    found_json_count = 0

    detected_chosen_sites =  set()
    found_versions = {".har": set(), ".json": set()}

    for file in subm_files:
        # Check extension
        if file.endswith(".har"):
            ext = ".har"
            found_har_count += 1
        elif file.endswith(".json"):
            ext = ".json"
            found_json_count += 1
        else:
            if file != FORMAT_CHECKER:
                print(f'🚨 Unidentified file: {file}, check format.')
            continue

        # Split
        split = file[:-len(ext)].split('_')
        if len(split) != 2:
            print(f'🚨 Wrong filename: Too many underscores in {file}, naming should be <eTLD+1>_<version>{ext}')
            continue

        # Check domain
        site = split[0]
        if site not in ACCEPTED_SITE_LIST_FILENAMES:
            print(f'🚨 Wrong filename: Site domain not recognized in {file}, naming should be <eTLD+1>_<version>{ext}')
            continue
        detected_chosen_sites.add(site)

        # Check Version
        version = split[1]
        if version not in ACCEPTED_VERSIONS:
            print(f'🚨 Wrong filename: Version {version} not recognized in {file}, accepted versions are {ACCEPTED_VERSIONS}')
            continue
        found_versions[ext].add(version)

    passed_checks = True
    # Check Count
    if found_har_count < HAR_JSON_FILE_REQUIREMENT:
        print(f'☢️ Only found {found_har_count} HAR files, should be {HAR_JSON_FILE_REQUIREMENT}')
        passed_checks = False
    elif found_har_count > HAR_JSON_FILE_REQUIREMENT:
        print(f'🚨 Found {found_har_count} HAR files, should be {HAR_JSON_FILE_REQUIREMENT}')
        passed_checks = False
    if found_json_count < HAR_JSON_FILE_REQUIREMENT:
        print(f'☢️ Only found {found_json_count} JSON files, should be {HAR_JSON_FILE_REQUIREMENT}')
        passed_checks = False
    elif found_json_count > HAR_JSON_FILE_REQUIREMENT:
        print(f'🚨 Found {found_json_count} JSON files, should be {HAR_JSON_FILE_REQUIREMENT}')
        passed_checks = False

    # Check all versions present:
    if len(found_versions['.har']) != len(ACCEPTED_VERSIONS):
        print(f'☢️ Only found the following versions for HAR files: {found_versions['.har']}, should be {ACCEPTED_VERSIONS}')
        passed_checks = False
    if len(found_versions['.json']) != len(ACCEPTED_VERSIONS):
        print(f'☢️ Only found the following versions for JSON files: {found_versions['.json']}, should be {ACCEPTED_VERSIONS}')
        passed_checks = False

    if len(detected_chosen_sites) != 1:
        print(f'🚨 Only one site should be chosen. Detected {detected_chosen_sites}')
        passed_checks = False

    return passed_checks


def check_files(student_number):
    print('🔍 Checking for missing files')
    subm_files = os.listdir()

    found_requirements = False
    found_domain_map = False
    found_src_code_file = False
    found_pdf = False

    files_to_check = []

    # Loop through all files
    for file in subm_files:
        # Check the universal files
        if file == ACCEPTED_REQUIREMENTS_FILENAME:
            found_requirements = True
        elif file == 'domain_map.json':
            found_domain_map = True
        elif file == (student_number + ".py"):
            found_src_code_file = True
        elif file == (student_number + ".pdf"):
            found_pdf = True
        else:
            files_to_check.append(file)


    # Print Warnings based on missing files
    if not found_requirements:
        print(f'🚨 requirements.txt is missing')
    if not found_domain_map:
        print(f'🚨 domain_map.json is missing')
    if not found_src_code_file:
        print(f'☢️ No source code file found (should be {student_number}.py)')
    if not found_pdf:
        print(f'☢️ No report file found (should be {student_number}.pdf)')

    all_files_present = (found_requirements and found_domain_map and \
        found_src_code_file and found_pdf)

    passed_checks = check_har_or_json_files(files_to_check)

    if (all_files_present and passed_checks):
        print(f'✅ All files found')
        print('-----')
        print()
        return True
    else:
        print(f'❌ Not all files found')
        # print file list
        print("Detected Files:", subm_files)
        print('-----')
        print()
        return False

def check_variable_present_and_instance(student_solutions, variable_name, json_file):
    # Check if variable is present
    if variable_name not in student_solutions:
        print(f'🚨 Variable {variable_name} not found in {json_file}')
        return False
    # Check if major variable type is correct (int or list)
    if not isinstance(student_solutions[variable_name], VARIABLES[variable_name][0]):
        print(f'🚨 Variable {variable_name} in {json_file} is not a {VARIABLES[variable_name][0]} but a {type(student_solutions[variable_name]).__name__}')
        return False
    if len(VARIABLES[variable_name]) == 1:
        return True

    # If type is list, check inner type
    for item in student_solutions[variable_name]:
        if item is None:
            continue
        is_type = False
        for type_to_check in VARIABLES[variable_name][1]:
            if isinstance(item, type_to_check):
                is_type = True
        if not is_type:
            print(f'🚨 Item {item} in Variable {variable_name} in {json_file} is not a {VARIABLES[variable_name][1]} but a {type(item).__name__}')
            return False

    return True

def check_json_format():
    print('🔍 Checking json format')
    subm_files = os.listdir()

    json_files = glob("*.json")

    all_correct = True

    for json_file in json_files:
        if json_file == "domain_map.json":
            continue
        with open(json_file, 'r', encoding='utf-8') as f:
            student_solutions = json.load(f)

        json_file_is_correct = True

        for variable in VARIABLES:
            if not check_variable_present_and_instance(student_solutions, variable, json_file):
                json_file_is_correct = False
                all_correct = False


        if json_file_is_correct:
            print(f'✅ {json_file} is correctly formatted')
        else:
            print(f'❌ {json_file} is incorrectly formatted')

    print()
    if all_correct:
        print(f'✅ All detected JSON files are correctly formatted')
    else:
        print(f'❌ Some JSON files are incorrectly formatted')
    print('-----')
    print()

    return all_correct




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check submission files. Run as "python format_checker.py <student number>"')
    parser.add_argument("student_number", help="Student number, e.g. s012345")
    args = parser.parse_args()

    all_files_present = check_files(args.student_number)
    all_json_format = check_json_format()

    print('-----')
    if all_files_present and all_json_format:
        print(f'✅ Submission is correctly formatted ✅')
    else:
        print(f'❌ Submission contains formatting mistakes ❌')