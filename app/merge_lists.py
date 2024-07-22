"""merge multiple csv file containing clan data"""
import argparse

from utils.storage import read_file, store_file

def get_arguments() -> argparse.Namespace:
    ''' Parse arguments from CLI or if none supplied get them from Environmental variables'''
    parser = argparse.ArgumentParser(
        prog="Wot_language_detector",
        description="Read file containg Clan data and then try \
            to detect the langauge in their description.")
    parser.add_argument('-i',
                        '--input-files',
                        nargs='+',
                        help='Files to be merged',
                        required=True)
    parser.add_argument("--output-file",
                        "-o",
                        type=str,
                        help="File clan data will be stored in",
                        required=True)
    args = parser.parse_args()
    return args

def main():
    args = get_arguments()

    merged_files = {}
    for file in args.input_files:
        clans = read_file(file)
        merged_files |= clans

    store_file(merged_files, args.output_file)

if __name__ == "__main__":
    main()
