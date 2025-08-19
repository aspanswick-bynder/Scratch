import csv
import os
import re
from collections import defaultdict
from pathlib import Path

ext_to_mime = {}
mime_patterns = {}
valid_mimes = set()


def load_mime_mapping(mapping_path):
    with open(mapping_path, newline='', encoding='utf-8') as mapping_file:
        reader = csv.DictReader(mapping_file)
        for row in reader:
            ext = row['extension'].strip().lower()
            mime = row['mime_type'].strip().lower()

            # Save mapping: extension → MIME
            ext_to_mime[ext] = mime
            valid_mimes.add(mime)

            # Initialize regex pattern list for this MIME type if not present
            if mime not in mime_patterns:
                mime_patterns[mime] = []

            # Regex to match the file extension as a whole word (case-insensitive), e.g. matches 'jpg' in 'file.jpg' or 'jpg'
            mime_patterns[mime].append(re.compile(rf'\b{re.escape(ext)}\b', re.IGNORECASE))

            # Regex to match any string ending with the file extension (case-insensitive), e.g. matches 'v1jpg', 'testJPG', 'myfilejpg'
            mime_patterns[mime].append(re.compile(rf'.*{re.escape(ext)}$', re.IGNORECASE))

            # Regex to match the full MIME type string as a whole word (case-insensitive), e.g. matches 'image/jpeg' in 'image/jpeg'
            mime_patterns[mime].append(re.compile(rf'\b{re.escape(mime)}\b', re.IGNORECASE))


def find_file(pattern):
    for file in Path(".").iterdir():
        if file.name.lower() == pattern.lower():
            return str(file)
    return None


def normalize_entry(entry):
    return entry.lower()


def match_mime(entry):
    for mime_type, patterns in mime_patterns.items():
        for pattern in patterns:
            if pattern.search(entry):
                return mime_type
    return None


def process_counts(input_file, potential_outfile, valid_outfile, invalid_outfile):
    env = extract_env(input_file)
    valid_mime_aggregate = defaultdict(int)
    invalid_mime_aggregate = defaultdict(int)
    potential_mime_aggregate = defaultdict(int)
    valid_entry_map = defaultdict(list)
    invalid_entry_map = defaultdict(list)
    potential_entry_map = defaultdict(list)
    valid_mime_sum = 0
    invalid_mime_sum = 0
    possible_mime_sum = 0

    # Read input file
    with open(input_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader, None)  # Skip header row if present

        for row in reader:
            entry = row[0]

            # Ensure the second column is a valid integer count
            try:
                count = int(row[1])
            except (IndexError, ValueError):
                continue

            # Check if the entry is a valid MIME type
            if entry in valid_mimes:
                valid_mime_aggregate[entry] += count
                valid_entry_map[entry].append(entry)
                valid_mime_sum += count
            # Attempt to map the entry to a known MIME type
            elif match_mime(normalize_entry(entry)):
                matched_mime = match_mime(normalize_entry(entry))
                potential_mime_aggregate[matched_mime] += count
                potential_entry_map[matched_mime].append(entry)
                possible_mime_sum += count
            # If no match, save the invalid mime and count
            else:
                invalid_mime_aggregate[entry] += count
                invalid_entry_map[entry].append(entry)
                invalid_mime_sum += count

    write_potential_mime_types(potential_outfile, potential_mime_aggregate, potential_entry_map,
                               possible_mime_sum, env)
    write_valid_mime_types(valid_outfile, valid_mime_aggregate, valid_mime_sum, env)
    write_invalid_mime_types(invalid_outfile, invalid_mime_aggregate, invalid_mime_sum, env)

def write_potential_mime_types(output_file, potential_mime_aggregate, potential_entry_map,
                               possible_mime_sum, env):
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(['Matched Mime Types', 'Count', 'Potential Mime Types'])

        for mime, total_count in potential_mime_aggregate.items():
            entries = ", ".join(potential_entry_map[mime])
            writer.writerow([mime, total_count, entries])

        # Add a summary row with total sum of matched counts
        writer.writerow(['Total Count', possible_mime_sum, ''])

    print(f"Sum of counts for possible mime type matches for {env}: {possible_mime_sum}\n")


def write_invalid_mime_types(output_file, invalid_mime_aggregate, invalid_mime_sum, env):
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(['Invalid Mime Types', 'Count'])

        for mime, total_count in invalid_mime_aggregate.items():
            writer.writerow([mime, total_count])

        # Add a summary row with total sum of invalid counts
        writer.writerow(['Total Invalid Count', invalid_mime_sum])

    print(f"Sum of counts for invalid mime type matches for {env}: {invalid_mime_sum}\n")


def write_valid_mime_types(output_file, valid_mime_aggregate, valid_mime_sum, env):
    with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
        writer = csv.writer(outfile)
        writer.writerow(['Valid Mime Types', 'Count'])

        for mime, total_count in valid_mime_aggregate.items():
            writer.writerow([mime, total_count])

        # Add a summary row with total sum of valid counts
        writer.writerow(['Total Valid Count', valid_mime_sum])

    print(f"Sum of counts for valid mime type matches for {env}: {valid_mime_sum}\n")

def extract_env(filename):
    match = re.search(r'prod-(.*?)-mime-types-counts\.csv', filename)
    if match:
        return match.group(1)
    return None

def sum_counts(filename):
    total = 0
    with open(filename, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)
        next(reader, None)  # Skip header if present
        for row in reader:
            try:
                total += int(row[1])
            except (IndexError, ValueError):
                continue
    return total

def main():
    load_mime_mapping("mimeTypes.csv")

    files_envs = [
        (
            'prod-us-only-mime-types-counts.csv',
            'mime-type-mapping-US.csv',
            'valid-mime-type-mapping-US.csv',
            'invalid-mime-type-mapping-US.csv'
        ),
        (
            'prod-eu-only-mime-types-counts.csv',
            'mime-type-mapping-EU.csv',
            'valid-mime-type-mapping-EU.csv',
            'invalid-mime-type-mapping-EU.csv'
        ),
        (
            'prod-global-mime-types-counts.csv',
            'mime-type-mapping-Global.csv',
            'valid-mime-type-mapping-Global.csv',
            'invalid-mime-type-mapping-Global.csv'
        )
    ]

    total_count = 0
    for infile, potential_outfile, valid_outfile, invalid_outfile in files_envs:
        actual_file = find_file(infile)
        total_count += sum_counts(actual_file)
        if actual_file:
            process_counts(actual_file, potential_outfile, valid_outfile, invalid_outfile)
        else:
            print(f"File not found: {infile}")

    print(f"Total count across all files: {total_count}\n")


if __name__ == "__main__":
    main()
