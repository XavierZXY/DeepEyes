import json


def filter_jsonl(input_file, output_file, key, value):
    """
    Reads a JSON Lines file, filters the data based on a key-value pair,
    and writes the filtered data to a new JSON Lines file.

    Args:
        input_file (str): The path to the input .jsonl file.
        output_file (str): The path where the filtered .jsonl file will be saved.
        key (str): The key to filter on (e.g., 'claname').
        value (str): The value that the key must match (e.g., 'wood').
    """
    with (
        open(input_file, "r", encoding="utf-8") as infile,
        open(output_file, "w", encoding="utf-8") as outfile,
    ):
        for line in infile:
            try:
                data = json.loads(line)
                if data.get(key) == value:
                    outfile.write(line)
            except json.JSONDecodeError as e:
                print(f"Skipping a malformed line: {line.strip()} - Error: {e}")


# Example usage:
input_filename = "/data1/huggingface/hub/datasets--XimiaoZhang--MVTec-2K/snapshots/d52ff40b834d44cfcbea1fafc204666fc0da5b18/test_uni.jsonl"
input_filename = "data/enhanced_dataset_with_bboxes.jsonl"
output_filename = "data/transistor_data.jsonl"
filter_key = "clsname"
filter_value = "transistor"

filter_jsonl(input_filename, output_filename, filter_key, filter_value)

print(f"data have saved to '{output_filename}' ")
